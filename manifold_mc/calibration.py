"""Calibration of Manifold multiple-choice options, next to the binary markets.

python manifold_mc/calibration.py -> manifold_mc/plots/*.png, bins.csv, metrics.csv
Inputs: data/manifold_mc/snapshots.parquet (manifold_mc/snapshots.py), manifold_mc/labels.jsonl (manifold_mc/labeling.py).
Main sample, as for binary markets (manifold/plots/calibration_*_15_bettors_by_then): price a fixed time after the market opened,
15+ bettors in the market by then, option still unresolved then. Groups (world, traded elsewhere, ...) come from the
Haiku labels with the binary rule (src/labeling_pilot.py group); binary groups mostly come from Jev instead.
Two weightings: every option counts 1, or every option 1/K, K = the market's options in that sample, so each market counts once.
Bars: 95%, resampling whole markets (options of one market share an outcome); metrics.csv also resamples creators.
"""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "manifold")]
from labeling_pilot import JEV_NO, JEV_YES, SCORED, group
from plot_calibration import EDGES
from stats import logit, wshift

OUT = ROOT / "manifold_mc/plots"
HORIZONS, MIN_BIN, DRAWS = ["1d", "1w", "1m"], 30, 1000


def frame():
    labels = {}
    for line in open(ROOT / "manifold_mc/labels.jsonl"):
        a = json.loads(json.loads(line)["result"])
        p = a["substantive"] / 100
        a["yes"] += [SCORED] * (p >= JEV_YES)
        a["unsure"] += [SCORED] * (JEV_NO < p < JEV_YES)
        labels[a["id"]] = a
    sides = {(i, o["n"]): o["default_side"] for i, a in labels.items() for o in a["options"]}
    index = {a["id"]: a["index"] for m in map(json.loads, open(ROOT / "data/manifold_mc/full.jsonl")) for a in m["answers"]}
    d = pd.read_parquet(ROOT / "data/manifold_mc/snapshots.parquet")
    unlabeled = d.loc[~d.id.isin(labels), "id"].nunique()
    assert unlabeled < 50, f"{unlabeled} markets have no labels"
    d = d[d.id.isin(labels)].copy()
    d["group"] = d.id.map(lambda i: group(labels[i]))
    d["default_side"] = [sides[(i, index[a])] for i, a in zip(d.id, d.answer)]
    d["prob"] = d.prob.clip(.001, .999)
    d["bin"] = pd.cut(d.prob, EDGES, include_lowest=True, labels=False).astype(int)
    return d


def main_sample(d):
    s = d[(d.anchor == "after_creation") & (d.bettors >= 15) & d.horizon.isin(HORIZONS)].copy()
    s["w"] = 1 / s.groupby(["id", "horizon"]).id.transform("size")
    return s


def boot(g, w, by="id", seed=0):
    """95% interval of the weighted YES rate, resampling whole clusters."""
    c = pd.factorize(g[by])[0]
    rng = np.random.default_rng(seed)
    k = np.array([np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c] for _ in range(DRAWS)]) * w
    return np.percentile(k @ g.y.to_numpy() / k.sum(axis=1), [2.5, 97.5])


def summary(g, w):
    x, y = logit(g.prob.to_numpy()), g.y.to_numpy()
    out = dict(options=len(g), markets=g.id.nunique(), creators=g.creator.nunique(), price=np.average(g.prob, weights=w), yes=np.average(y, weights=w),
               brier=np.average((g.prob - y) ** 2, weights=w), shift=wshift(x, y, w))
    rng = np.random.default_rng(0)
    for by in ["id", "creator"]:
        c = pd.factorize(g[by])[0]
        draws = [wshift(x, y, w * np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c]) for _ in range(200)]
        out[f"shift_low_{by}"], out[f"shift_high_{by}"] = np.percentile(draws, [2.5, 97.5])
    return out


SPLITS = {  # name: list of (label, color, filter)
    "world": [("World, each option counts 1", "#1d4ed8", lambda s: s.group == "world"),
              ("World, each market counts once", "#c2410c", lambda s: s.group == "world")],
    "kind": [("World, one winner", "#1d4ed8", lambda s: (s.group == "world") & s.one_winner),
             ("World, options resolve independently", "#c2410c", lambda s: (s.group == "world") & ~s.one_winner)],
    "added": [("World, options there from the start", "#1d4ed8", lambda s: (s.group == "world") & s.initial),
              ("World, options added later", "#c2410c", lambda s: (s.group == "world") & ~s.initial)],
    "side": [("World, nothing happening means NO", "#c2410c", lambda s: (s.group == "world") & (s.default_side == "NO")),
             ("World, nothing happening means YES", "#1d4ed8", lambda s: (s.group == "world") & (s.default_side == "YES")),
             ("World, no default side", "#047857", lambda s: (s.group == "world") & (s.default_side == "NONE"))],
    "groups": [("World", "#1d4ed8", lambda s: s.group == "world"), ("Traded elsewhere", "#6b7280", lambda s: s.group == "traded_elsewhere"),
               ("Not substantive", "#c2410c", lambda s: s.group == "not_substantive")],
}


