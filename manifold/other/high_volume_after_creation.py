"""Calibration of world markets with at least 3,000, 10,000 or 20,000 mana traded by 1, 3, 6 and 12 months after creation.

python manifold/other/high_volume_after_creation.py -> manifold/other/plots/high_volume_after_creation/calibration.png, bins.csv, summary.csv
Needs data/manifold/api and manifold/labeling/results/full/manifold_final.jsonl. Snapshots are cached in data/manifold/snapshots_long_horizons.parquet.
"""
import json
from multiprocessing import Pool
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # manifold/
import snapshots as s
from plot_calibration import MIN_BETTORS, resampled_ratio

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "manifold/other/plots/high_volume_after_creation"
CACHE = ROOT / "data/manifold/snapshots_long_horizons.parquet"
EDGES = np.linspace(0, 1, 11)
MIN_VOLUMES = [3000, 10000, 20000]
MIN_VOLUME = MIN_VOLUMES[-1]
s.HOURS = {"1m": 24 * 30, "3m": 24 * 90, "6m": 24 * 180, "1y": 24 * 365}


def load():
    world = {a["id"] for a in map(json.loads, open(ROOT / "manifold/labeling/results/full/manifold_final.jsonl")) if a["group"] == "world"}
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
        ax.plot([0, 1], [0, 1], color="gray", lw=1)
        b = curve(everything)
        ax.plot(b.p, b.y, "o-", ms=2, lw=1, color="silver", label=f"all volumes: n={len(everything):,}")
        for volume, color in zip(MIN_VOLUMES, ["C0", "C1", "C2"]):
            g = everything[everything.volume >= volume]
            b = curve(g)
            low, high = np.array([resampled_ratio(g[g.bin == i], "y", "one") for i in b.index]).T
            gap = resampled_ratio(g, "gap", "one")
            yerr = [(b.y - low).clip(lower=0), (high - b.y).clip(lower=0)] if volume == MIN_VOLUME else None
            ax.errorbar(b.p, b.y, yerr=yerr, fmt="o-", ms=3, lw=1.3, capsize=2, color=color, label=f"{volume:,}+: n={len(g):,}, gap {g.gap.mean() * 100:+.1f} pp [{gap[0] * 100:+.1f}, {gap[1] * 100:+.1f}]")
            summary.append(dict(min_volume=volume, horizon=h, markets=len(g), creators=g.creator.nunique(), mean_price=g.prob.mean(), yes_share=g.y.mean(), gap=g.gap.mean(), gap_low=gap[0], gap_high=gap[1]))
            bins += [dict(min_volume=volume, horizon=h, low=EDGES[i], high=EDGES[i + 1], markets=int(v.n), mean_price=v.p, yes_share=v.y, yes_low=l, yes_high=u) for (i, v), l, u in zip(b.iterrows(), low, high)]
        ax.set_title(f"{h} after creation", fontsize=10)
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.grid(alpha=.2); ax.legend(fontsize=7, loc="upper left"); ax.set_xlabel("Mean price in bin")
    axes[0].set_ylabel("Fraction resolved YES")
    fig.suptitle(f"World markets by mana traded by the snapshot, all with {MIN_BETTORS}+ bettors by then. Higher minimums are subsets of lower ones. Bars on {MIN_VOLUME:,}+ only: 95% interval, resampling creators.")
    fig.tight_layout(); fig.savefig(OUT / "calibration.png", dpi=140)
    pd.DataFrame(bins).to_csv(OUT / "bins.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "summary.csv", index=False)
    print(pd.DataFrame(summary).round(3).to_string())
    high = d[d.volume >= MIN_VOLUME]
    counts = high.groupby("id").horizon.nunique()
    same = high[high.id.isin(counts[counts == len(s.HOURS)].index)].groupby("horizon").agg(markets=("y", "size"), mean_price=("prob", "mean"), yes_share=("y", "mean")).loc[list(s.HOURS)]
    same.to_csv(OUT / "same_markets.csv")
    print(same.round(3).to_string())
