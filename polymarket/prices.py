"""API prices for the labeled Polymarket markets, at fixed times after trading starts and before closing. Free, no Haiku. Run in a tmux session.

python polymarket/prices.py meta   -> polymarket/meta.csv: token, trading start, close and outcome per market, from the Gamma API
python polymarket/prices.py prices -> polymarket/snapshots.jsonl: one line per market with its price at each moment; safe to restart
The price at a moment is the last hourly point of the CLOB price history at or before it, looking back at most 3 days. What the API price measures is checked in polymarket/open_in_feb.py check.
"""
import json, sys, threading, time, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from open_in_feb import history

META, SNAPS = HERE / "meta.csv", HERE / "snapshots.jsonl"
DAY, LOOKBACK = 86400, 3 * 86400
HORIZONS = {"1d": 1, "1w": 7, "1m": 30}


def ts(s):
    return int(pd.Timestamp(s).timestamp())


def meta():
    ids = list(pd.read_csv(HERE / "cohorts.csv", dtype=str).id)
    rows = []
    for i in range(0, len(ids), 50):
        rows += fetch_batch(ids[i:i + 50])
        if i % 5000 == 0:
            print(i, len(rows), flush=True)
    found = {r["id"] for r in rows}
    assert len(found) == len(rows) and found <= set(ids), "duplicate or unexpected markets"
    print(f"{len(rows):,} of {len(ids):,} found")
    pd.DataFrame(rows).to_csv(META, index=False)


def fetch_batch(ids):
    url = "https://gamma-api.polymarket.com/markets?" + urllib.parse.urlencode([("id", x) for x in ids] + [("closed", "true"), ("limit", len(ids))])
    for wait in [2, 10, 60, None]:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "calibration-study"}), timeout=90) as r:
                got = json.load(r)
            break
        except OSError:
            if wait is None:
                raise
            time.sleep(wait)
    out = []
    for m in got:
        p = list(map(float, json.loads(m["outcomePrices"])))
        assert len(p) == 2 and max(p) >= .99, f"{m['id']} not resolved: {p}"  # some resolved markets store 0.9999992 instead of 1
        start = m.get("acceptingOrdersTimestamp") or m.get("startDate") or m["createdAt"]
        out.append(dict(id=m["id"], token=json.loads(m.get("clobTokenIds") or "[null]")[0], start=ts(start), close=ts(m["closedTime"]), y=int(p[0] > .5)))
    return out


def one(r):
    """Moments outside trading are skipped; moments 1d and 1w share one 8-day window."""
    out = dict(id=r.id)
    if pd.isna(r.token):  # old AMM markets have no CLOB price history
        return out
    for anchor, sign, base in [("after_start", 1, r.start), ("before_close", -1, r.close)]:
        moments = {h: base + sign * d * DAY for h, d in HORIZONS.items()}
        moments = {h: t for h, t in moments.items() if r.start < t < r.close}
        near = [t for h, t in moments.items() if h != "1m"]
        hist = history(r.token, min(near) - LOOKBACK, max(near)) if near else []
        if "1m" in moments:
            hist = hist + history(r.token, moments["1m"] - LOOKBACK, moments["1m"])
        for h, t in moments.items():
            before = [x for x in hist if t - LOOKBACK <= x["t"] <= t]
            last = max(before, key=lambda x: x["t"]) if before else None
            out[f"{anchor}_{h}"] = [t, last["p"], (t - last["t"]) / 3600] if last else [t, None, None]
    return out


def prices():
    d = pd.read_csv(META, dtype={"id": str, "token": str})
    done = {json.loads(l)["id"] for l in open(SNAPS)} if SNAPS.exists() else set()
    d = d[~d.id.isin(done)]
    print(f"{len(d):,} markets left", flush=True)
    lock = threading.Lock()
    with ThreadPoolExecutor(8) as ex, open(SNAPS, "a") as f:
        for n, out in enumerate(ex.map(one, d.itertuples()), 1):
            with lock:
                f.write(json.dumps(out) + "\n")
            if n % 1000 == 0:
                f.flush()
                print(f"{n:,} done", flush=True)


if __name__ == "__main__":
    {"meta": meta, "prices": prices}[sys.argv[1]]()
