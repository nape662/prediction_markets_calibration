"""The price of every option of every Manifold multiple-choice market at fixed times, like src/snapshots.py for binary markets.

python manifold_mc/snapshots.py -> data/manifold_mc/snapshots.parquet, one row per option, anchor and horizon
Each option is its own YES/NO forecast. Outcome y: in one-winner markets 1 for the winning option and 0 for the others;
in independent-option markets the option's own YES or NO. Options resolved N/A or to a split probability are dropped,
the rest of their market stays. One-winner markets resolved to a split (MKT) are dropped whole: the API doesn't say which
options got what share. The "Other" option is dropped.
Price: probAfter of the last bet that moved this option's price, at or before the moment. In one-winner markets a bet
on one option moves the others; those moves are the zero-share redemptions, so they count as moves too.
before_resolution: the option's resolution time minus the horizon (in independent markets each option resolves on its own).
after_creation: market creation plus the horizon; the option must be unresolved then.
An option must exist at the moment (initial: created within a minute of the market) and have a price move by then.
bettors/volume count the market's nonzero fills by the moment; opt_bettors/opt_volume only those on this option.
"""
import bisect, gzip, json
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/manifold_mc"
HOURS = {"12h": 12, "1d": 24, "1w": 24 * 7, "1m": 24 * 30, "1y": 24 * 365}


def counts(fills):
    """Times, and the number of distinct users and the summed volume up to each time."""
    fills.sort()
    seen, volume, bettors = set(), [], []
    for _, amount, user in fills:
        seen.add(user)
        volume.append((volume[-1] if volume else 0) + amount)
        bettors.append(len(seen))
    return [f[0] for f in fills], bettors, volume


def at(series, t):
    times, bettors, volume = series
    n = bisect.bisect_right(times, t)
    return (bettors[n - 1], volume[n - 1]) if n else (0, 0.0)


def outcome(market, answer):
    if not market["shouldAnswersSumToOne"]:
        return {"YES": 1, "NO": 0}.get(answer.get("resolution")), answer.get("resolutionTime")
    if market["resolution"] == "MKT":  # a split; the API doesn't say how it was split, so no option of the market is usable
        assert "resolutions" not in market and all(a.get("resolution") is None for a in market["answers"]), market["id"]
        return None, None
    return int(market["resolution"] == answer["id"]), market["resolutionTime"]


def snapshots(market):
    bets = json.load(gzip.open(DATA / "bets" / f"{market['id']}.json.gz"))
    moves, fills, market_fills = defaultdict(list), defaultdict(list), []
    for b in bets:
        if b["probBefore"] != b["probAfter"]:
            moves[b["answerId"]].append((b["createdTime"], b["probAfter"]))
        if not b.get("isRedemption"):
            for f in b.get("fills") or [dict(timestamp=b["createdTime"], amount=b["amount"])]:
                if f["amount"] != 0:
                    fills[b["answerId"]].append((f["timestamp"], abs(f["amount"]), b["userId"]))
                    market_fills.append((f["timestamp"], abs(f["amount"]), b["userId"]))
    whole = counts(market_fills)
    rows = []
    for a in market["answers"]:
        y, resolved = outcome(market, a)
        if a.get("isOther") or y is None:
            continue
        own, history = counts(fills[a["id"]]), sorted(moves[a["id"]])
        for name, hours in HOURS.items():
            for anchor, t in [("before_resolution", resolved - hours * 3600e3), ("after_creation", market["createdTime"] + hours * 3600e3)]:
                n = bisect.bisect_right(history, (t, 2.0))
                if n and a["createdTime"] <= t < resolved:
                    (bettors, volume), (opt_bettors, opt_volume) = at(whole, t), at(own, t)
                    rows.append(dict(id=market["id"], answer=a["id"], anchor=anchor, horizon=name, prob=history[n - 1][1],
                                     age_days=(t - history[n - 1][0]) / 86400e3, y=y, bettors=bettors, volume=volume,
                                     opt_bettors=opt_bettors, opt_volume=opt_volume, initial=a["createdTime"] - market["createdTime"] <= 60e3,
                                     one_winner=market["shouldAnswersSumToOne"], add_mode=market["addAnswersMode"], creator=market["creatorId"]))
    return rows


if __name__ == "__main__":
    markets = list(map(json.loads, open(DATA / "full.jsonl")))
    with Pool(6, maxtasksperchild=50) as pool:  # one market's bets can take 2 GB; a fresh worker gives the memory back
        rows = [r for market in pool.imap_unordered(snapshots, markets) for r in market]
    pd.DataFrame(rows).to_parquet(DATA / "snapshots.parquet")
