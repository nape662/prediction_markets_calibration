"""Fetch Manifold data via the public API (500 req/min limit).

python src/manifold_fetch.py markets          -> data/manifold/api/markets.jsonl (all resolved BINARY markets)
python src/manifold_fetch.py bets [min_bettors] -> data/manifold/api/bets/<id>.json (all bets, ascending)
"""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

API = "https://api.manifold.markets/v0/"
OUT = Path(__file__).resolve().parents[1] / "data/manifold/api"


def get(endpoint, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(8):
        time.sleep(0.13)
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2**attempt)
    raise RuntimeError(f"giving up on {url}")


def fetch_markets():
    OUT.mkdir(parents=True, exist_ok=True)
    seen, before = set(), None
    with open(OUT / "markets.jsonl", "w") as f:
        while True:
            params = dict(sort="newest", filter="resolved", contractType="BINARY", limit=1000)
            if before:
                params["beforeTime"] = before
            page = get("search-markets", **params)
            new = [m for m in page if m["id"] not in seen]
            if not new:
                break
            for m in new:
                seen.add(m["id"])
                f.write(json.dumps(m) + "\n")
            before = page[-1]["createdTime"] + 1
            print(len(seen), time.strftime("%Y-%m-%d", time.gmtime(before / 1000)), flush=True)


def fetch_bets(min_bettors):
    (OUT / "bets").mkdir(exist_ok=True)
    markets = [json.loads(l) for l in open(OUT / "markets.jsonl")]
    todo = [m for m in markets if m["uniqueBettorCount"] >= min_bettors and m["resolution"] in ("YES", "NO")]
    for i, m in enumerate(todo):
        path = OUT / "bets" / f"{m['id']}.json"
        if path.exists():
            continue
        bets, after = [], None
        while True:
            params = dict(contractId=m["id"], limit=1000, order="asc")
            if after:
                params["after"] = after
            page = get("bets", **params)
            bets += page
            if len(page) < 1000:
                break
            after = page[-1]["id"]
        path.write_text(json.dumps(bets))
        if i % 100 == 0:
            print(f"{i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    fetch_markets() if sys.argv[1] == "markets" else fetch_bets(int(sys.argv[2]) if len(sys.argv) > 2 else 1)
