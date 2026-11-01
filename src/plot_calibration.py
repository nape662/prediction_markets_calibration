"""Calibration per plot group, at fixed times before resolution and after creation, with Brier scores against a constant guess.

python src/plot_calibration.py -> plots/calibration_<anchor>_<filter>.png, plots/calibration_<filter>_bins.csv, plots/calibration_<filter>_brier.csv
filter is 15_bettors_ever (by the market's end, which uses the future) or 15_bettors_by_then (already there when the price is taken).
Needs data/manifold/snapshots.parquet (src/snapshots.py) and labeling/results/full/manifold_final.jsonl.
The constant guess is each panel's own YES share, known only afterwards, which flatters it slightly.
Intervals resample creators, a cheap stand-in for related questions; markets from different creators can still share one outcome.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
EDGES = [0, .02, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, .98, 1]
HORIZONS = ["12h", "1d", "1w", "1m", "1y"]
GROUPS = {"world": "World", "traded_elsewhere": "Traded elsewhere\n(sport, prices, weather, scheduled numbers, words)", "not_forecast": "Not a forecast\n(existing facts, estimates, puzzles)",
          "fixed_chance": "Fixed chance\n(coin flips, dice, lotteries)", "not_substantive": "Not substantive\n(games about the market, empty questions)"}
ANCHORS = {"before_resolution": "before resolution", "after_creation": "after creation"}
RESAMPLES, FEW, FEW_CREATORS, MIN_BETTORS = 2000, 30, 5, 15
FILTERS = {"15_bettors_ever": "OLD FILTER: 15 bettors at any point in the market's life, even after this price was taken. This uses the future.",
           "15_bettors_by_then": "NEW FILTER: 15 bettors already there when this price was taken."}
rng = np.random.default_rng(0)


def load():
    groups = {a["id"]: a["group"] for a in map(json.loads, open(ROOT / "labeling/results/full/manifold_final.jsonl"))}
    d = pd.read_parquet(ROOT / "data/manifold/snapshots.parquet")
    assert set(d.resolution) == {"YES", "NO"}
    d["group"] = d.id.map(groups)
    assert d.group.notna().all()
    creators = {m["id"]: m["creatorId"] for m in map(json.loads, open(ROOT / "data/manifold/api/markets.jsonl")) if m["id"] in groups}
    d["creator"] = d.id.map(creators)
    d["y"] = (d.resolution == "YES").astype(float)
    d["bin"] = pd.cut(d.prob, EDGES, include_lowest=True, labels=False).astype(int)
    return d[d.group.isin(GROUPS)]


def resampled_ratio(g, top, bottom):
    """95% interval of sum(top) / sum(bottom), resampling creators."""
    t, b = g.groupby("creator")[top].sum().to_numpy(), g.groupby("creator")[bottom].sum().to_numpy()
    draws = rng.multinomial(len(t), np.full(len(t), 1 / len(t)), RESAMPLES)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.nanpercentile(draws @ t / (draws @ b), [2.5, 97.5])


def tables(d):
    bins, brier = [], []
    for (anchor, group, h), g in d.groupby(["anchor", "group", "horizon"]):
        g = g.assign(one=1.0)
        key = dict(anchor=anchor, group=group, horizon=h)
        for b, x in g.groupby("bin"):
            i = resampled_ratio(x, "y", "one") if 0 < x.y.mean() < 1 and x.creator.nunique() >= FEW_CREATORS else [np.nan, np.nan]  # resampling can't show what it never saw
            bins.append(dict(key, low=EDGES[b], high=EDGES[b + 1], markets=len(x), mean_price=x.prob.mean(), yes_share=x.y.mean(), yes_low=i[0], yes_high=i[1]))
        decided = (g.prob < .02) | (g.prob > .98)
        for name, x in [("all", g), ("without below 2% and above 98%", g[~decided])]:
            if len(x):
                x = x.assign(market=(x.prob - x.y) ** 2)
                i = resampled_ratio(x, "market", "one")
                brier.append(dict(key, markets_used=name, markets=len(x), share_of_panel=len(x) / len(g), yes_share=x.y.mean(), brier_market=x.market.mean(), brier_market_low=i[0],
                                  brier_market_high=i[1], brier_constant=x.y.mean() * (1 - x.y.mean())))
    return pd.DataFrame(bins), pd.DataFrame(brier)


def plot(bins, brier, anchor, name):
    fig, axes = plt.subplots(len(GROUPS), len(HORIZONS), figsize=(18, 19), sharex=True, sharey=True)
    biggest = bins.markets.max()
    for r, (group, label) in enumerate(GROUPS.items()):
        for c, h in enumerate(HORIZONS):
            ax = axes[r, c]
            key = (bins.anchor == anchor) & (bins.group == group) & (bins.horizon == h)
            ax.plot([0, 100], [0, 100], color="#999999", linewidth=1)
            ax.set_xlim(0, 100), ax.set_ylim(0, 100)
            ax.set_xticks(range(0, 101, 25)), ax.set_yticks(range(0, 101, 25))
            ax.grid(color="#e4e4e4", linewidth=0.6), ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
            s = brier[(brier.anchor == anchor) & (brier.group == group) & (brier.horizon == h) & (brier.markets_used == "all")]
            markets = int(s.markets.iloc[0]) if len(s) else 0
            ax.set_title(f"{h} {ANCHORS[anchor]}, {markets:,} markets", fontsize=10)
            if markets:
                ax.text(98, 3, f"Brier, lower is better\nMarket {s.brier_market.iloc[0]:.3f}\nConstant {s.yes_share.iloc[0]:.0%} {s.brier_constant.iloc[0]:.3f}", ha="right", va="bottom", fontsize=9)
            x = bins[key]
            for few, face in [(False, "#2a6fbb"), (True, "white")]:
                p = x[(x.markets < FEW) == few]
                ax.errorbar(p.mean_price * 100, p.yes_share * 100, yerr=[(p.yes_share - p.yes_low).fillna(0) * 100, (p.yes_high - p.yes_share).fillna(0) * 100], fmt="none", ecolor="#2a6fbb", elinewidth=1, zorder=2)
                ax.scatter(p.mean_price * 100, p.yes_share * 100, s=12 + 120 * np.sqrt(p.markets / biggest), facecolor=face, edgecolor="#2a6fbb", zorder=3, clip_on=False)
        axes[r, 0].set_ylabel(f"{label}\n\nWhat happened (% resolved YES)", fontsize=9.5)
    for ax in axes[-1]:
        ax.set_xlabel("What the market said (%)")
    fig.suptitle(f"Do markets happen as often as the price says, {ANCHORS[anchor]}? On the line means yes", fontsize=14, x=0.01, y=0.995, ha="left")
    fig.text(0.01, 0.965, FILTERS[name], fontsize=15, fontweight="bold", color="#c00000")
    how = {"before_resolution": "resolution minus the horizon. YES markets often resolve early, so this moment depends on the outcome.",
           "after_creation": "creation plus the horizon, for markets still unresolved then. Traders can see that a market is still open, so this doesn't depend on the outcome. Only resolved markets are in the data, so ones still open today are missing."}[anchor]
    fig.text(0.01, 0.005, "Groups from the merged Jev, Opus and Terra labels, first match wins; the 38 direct-opinion markets aren't shown. Manifold YES/NO markets.\n"
             f"Each market counts once per panel, at its last price-moving bet at or before {how}\n"
             "One dot per price range (0-2, 2-5, 5-10, 10-20 ... 80-90, 90-95, 95-98, 98-100), placed at the range's average price. Bigger dot = more markets; hollow = under 30.\n"
             "Bars: 95% interval from resampling creators, likely still too narrow; no bar under 5 creators or where every market resolved the same way. Constant: guessing the panel's own YES share for every market.", fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, 0.035, 1, 0.96))
    fig.savefig(ROOT / f"plots/calibration_{anchor}_{name}.png", dpi=110)


if __name__ == "__main__":
    d = load()
    for name, data in [("15_bettors_ever", d), ("15_bettors_by_then", d[d.bettors >= MIN_BETTORS])]:
        bins, brier = tables(data)
        bins.to_csv(ROOT / f"plots/calibration_{name}_bins.csv", index=False, float_format="%.4f")
        brier.to_csv(ROOT / f"plots/calibration_{name}_brier.csv", index=False, float_format="%.4f")
        for anchor in ANCHORS:
            plot(bins, brier, anchor, name)
        a = brier[brier.markets_used == "all"]
        print(name)
        for col in ["markets", "brier_market", "brier_constant"]:
            print(col); print(a.pivot_table(index=["anchor", "group"], columns="horizon", values=col)[HORIZONS].round(3).to_string())
        print(bins[(bins.group == "world") & (bins.horizon.isin(["12h", "1w", "1m"])) & (bins.anchor == "after_creation")][["horizon", "low", "markets", "mean_price", "yes_share"]].round(3).to_string())
