"""Fetch Manifold data via the public API (500 req/min limit).

python src/manifold_fetch.py markets          -> data/manifold/api/markets.jsonl (all resolved BINARY markets)
python src/manifold_fetch.py bets -> data/manifold/api/full.jsonl (full market incl. topics) and
                                     data/manifold/api/bets/<id>.json (all bets, ascending; non-sports only)
"""
import json, sys, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api.manifold.markets/v0/"
OUT = Path(__file__).resolve().parents[1] / "data/manifold/api"
MIN_BETTORS, MIN_VOLUME = 15, 1000
SPORTS = set("""sports nfl nba mlb nhl ncaa ncaaf ncaab soccer football basketball baseball hockey tennis golf
cricket rugby f1 formula motorsports nascar boxing ufc mma fighting uefa fifa premier premiere bundesliga laliga
seriea olympics superbowl bowl atp wta cycling wrestling darts snooker""".split())  # words in topic slugs
_lock, _next = threading.Lock(), [0.0]


def throttle():
    with _lock:
        _next[0] = max(_next[0] + 0.125, time.time())
        wait = _next[0] - time.time()
    time.sleep(max(wait, 0))


def get(endpoint, **params):
    url = API + endpoint + "?" + urllib.parse.urlencode(params)
    for attempt in range(8):
        throttle()
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


def bets_of(market_id):
    bets, after = [], None
    while True:
        params = dict(contractId=market_id, limit=1000, order="asc")
        if after:
            params["after"] = after
        page = get("bets", **params)
        bets += page
        if len(page) < 1000:
            return bets
        after = page[-1]["id"]


def is_sports(m):
    return any(SPORTS & set(slug.split("-")) for slug in m.get("groupSlugs") or [])


def fetch_one(market_id):
    m = get("market/" + market_id)
    if not is_sports(m):
        (OUT / "bets" / f"{market_id}.json").write_text(json.dumps(bets_of(market_id)))
    return m


def fetch_bets():
    (OUT / "bets").mkdir(exist_ok=True)
    full = OUT / "full.jsonl"
    done = {json.loads(l)["id"] for l in open(full)} if full.exists() else set()
    markets = [json.loads(l) for l in open(OUT / "markets.jsonl")]
    todo = [m["id"] for m in markets if m["id"] not in done and m["resolution"] in ("YES", "NO")
            and m["uniqueBettorCount"] >= MIN_BETTORS and m["volume"] >= MIN_VOLUME]
    with open(full, "a") as f, ThreadPoolExecutor(8) as pool:
        for i, m in enumerate(pool.map(fetch_one, todo)):
            f.write(json.dumps(m) + "\n")
            if i % 200 == 0:
                f.flush()
                print(f"{i}/{len(todo)}", flush=True)


if __name__ == "__main__":
    fetch_markets() if sys.argv[1] == "markets" else fetch_bets()
