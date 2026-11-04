"""Polymarket calibration split by the Haiku labels, like the Manifold plots in notes/second_pass_results.md.

python polymarket/calibration.py -> plots/polymarket/*.png, metrics.csv, bins.csv
Inputs: snapshots.jsonl and meta.csv (polymarket/prices.py), results.jsonl (16-question Haiku pass), outside_results.jsonl (polymarket/outside.py), cohorts.csv.
Main sample: the closed_by_feb cohort. Each market counts once per moment. Intervals resample events (event_title), because markets of one event share an outcome.
"""
import json, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from yes_bias import boot_rate, summary

OUT = HERE.parent / "plots/polymarket"
HORIZONS, MIN_BIN = ["1d", "1w", "1m"], 30
ANCHORS = {"after_start": "after trading starts", "before_close": "before closing"}


def frame():
    meta = pd.read_csv(HERE / "meta.csv", dtype={"id": str, "token": str})
    cohort = pd.read_csv(HERE / "cohorts.csv", dtype={"id": str})
    labels = pd.DataFrame([json.loads(json.loads(l)["result"]) for l in open(HERE / "results.jsonl")])
    outside = {i: s for l in open(HERE / "outside_results.jsonl") for i, s in json.loads(l)["answers"].items()}
    event = {m["id"]: m["event_title"] or m["question"] for m in map(json.loads, open(HERE / "input.jsonl"))}
    rows = []
    for s in map(json.loads, open(HERE / "snapshots.jsonl")):
        for k, v in s.items():
            if k != "id" and v[1] is not None:
                anchor, h = k.rsplit("_", 1)
                rows.append(dict(id=s["id"], anchor=anchor, horizon=h, prob=v[1], lag_h=v[2]))
    a = pd.DataFrame(rows).merge(meta[["id", "y"]], on="id", validate="m:1").merge(cohort[["id", "cohort"]], on="id", validate="m:1")
    a = a.merge(labels[["id", "default_side", "substantive"]], on="id", validate="m:1")
    a["outside"] = a.id.map(outside)
    a["creator"] = a.id.map(event)  # the resampling unit, named creator for the shared helpers
    a["prob"] = a.prob.clip(.001, .999)
    a["bin"] = np.minimum((a.prob * 10).astype(int), 9)
    a["source"] = np.where(a.outside.isna(), None, np.where(a.outside != "none", "has a source", np.where(a.substantive >= 80, "no source, substantive 80+", "no source, substantive <80")))
    return a


SPLITS = {
    "all": ("prob", [(None, "#1d4ed8", "All markets")]),
    "default_side": ("default_side", [("NO", "#c2410c", "Nothing happening means NO"), ("YES", "#1d4ed8", "Nothing happening means YES"), ("NONE", "#047857", "No default side")]),
    "source": ("source", [("has a source", "#6b7280", "Outside source exists"), ("no source, substantive <80", "#1d4ed8", "No source, substantive <80"), ("no source, substantive 80+", "#c2410c", "No source, substantive 80+")]),
}


def groups(a, split):
    col, sides = SPLITS[split]
    for side, color, label in sides:
        yield side, color, label, (a if side is None else a[a[col] == side])


def tables(a):
    bins, metrics = [], []
    for cohort, c in a.groupby("cohort"):
        for split in SPLITS:
            for (anchor, h), g in c.groupby(["anchor", "horizon"]):
                for side, _, label, s in groups(g, split):
                    if len(s) < MIN_BIN:
                        continue
                    m = summary(s)
                    metrics.append(dict(cohort=cohort, split=split, group=label, anchor=anchor, horizon=h, events=s.creator.nunique(), brier=((s.prob - s.y) ** 2).mean(), **m))
                    for b, x in s.groupby("bin"):
                        lo, hi = boot_rate(x) if len(x) >= MIN_BIN else (np.nan, np.nan)
                        bins.append(dict(cohort=cohort, split=split, group=label, anchor=anchor, horizon=h, bin=b, n=len(x), price=x.prob.mean(), yes=x.y.mean(), yes_low=lo, yes_high=hi))
    return pd.DataFrame(bins), pd.DataFrame(metrics)


def plot(bins, split, anchors, name, title, note):
    fig, axes = plt.subplots(len(anchors), 3, figsize=(15, 5.3 * len(anchors) + 1.2), squeeze=False, sharex=True, sharey=True)
    for row, anchor in zip(axes, anchors):
        for ax, h in zip(row, HORIZONS):
            ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
            ax.grid(color="#eeeeee", lw=.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set(xlim=(0, 100), ylim=(0, 100), title=f"{h} {ANCHORS[anchor]}")
            for (side, color, label), offset in zip(SPLITS[split][1], [(-4, 6), (5, -10), (6, 1)]):
                b = bins[(bins.cohort == "closed_by_feb") & (bins.split == split) & (bins.group == label) & (bins.anchor == anchor) & (bins.horizon == h) & (bins.n >= MIN_BIN)]
                b = b.set_index("bin").reindex(range(10))  # a dropped bin breaks the line
                ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker="o", ms=5, lw=1.8, elinewidth=.8, label=label)
                for r in b.dropna(subset="n").itertuples():
                    ax.annotate(f"{int(r.n):,}", (r.price * 100, r.yes * 100), xytext=offset, textcoords="offset points", ha="right" if offset[0] < 0 else "left", fontsize=7, color="#444444")
        row[0].set_ylabel("Resolved YES (%)")
    for ax in axes[-1]:
        ax.set_xlabel("Price (%)")
    axes[0][0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle(title, x=.01, ha="left", fontsize=14)
    fig.text(.01, .01, "Source: Polymarket Gamma and CLOB APIs; labels from Haiku, which saw text only. Resolved Yes/No markets that closed before Feb 2, 2026 with $1,000+ lifetime volume, sports, asset-price and weather markets removed.\n"
             "Price: last hourly API price at or before the moment, at most 3 days old; moments outside trading skipped. 10-point bins, bins under 30 markets dropped, number = markets in the bin. Bars: 95%, resampling events.\n" + note,
             fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, .1 if len(anchors) == 1 else .06, 1, .96))
    fig.savefig(OUT / f"{name}.png", dpi=140)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    a = frame()
    print(a.groupby(["cohort", "anchor", "horizon"]).size().to_string(), f"\nno outside answer: {a.outside.isna().mean():.1%} of snapshots, median price age {a.lag_h.median():.1f}h", flush=True)
    bins, metrics = tables(a)
    bins.to_csv(OUT / "bins.csv", index=False)
    metrics.round(4).to_csv(OUT / "metrics.csv", index=False)
    plot(bins, "all", list(ANCHORS), "overall", "Polymarket calibration, all labeled markets",
         "Before closing: a market that resolves YES early closes early, so this moment depends on the outcome.")
    plot(bins, "default_side", ["after_start"], "by_side", "Polymarket, split by what happens if nothing new happens", "Haiku answered: if nothing new happens until the deadline, how does this resolve?")
    plot(bins, "source", ["after_start"], "by_source", "Polymarket, split by whether an outside source gives the answer",
         "Outside source: Haiku's forced-choice follow-up (polymarket/outside_prompt.txt): poll, odds, finance, data series, schedule or published forecast, not another prediction market. Substantive: 0-100 score from the main pass.")


if __name__ == "__main__":
    main()
