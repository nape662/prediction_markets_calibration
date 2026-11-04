"""Markets open when Becker's trades end (2026-02-02) that closed by our API fetch (2026-10-31).

python polymarket/open_in_feb.py scan      -> markets.parquet: resolved Yes/No markets of this kind, with a printed funnel
python polymarket/open_in_feb.py activity  -> activity.parquet: takers and dollars per market by Feb 2, from Becker's trades
python polymarket/open_in_feb.py prices    -> snapshots.parquet: API price 30d, 7d and 1d before closing, for markets with $1,000 or 15 takers that the sieve leaves
python polymarket/open_in_feb.py check     -> compares API prices with Becker's trades on older markets, to see what the API price measures
"""
import json, sys, time, urllib.error, urllib.parse, urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import duckdb, numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import sieve

BECKER = ROOT / "data/becker/data/polymarket"
OUT = ROOT / "data/polymarket/open_in_feb"
END = datetime.fromisoformat("2026-02-02T18:27:46Z")  # last block in Becker's trades
HORIZONS = {"1m": 30, "1w": 7, "1d": 1}
WINDOW = 3 * 86400  # the API refuses hourly windows over about 15 days, so each moment gets its own short window
EXCHANGES = "('0xC5d563A36AE78145C45a50134d48A1215220f80a','0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E')"  # a fill with one of these as taker repeats fills already listed


def duck():
    c = duckdb.connect()
    c.sql(f"set memory_limit='6GB'; set threads=8; set temp_directory='{OUT}/duck'; set preserve_insertion_order=false")
    return c


def scan():
    rows, n = [], Counter()
    for line in open(ROOT / "data/polymarket/api/markets.jsonl"):
        m = json.loads(line)
        n["all markets"] += 1
        if not m.get("createdAt") or datetime.fromisoformat(m["createdAt"]) >= END:
            continue
        n["created before Feb 2"] += 1
        closed = m.get("closedTime")
        if not closed:
            n["  no closing time, so open at fetch"] += 1
            continue
        closed = datetime.fromisoformat(closed)
        if closed < END:
            n["  closed before Feb 2"] += 1
            continue
        n["  closed after Feb 2"] += 1
        if json.loads(m.get("outcomes") or "[]") != ["Yes", "No"]:
            continue
        n["    Yes/No"] += 1
        p = json.loads(m.get("outcomePrices") or "[]")
        y = 1 if p and float(p[0]) == 1 else 0 if p and float(p[1]) == 1 else None
        if y is None or not m.get("clobTokenIds"):
            continue
        n["    Yes/No and resolved"] += 1
        e = (m.get("events") or [{}])[0]
        desc = m.get("description") or ""
        game = m.get("sportsMarketType") or e.get("gameId")
        rows.append(dict(id=m["id"], question=m.get("question"), event_title=e.get("title"), event_id=e.get("id"),
                         series=e.get("seriesSlug") or ((e.get("series") or [{}])[0]).get("slug"), category=m.get("category"),
                         tags=" ".join(t.get("slug", "") for t in m.get("tags") or []), game=None if game is None else str(game),
                         description=desc if "polymarket.com/event" in desc or "data.polymarket" in desc else None,
                         tokens=m["clobTokenIds"], created=m["createdAt"], closed=m["closedTime"], end_date=m.get("endDate"),
                         volume_now=float(m.get("volumeNum") or 0), y=y))
    pd.DataFrame(rows).to_parquet(OUT / "markets.parquet", index=False)
    for k, v in n.items():
        print(f"{k:40s}{v:>10,d}")


def activity():
    m = pd.read_parquet(OUT / "markets.parquet", columns=["id", "tokens"])
    tok = pd.DataFrame([(t, i) for ts, i in zip(m.tokens.map(json.loads), m.id) for t in ts], columns=["token", "id"])
    c = duck()
    c.register("tok", tok)
    c.sql(f"""copy (with a as (select taker,maker_asset_id,taker_asset_id,maker_amount,taker_amount from '{BECKER}/trades/trades_*.parquet' where taker not in {EXCHANGES}),
        s as (select taker,taker_asset_id token,maker_amount usdc from a where maker_asset_id='0'
              union all select taker,maker_asset_id,taker_amount from a where taker_asset_id='0')
        select tok.id,count(distinct taker) takers,sum(usdc)/1e6 vol from s join tok using(token) group by tok.id) to '{OUT}/activity.parquet' (format parquet)""")
    a = pd.read_parquet(OUT / "activity.parquet")
    print(f"{len(m):,} markets, {len(a):,} with any trade by Feb 2, $1,000+ {(a.vol >= 1000).sum():,}, 15+ takers {(a.takers >= 15).sum():,}, either {((a.vol >= 1000) | (a.takers >= 15)).sum():,}, both {((a.vol >= 1000) & (a.takers >= 15)).sum():,}")


def history(token, start, end):
    url = "https://clob.polymarket.com/prices-history?" + urllib.parse.urlencode(dict(market=token, startTs=start, endTs=end, fidelity=60))
    for wait in [5, 30, 120, None]:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "calibration-study"}), timeout=60) as r:
                return json.load(r)["history"]
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500 or wait is None:
                raise
        except (urllib.error.URLError, TimeoutError):
            if wait is None:
                raise
        time.sleep(wait)


