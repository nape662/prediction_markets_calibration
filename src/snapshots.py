"""The price of every labeled Manifold market at fixed times before resolution.

python src/snapshots.py -> data/manifold/snapshots.parquet: id, anchor, horizon, prob, age_days, bettors, volume, resolution
A snapshot is probAfter of the last non-redemption bet that moved the price, at or before a moment in time.
before_resolution: that moment is resolution minus the horizon, so which moment a market gets depends on when its outcome arrived.
after_creation: that moment is creation plus the horizon, and the market must still be unresolved then, which traders can see at that moment.
A market with no such bet has no row at that horizon. age_days is how old that bet is at the snapshot.
bettors and volume count nonzero fills that had happened by the snapshot, so they can be filtered on without using the future.
"""
import bisect, json
from multiprocessing import Pool
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API = ROOT / "data/manifold/api"
HOURS = {"12h": 12, "1d": 24, "1w": 24 * 7, "1m": 24 * 30, "3m": 24 * 91, "6m": 24 * 182, "1y": 24 * 365}


def snapshots(market):
    bets = [b for b in json.load(open(API / "bets" / f"{market['id']}.json")) if not b.get("isRedemption")]
    moves = [b for b in bets if b["probBefore"] != b["probAfter"]]
    fills = sorted((f["timestamp"], abs(f["amount"]), b["userId"]) for b in bets for f in b.get("fills") or [dict(timestamp=b["createdTime"], amount=b["amount"])] if f["amount"] != 0)
    times, seen, volume, bettors = [f[0] for f in fills], set(), [], []
    for _, amount, user in fills:
        seen.add(user)
        volume.append((volume[-1] if volume else 0) + amount)
        bettors.append(len(seen))
    rows = []
    for name, hours in HOURS.items():
        for anchor, t in [("before_resolution", market["resolutionTime"] - hours * 3600e3), ("after_creation", market["createdTime"] + hours * 3600e3)]:
            before = [b for b in moves if b["createdTime"] <= t]
            if before and t < market["resolutionTime"]:
                n = bisect.bisect_right(times, t)
                rows.append(dict(id=market["id"], anchor=anchor, horizon=name, prob=before[-1]["probAfter"], age_days=(t - before[-1]["createdTime"]) / 86400e3,
                                 bettors=bettors[n - 1] if n else 0, volume=volume[n - 1] if n else 0.0, resolution=market["resolution"]))
    return rows


if __name__ == "__main__":
    ids = {json.loads(l)["id"] for l in open(ROOT / "labeling/results/full/manifold_final.jsonl")}
    markets = [m for m in map(json.loads, open(API / "markets.jsonl")) if m["id"] in ids]
    assert len(markets) == len(ids), (len(markets), len(ids))
    with Pool(8) as pool:
        rows = [r for market in pool.imap_unordered(snapshots, markets, chunksize=200) for r in market]
    pd.DataFrame(rows).to_parquet(ROOT / "data/manifold/snapshots.parquet")
