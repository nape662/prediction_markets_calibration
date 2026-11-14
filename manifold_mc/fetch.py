"""Fetch resolved Manifold multiple-choice markets via the public API (500 req/min limit).

python manifold_mc/fetch.py list -> data/manifold_mc/markets.jsonl: every resolved MULTIPLE_CHOICE market (search results, no options)
python manifold_mc/fetch.py bets -> data/manifold_mc/full.jsonl: full market with its options, for markets passing the binary gate
                                    data/manifold_mc/bets/<id>.json.gz: all bets, ascending, with the zero-share redemptions that record
                                    how a bet on one option moved the others. Safe to restart.
"""
import gzip, json, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "manifold")]
from manifold_fetch import MIN_BETTORS, MIN_VOLUME, get

OUT = ROOT / "data/manifold_mc"


def fetch_list():
    OUT.mkdir(parents=True, exist_ok=True)
    seen, before = set(), None
    with open(OUT / "markets.jsonl", "w") as f:
        while True:
            page = get("search-markets", sort="newest", filter="resolved", contractType="MULTIPLE_CHOICE", limit=1000, **({"beforeTime": before} if before else {}))
            new = [m for m in page if m["id"] not in seen]
            if not new:
                break
            seen.update(m["id"] for m in new)
            f.writelines(json.dumps(m) + "\n" for m in new)
            before = page[-1]["createdTime"] + 1
            print(len(seen), flush=True)


def bets_of(market_id):
    bets, after = [], None
    while True:
        page = get("bets", contractId=market_id, limit=1000, order="asc", filterRedemptions="false", includeZeroShareRedemptions="true", **({"after": after} if after else {}))
        bets += page
        if len(page) < 1000:
            return bets
        after = page[-1]["id"]


def fetch_one(market_id):
    path = OUT / "bets" / f"{market_id}.json.gz"
    if not path.exists():
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(gzip.compress(json.dumps(bets_of(market_id)).encode()))
        tmp.rename(path)  # a kill mid-write leaves only the .tmp, which is redone
    return get("market/" + market_id)


def fetch_bets():
    (OUT / "bets").mkdir(exist_ok=True)
    full = OUT / "full.jsonl"
    done = {json.loads(l)["id"] for l in open(full)} if full.exists() else set()
    todo = [m["id"] for m in map(json.loads, open(OUT / "markets.jsonl"))
            if m["id"] not in done and m["resolution"] != "CANCEL" and m["uniqueBettorCount"] >= MIN_BETTORS and m["volume"] >= MIN_VOLUME]
    with open(full, "a") as f, ThreadPoolExecutor(24) as pool:
        for i, m in enumerate(pool.map(fetch_one, todo)):
            f.write(json.dumps(m) + "\n")
            if i % 200 == 0:
                f.flush()
                print(f"{i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    fetch_list() if sys.argv[1] == "list" else fetch_bets()
