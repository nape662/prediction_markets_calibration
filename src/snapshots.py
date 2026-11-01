"""The price of every labeled Manifold market at fixed times before resolution.

python src/snapshots.py -> data/manifold/snapshots.parquet: id, horizon, prob, age_days, resolution
A snapshot is probAfter of the last non-redemption bet that moved the price, at or before resolution minus the horizon.
A market with no such bet has no row at that horizon. age_days is how old that bet is at the snapshot.
"""
import json
from multiprocessing import Pool
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "data/manifold/api"
HOURS = {"12h": 12, "1d": 24, "1w": 24 * 7, "1m": 24 * 30, "1y": 24 * 365}


def snapshots(market):
    moves = [b for b in json.load(open(API / "bets" / f"{market['id']}.json")) if not b.get("isRedemption") and b["probBefore"] != b["probAfter"]]
    rows = []
    for name, hours in HOURS.items():
        t = market["resolutionTime"] - hours * 3600e3
        before = [b for b in moves if b["createdTime"] <= t]
        if before:
            rows.append(dict(id=market["id"], horizon=name, prob=before[-1]["probAfter"], age_days=(t - before[-1]["createdTime"]) / 86400e3, resolution=market["resolution"]))
    return rows


if __name__ == "__main__":
    ids = {json.loads(l)["id"] for l in open(ROOT / "labeling/results/full/manifold_final.jsonl")}
    markets = [m for m in map(json.loads, open(API / "markets.jsonl")) if m["id"] in ids]
    assert len(markets) == len(ids), (len(markets), len(ids))
    with Pool(8) as pool:
        rows = [r for market in pool.imap_unordered(snapshots, markets, chunksize=200) for r in market]
    pd.DataFrame(rows).to_parquet(ROOT / "data/manifold/snapshots.parquet")
