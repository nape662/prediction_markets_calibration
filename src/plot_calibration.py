"""Calibration of world markets at each horizon, and Brier scores against two forecasts that ignore the question.

python src/plot_calibration.py -> plots/calibration_world.png, plots/calibration_world_bins.csv, plots/calibration_world_brier.csv
Needs data/manifold/snapshots.parquet (src/snapshots.py) and labeling/results/full/manifold_final.jsonl.
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
RESAMPLES, FEW = 2000, 30
rng = np.random.default_rng(0)


def world():
    ids = {a["id"] for a in map(json.loads, open(ROOT / "labeling/results/full/manifold_final.jsonl")) if a["group"] == "world"}
    d = pd.read_parquet(ROOT / "data/manifold/snapshots.parquet")
    d = d[d.id.isin(ids)].copy()
    assert set(d.resolution) == {"YES", "NO"}
    creators = {m["id"]: m["creatorId"] for m in map(json.loads, open(ROOT / "data/manifold/api/markets.jsonl")) if m["id"] in ids}
    d["creator"] = d.id.map(creators)
    d["y"] = (d.resolution == "YES").astype(float)
    d["bin"] = pd.cut(d.prob, EDGES, include_lowest=True, labels=False).astype(int)
    return d


def resampled_ratio(g, top, bottom):
    """95% interval of sum(top) / sum(bottom), resampling creators."""
    t, b = g.groupby("creator")[top].sum().to_numpy(), g.groupby("creator")[bottom].sum().to_numpy()
    draws = rng.multinomial(len(t), np.full(len(t), 1 / len(t)), RESAMPLES)
    with np.errstate(invalid="ignore"):
        return np.nanpercentile(draws @ t / (draws @ b), [2.5, 97.5])


def tables(d):
    bins, brier = [], []
    for h in HORIZONS:
        g = d[d.horizon == h].assign(one=1.0)
        for b, x in g.groupby("bin"):
            bins.append(dict(horizon=h, low=EDGES[b], high=EDGES[b + 1], markets=len(x), mean_price=x.prob.mean(), yes_share=x.y.mean(),
                             yes_low=(i := resampled_ratio(x, "y", "one"))[0], yes_high=i[1]))
        decided = (g.prob < .02) | (g.prob > .98)
        for name, x in [("all", g), ("without below 2% and above 98%", g[~decided])]:
            x = x.assign(market=(x.prob - x.y) ** 2, no=x.y, rate=(x.y.mean() - x.y) ** 2)
            brier.append(dict(horizon=h, markets_used=name, markets=len(x), share_of_horizon=len(x) / len(g), yes_share=x.y.mean(), brier_market=x.market.mean(),
                              brier_market_low=(i := resampled_ratio(x, "market", "one"))[0], brier_market_high=i[1], brier_always_no=x.no.mean(), brier_constant_rate=x.rate.mean()))
    bins = pd.DataFrame(bins)
    bins.loc[bins.yes_share.isin([0, 1]), ["yes_low", "yes_high"]] = np.nan  # resampling can't produce an outcome it never saw, so it would claim certainty
    return bins, pd.DataFrame(brier)


def plot(bins, brier):
    fig, axes = plt.subplots(1, 5, figsize=(18, 5), sharex=True, sharey=True)
    for ax, h in zip(axes, HORIZONS):
        x, b = bins[bins.horizon == h], brier[(brier.horizon == h) & (brier.markets_used == "all")].iloc[0]
        ax.plot([0, 100], [0, 100], color="#999999", linewidth=1)
        for few, face in [(False, "#2a6fbb"), (True, "white")]:
            s = x[(x.markets < FEW) == few]
            ax.errorbar(s.mean_price * 100, s.yes_share * 100, yerr=[(s.yes_share - s.yes_low) * 100, (s.yes_high - s.yes_share) * 100], fmt="none", ecolor="#2a6fbb", elinewidth=1, zorder=2)
            ax.scatter(s.mean_price * 100, s.yes_share * 100, s=12 + 120 * np.sqrt(s.markets / bins.markets.max()), facecolor=face, edgecolor="#2a6fbb", zorder=3)
        ax.set_title(f"{h} before resolution, {int(b.markets):,} markets", fontsize=10)
        ax.text(98, 3, f"Brier, lower is better\nMarket {b.brier_market:.3f}\nConstant {b.yes_share:.0%} {b.brier_constant_rate:.3f}\nAlways NO {b.brier_always_no:.3f}", ha="right", va="bottom", fontsize=9)
        ax.set_xlim(0, 100), ax.set_ylim(0, 100)
        ax.set_xticks(range(0, 101, 25)), ax.set_yticks(range(0, 101, 25))
        ax.grid(color="#e4e4e4", linewidth=0.6), ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlabel("What the market said (%)")
    axes[0].set_ylabel("What actually happened (% resolved YES)")
    fig.suptitle("Do world markets happen as often as the price says? On the line means yes", fontsize=14, x=0.01, ha="left")
    fig.text(0.01, 0.01, "World group from the merged Jev, Opus and Terra labels, Manifold YES/NO markets with at least 15 bettors. Each market counts once per panel, at its last price-moving bet at or before resolution minus the horizon.\n"
             "One dot per price range (0-2, 2-5, 5-10, 10-20 ... 80-90, 90-95, 95-98, 98-100), placed at the range's average price. Bigger dot = more markets; hollow = under 30. Bars: 95% interval from resampling creators, likely still too narrow; no bar where every market in the range resolved the same way.\n"
             "Horizons count back from the actual resolution, and YES markets often resolve early, so the time before resolution depends on the outcome. The 1y panel holds fewer, longer-running markets.", fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, 0.11, 1, 0.97))
    fig.savefig(ROOT / "plots/calibration_world.png", dpi=130)


if __name__ == "__main__":
    bins, brier = tables(world())
    bins.to_csv(ROOT / "plots/calibration_world_bins.csv", index=False, float_format="%.4f")
    brier.to_csv(ROOT / "plots/calibration_world_brier.csv", index=False, float_format="%.4f")
    plot(bins, brier)
    print(brier.round(3).to_string())
    print(bins.round(3).to_string())