def weights(label, g):
    return g.w.to_numpy() if "market counts once" in label else np.ones(len(g))


def tables(s):
    bins, metrics = [], []
    for split, lines in SPLITS.items():
        for label, _, keep in lines:
            for h, g in s[keep(s)].groupby("horizon"):
                if g.id.nunique() < MIN_BIN:
                    continue
                metrics.append(dict(split=split, line=label, horizon=h, **summary(g, weights(label, g))))
                for b, x in g.groupby("bin"):
                    w = weights(label, x)
                    lo, hi = boot(x, w) if x.id.nunique() >= MIN_BIN else (np.nan, np.nan)
                    bins.append(dict(split=split, line=label, horizon=h, bin=b, options=len(x), markets=x.id.nunique(),
                                     price=np.average(x.prob, weights=w), yes=np.average(x.y, weights=w), yes_low=lo, yes_high=hi))
    return pd.DataFrame(bins), pd.DataFrame(metrics)


def plot(bins, split, name, title, note, binary=False):
    fig, axes = plt.subplots(1, 3, figsize=(15, 6.4), sharex=True, sharey=True)
    old = pd.read_csv(ROOT / "manifold/plots/calibration_15_bettors_by_then_bins.csv") if binary else None
    for ax, h in zip(axes, HORIZONS):
        ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
        ax.grid(color="#eeeeee", lw=.6)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set(xlim=(0, 100), ylim=(0, 100), title=f"{h} after the market opened", xlabel="Price (%)")
        if binary:
            o = old[(old.group == "world") & (old.anchor == "after_creation") & (old.horizon == h) & (old.markets >= MIN_BIN)]
            ax.plot(o.mean_price * 100, o.yes_share * 100, color="#9ca3af", marker="s", ms=4, lw=1.4, label="World, binary markets")
        for (label, color, _), offset in zip(SPLITS[split], [(-4, 6), (5, -10), (6, 1)]):
            b = bins[(bins.split == split) & (bins.line == label) & (bins.horizon == h) & (bins.markets >= MIN_BIN)].set_index("bin").reindex(range(len(EDGES) - 1))
            ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker="o", ms=5, lw=1.8, elinewidth=.8, label=label)
            for r in b.dropna(subset="markets").itertuples():
                ax.annotate(f"{int(r.options):,}/{int(r.markets):,}", (r.price * 100, r.yes * 100), xytext=offset, textcoords="offset points",
                            ha="right" if offset[0] < 0 else "left", fontsize=6.5, color=color)
    axes[0].set_ylabel("Resolved YES (%)")
    axes[0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle(title, x=.01, ha="left", fontsize=14)
    fig.text(.01, .01, "Source: Manifold API. Resolved multiple-choice markets with 15+ bettors and 1,000+ mana in all; each option is a YES/NO forecast, 'Other' and options resolved N/A or split are left out.\n"
             "Price: the option's price after the last bet that moved it, at the moment; the market needs 15+ bettors by then and the option must exist and be unresolved then.\n"
             "Bins as for binary markets, bins with under 30 markets dropped; numbers = options/markets in the bin. Bars: 95%, resampling whole markets. World: Haiku labels, binary group rule.\n" + note,
             fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, .13, 1, .95))
    fig.savefig(OUT / f"{name}.png", dpi=140)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = main_sample(frame())
    print(s.groupby("horizon").agg(options=("id", "size"), markets=("id", "nunique")).to_string(), flush=True)
    bins, metrics = tables(s)
    bins.round(4).to_csv(OUT / "bins.csv", index=False)
    metrics.round(4).to_csv(OUT / "metrics.csv", index=False)
    plot(bins, "world", "world", "Manifold multiple-choice options, world questions",
         "Each market counts once: every option weighted 1/K. Grey: binary world markets, same moment and gate (manifold/plots/calibration_15_bettors_by_then_bins.csv, Jev/Opus labels).", binary=True)
    plot(bins, "kind", "kind", "One-winner vs independent options", "One winner: exactly one option resolves YES. Independent: each option resolves YES or NO on its own.")
    plot(bins, "added", "added", "Options present at the start vs added later", "From the start: created within a minute of the market. A later option enters only once it exists, so no future information is used.")
    plot(bins, "side", "side", "Split by each option's default side", "Haiku, per option: if nothing new happens until the deadline, how does this option resolve?")
    plot(bins, "groups", "groups", "Split by question type", "Groups from Haiku's market labels with the rule used for binary markets.")


if __name__ == "__main__":
    main()
