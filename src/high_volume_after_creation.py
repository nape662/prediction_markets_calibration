"""Calibration of world markets with at least 20,000 mana traded by 1, 3, 6 and 12 months after creation.

python src/high_volume_after_creation.py -> plots/high_volume_after_creation/calibration.png, bins.csv, summary.csv
Needs data/manifold/api and labeling/results/full/manifold_final.jsonl. Snapshots are cached in data/manifold/snapshots_long_horizons.parquet.
"""
import json
from multiprocessing import Pool
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import snapshots as s
from plot_calibration import MIN_BETTORS, resampled_ratio

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "plots/high_volume_after_creation"
CACHE = ROOT / "data/manifold/snapshots_long_horizons.parquet"
EDGES = np.linspace(0, 1, 11)
MIN_VOLUME = 20000
s.HOURS = {"1m": 24 * 30, "3m": 24 * 90, "6m": 24 * 180, "1y": 24 * 365}


def load():
    world = {a["id"] for a in map(json.loads, open(ROOT / "labeling/results/full/manifold_final.jsonl")) if a["group"] == "world"}
    markets = [m for m in map(json.loads, open(s.API / "markets.jsonl")) if m["id"] in world]
    assert len(markets) == len(world), (len(markets), len(world))
    if not CACHE.exists():
        with Pool(8) as pool:
            rows = [r for market in pool.imap_unordered(s.snapshots, markets, chunksize=200) for r in market]
        pd.DataFrame(rows).query("anchor == 'after_creation'").to_parquet(CACHE)
    d = pd.read_parquet(CACHE)
    assert set(d.resolution) == {"YES", "NO"}
    d["creator"] = d.id.map({m["id"]: m["creatorId"] for m in markets})
    d["y"] = (d.resolution == "YES").astype(float)
    d["one"] = 1.0
    d["gap"] = d.prob - d.y
    d["bin"] = pd.cut(d.prob, EDGES, include_lowest=True, labels=False).astype(int)
    return d[d.bettors >= MIN_BETTORS]


def curve(g):
    return g.groupby("bin").agg(n=("y", "size"), p=("prob", "mean"), y=("y", "mean")).query("n >= 10")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    d = load()
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.6), sharex=True, sharey=True)
    bins, summary = [], []
    for ax, h in zip(axes, s.HOURS):
        everything = d[d.horizon == h]
        g = everything[everything.volume >= MIN_VOLUME]
        ax.plot([0, 1], [0, 1], color="gray", lw=1)
        b = curve(everything)
        ax.plot(b.p, b.y, "o-", ms=2, lw=1, color="silver", label=f"all volumes: n={len(everything):,}")
        b = curve(g)
        low, high = np.array([resampled_ratio(g[g.bin == i], "y", "one") for i in b.index]).T
        ax.errorbar(b.p, b.y, yerr=[(b.y - low).clip(lower=0), (high - b.y).clip(lower=0)], fmt="o-", ms=4, capsize=2, color="C2", label=f"{MIN_VOLUME:,}+ mana: n={len(g):,}")
        gap = resampled_ratio(g, "gap", "one")
        summary.append(dict(horizon=h, markets=len(g), creators=g.creator.nunique(), mean_price=g.prob.mean(), yes_share=g.y.mean(), gap=g.gap.mean(), gap_low=gap[0], gap_high=gap[1]))
        bins += [dict(horizon=h, low=EDGES[i], high=EDGES[i + 1], markets=int(v.n), mean_price=v.p, yes_share=v.y, yes_low=l, yes_high=u) for (i, v), l, u in zip(b.iterrows(), low, high)]
        ax.set_title(f"{h} after creation\nprice {g.prob.mean():.0%}, YES {g.y.mean():.0%}, gap {g.gap.mean() * 100:+.1f} pp [{gap[0] * 100:+.1f}, {gap[1] * 100:+.1f}]", fontsize=10)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.grid(alpha=.2); ax.legend(fontsize=8, loc="upper left"); ax.set_xlabel("Mean price in bin")
    axes[0].set_ylabel("Fraction resolved YES")
    fig.suptitle(f"World markets with at least {MIN_VOLUME:,} mana traded and {MIN_BETTORS} bettors by the snapshot. Bars: 95% interval, resampling creators.")
    fig.tight_layout(); fig.savefig(OUT / "calibration.png", dpi=140)
    pd.DataFrame(bins).to_csv(OUT / "bins.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "summary.csv", index=False)
    print(pd.DataFrame(summary).round(3).to_string())
    high = d[d.volume >= MIN_VOLUME]
    counts = high.groupby("id").horizon.nunique()
    same = high[high.id.isin(counts[counts == len(s.HOURS)].index)].groupby("horizon").agg(markets=("y", "size"), mean_price=("prob", "mean"), yes_share=("y", "mean")).loc[list(s.HOURS)]
    same.to_csv(OUT / "same_markets.csv")
    print(same.round(3).to_string())