def prices():
    d = pd.read_parquet(OUT / "markets.parquet").merge(pd.read_parquet(OUT / "activity.parquet"), on="id", validate="1:1")
    d = d[(d.vol >= 1000) | (d.takers >= 15)].reset_index(drop=True)
    d["rule"] = None
    for rule, hit in sieve.rules(d, True).items():
        d.loc[hit & d.rule.isna(), "rule"] = rule
    print(f"$1,000 or 15 takers by Feb 2: {len(d):,}. Removed by the sieve: {d.rule.value_counts().to_dict()}", flush=True)
    d = d[d.rule.isna()]
    d.to_parquet(OUT / "kept.parquet", index=False)

    def one(r):
        out = []
        close = int(datetime.fromisoformat(r.closed).timestamp())
        for h, days in HORIZONS.items():
            t = close - days * 86400
            hist = [x for x in history(json.loads(r.tokens)[0], t - WINDOW, t) if x["t"] <= t]
            out.append(dict(id=r.id, horizon=h, moment=t, price=hist[-1]["p"] if hist else None, lag_h=(t - hist[-1]["t"]) / 3600 if hist else None))
        return out

    with ThreadPoolExecutor(4) as ex:
        rows = [x for got in ex.map(one, d.itertuples()) for x in got]
    s = pd.DataFrame(rows).merge(d[["id", "y", "question", "takers", "vol"]], on="id")
    s.to_parquet(OUT / "snapshots.parquet", index=False)
    s["after_feb"] = s.moment >= END.timestamp()
    for h, g in s.groupby("horizon"):
        p = g[g.price.notna()]
        print(f"{h}: {len(g):,} markets, {len(p):,} with an API price, {p.after_feb.sum():,} of those at a moment after Feb 2, mean price {p.price.mean():.3f}, YES {p.y.mean():.3f}, median lag {p.lag_h.median():.1f}h")


def check(n=150):
    """If the API price is the last trade, it can't change between two points with no fill between them, and it should equal the last fill."""
    c = duck()
    s = pd.read_parquet(ROOT / "data/yes_bias/pm_snap.parquet", columns=["id", "horizon", "takers", "created_at"])
    s = s[(s.horizon == "1w") & (s.takers >= 15)].sample(n, random_state=0)
    s["t"] = (pd.to_datetime(s.created_at, utc=True) + pd.Timedelta(days=7)).map(lambda x: int(x.timestamp()))
    tokens = c.sql(f"select id,clob_token_ids from '{BECKER}/markets/markets_*.parquet'").df()
    s = s.merge(tokens, on="id")
    c.register("ids", s[["id"]])
    fills = c.sql(f"""select t.id,epoch(t.ts) ts,t.yes,t.price p from '{ROOT}/data/yes_bias/pm_trades_t.parquet' t join ids using(id)
                      where t.taker not in {EXCHANGES} order by t.id,t.ts""").df()
    fills = {i: g for i, g in fills.groupby("id")}
    with ThreadPoolExecutor(4) as ex:
        hists = list(ex.map(lambda r: history(json.loads(r.clob_token_ids)[0], r.t - WINDOW, r.t), s.itertuples()))
    rows, pairs = [], []
    for r, hist in zip(s.itertuples(), hists):
        f = fills[r.id]
        every = f.ts.to_numpy()  # either token, any price: used to tell whether anything traded between two points
        y = f[f.yes == 1].groupby("ts").p.agg(["min", "max"])  # fills in one block have no usable order, so a whole block counts as the last trade
        ts, low, high = y.index.to_numpy(), y["min"].to_numpy(), y["max"].to_numpy()
        for a, b in zip(hist, hist[1:]):
            pairs.append((r.id, b["p"] != a["p"], np.searchsorted(every, b["t"], "right") == np.searchsorted(every, a["t"], "right")))
        for x in hist:
            i = np.searchsorted(ts, x["t"], "right") - 1
            if i >= 0:
                rows.append((r.id, x["p"], max(low[i] - x["p"], x["p"] - high[i], 0), (low[i] + high[i]) / 2))
    d = pd.DataFrame(rows, columns=["id", "api", "diff", "last_fill"])
    p = pd.DataFrame(pairs, columns=["id", "moved", "no_fill"])
    print(f"{d.id.nunique()} markets, {len(d):,} hourly points")
    print(f"API within 0.1 point of the last Yes fills: {(d['diff'] < .001).mean():.1%}. Median gap {d['diff'].median() * 100:.2f} points, 90th percentile {d['diff'].quantile(.9) * 100:.2f}")
    print(f"Pairs of hourly points with no fill between them: {p.no_fill.sum():,}. API price moved anyway in {p[p.no_fill].moved.mean():.1%}. With a fill: moved in {p[~p.no_fill].moved.mean():.1%}")
    half = lambda x: ((x * 1000).round() % 10 == 5).mean()
    print(f"Share on a half cent: API {half(d.api):.1%}, Yes fills {half(pd.concat(fills.values()).query('yes == 1').p):.1%}")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    globals()[sys.argv[1]]()
