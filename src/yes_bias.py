"""Why world markets sit below the diagonal: every check behind notes/yes_bias_debug.md. Run in a tmux session.

python src/yes_bias.py unresolved -> data/yes_bias/unresolved.jsonl: markets still open or closed without resolution, which the main fetch skips
python src/yes_bias.py moves      -> data/yes_bias/moves.parquet: every price-moving bet with the trader's earlier bet count
python src/yes_bias.py polymarket -> data/yes_bias/pm_*.parquet: Polymarket trades and snapshots from Becker data; pm_snapshots redoes only the snapshots
python src/yes_bias.py analyze    -> plots/yes_bias/metrics.csv, bins.csv, before_deadline.csv; src/yes_bias_plots.py draws them
Shift is the log-odds added to every price that makes the group's mean price equal its YES rate; 0 is calibrated, -0.5 means YES odds overstated 1.65 times.
Hand labels in labeling/review/yes_bias/ were made seeing titles only (polarity, pairs); the resolution audit necessarily saw outcomes.
"""
import calendar, hashlib, json, re, sys, time, urllib.parse, urllib.request
from multiprocessing import Pool
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import minimize_scalar
from sklearn.feature_extraction.text import TfidfVectorizer
from plot_calibration import ROOT, load

OUT, DATA, HAND = ROOT / "plots/yes_bias", ROOT / "data/yes_bias", ROOT / "labeling/review/yes_bias"
API = ROOT / "data/manifold/api"
COLLECTED, HOURS = pd.Timestamp("2026-10-30"), {"1d": 24, "1w": 168, "1m": 720}
RESAMPLES, TOLERANCE, SIMILAR = 500, 1e-3, .42
MON = "jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec"
NEG = re.compile(r"\b(still|remain|remains|stay|stays|continue|continues|survive|survives|keep|keeps|maintain|alive|retain|retains|hold on|not|no|never|won't|without|fail|fails|avoid|avoids|last through|complete (?:his|her|their) term|finish (?:his|her|their) term)\b", re.I)
PERSIST = re.compile(r"\b(still|remain|remains|stay|stays|continue|continues|survive|survives|alive|retain|retains)\b", re.I)
BY = re.compile(rf"\b(by|before|until|within)\b[^?]*\b({MON}|q[1-4]|20\d\d|eoy|year|month|week|end of|\d{{1,2}}(st|nd|rd|th)?\b)", re.I)
ANYDATE = re.compile(rf"\b(by|before|until|through|in|during|within)\b[^?]*\b({MON}|q[1-4]|20\d\d|eoy|year|month|week|end of)", re.I)
MARGIN = re.compile(r"\b(win|wins|lead|leads)\b[^?]*\bby\b|\bby \d{1,2}(\b|[-–.%+])|\bmargin\b", re.I)
logit = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))


def kind(q):
    """The same text rule for both platforms, no model involved."""
    if PERSIST.search(q):
        return "still_or_remain"
    if BY.search(q) and not NEG.search(q) and not MARGIN.search(q):
        return "by_date"
    return "no_date" if not ANYDATE.search(q) and not NEG.search(q) else "other"


def deadline(q, created):
    """The deadline written in a title and whether it is unambiguous. "by 2025" and "by March" could mean the start or the end of the period, so they count as unclear."""
    q, c = q.lower(), pd.Timestamp(created, unit="ms")
    months = {m: i + 1 for i, m in enumerate(MON.split("|"))}
    m = re.search(rf"\b(by|before|until|through|on|at|end of)\s+(?:the\s+)?(?:end\s+of\s+)?({MON})[a-z]*\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(20[2-3]\d))?", q)
    if m and 1 <= int(m[3]) <= calendar.monthrange(2024, months[m[2]])[1]:  # a leap year, so February 29 parses
        day = min(int(m[3]), calendar.monthrange(int(m[4]) if m[4] else c.year, months[m[2]])[1])
        year = int(m[4]) if m[4] else c.year + (pd.Timestamp(c.year, months[m[2]], day) < c)
        return pd.Timestamp(year, months[m[2]], min(day, calendar.monthrange(year, months[m[2]])[1])), True
    m = re.search(r"\b(before)\s+(?:the\s+end\s+of\s+)?(20[2-3]\d)\b", q)
    if m:
        return pd.Timestamp(int(m[2]), 12, 31) if "end of" in m[0] else pd.Timestamp(int(m[2]), 1, 1), True
    m = re.search(r"\b(in|during|through|end of|eoy)\s+(?:the\s+)?(?:end\s+of\s+)?(20[2-3]\d)\b", q)
    if m:
        return pd.Timestamp(int(m[2]), 12, 31), True
    m = re.search(rf"\b(by|before|until|through|in|during|end of|of)\s+(?:the\s+)?(?:end\s+of\s+)?(?:({MON})[a-z]*\.?\s+)?(20[2-3]\d)\b", q)
    if m:
        return (pd.Timestamp(int(m[3]), months[m[2]], 1) + pd.offsets.MonthEnd(0) if m[2] else pd.Timestamp(int(m[3]), 12, 31)), False
    m = re.search(rf"\b(by|before|until|through|in|end of)\s+(?:the\s+)?(?:end\s+of\s+)?({MON})[a-z]*\b", q)
    if m:
        return pd.Timestamp(c.year + (months[m[2]] < c.month), months[m[2]], 1) + pd.offsets.MonthEnd(0), False
    return pd.NaT, False


def wshift(x, y, w):
    return minimize_scalar(lambda a: -np.sum(w * (y * (a + x) - np.log1p(np.exp(a + x)))), bounds=(-4, 4), method="bounded", options=dict(xatol=TOLERANCE)).x


def summary(g, by="creator", seed=0):
    x, y = logit(g.prob.to_numpy()), g.y.to_numpy()
    w = g.w.to_numpy() if "w" in g else np.ones(len(g))  # optional per-market weights
    c = pd.factorize(g[by])[0]
    rng = np.random.default_rng(seed)
    draws = [wshift(x, y, w * np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c]) for _ in range(RESAMPLES)]
    low, high = np.percentile(draws, [2.5, 97.5])
    price, yes = np.average(g.prob, weights=w), np.average(y, weights=w)
    return dict(n=len(g), price=price, yes=yes, gap=price - yes, shift=wshift(x, y, w), low=low, high=high)


def fetch_unresolved():
    DATA.mkdir(exist_ok=True)
    seen = set()
    with open(DATA / "unresolved.jsonl", "w") as f:
        for status in ["open", "closed"]:
            before = None
            while True:
                params = dict(sort="newest", filter=status, contractType="BINARY", limit=1000) | (dict(beforeTime=before) if before else {})
                page = json.load(urllib.request.urlopen("https://api.manifold.markets/v0/search-markets?" + urllib.parse.urlencode(params), timeout=60))
                new = [m for m in page if m["id"] not in seen]
                if not new:
                    break
                for m in new:
                    seen.add(m["id"])
                    f.write(json.dumps(m) + "\n")
                before = page[-1]["createdTime"] + 1
                time.sleep(.2)


def market_moves(i):
    return [(i, b["userId"], b["createdTime"], b["probBefore"], b["probAfter"]) for b in json.load(open(API / "bets" / f"{i}.json")) if not b.get("isRedemption") and b["probBefore"] != b["probAfter"]]


def build_moves():
    ids = [json.loads(l)["id"] for l in open(ROOT / "labeling/results/full/manifold_final.jsonl")]
    with Pool(10) as pool:
        rows = [r for m in pool.imap_unordered(market_moves, ids, chunksize=200) for r in m]
    d = pd.DataFrame(rows, columns=["id", "user", "t", "pb", "pa"]).sort_values("t")
    d["prior"] = d.groupby("user").cumcount()
    d["dl"] = logit(d.pa) - logit(d.pb)
    d.to_parquet(DATA / "moves.parquet")


def polymarket():
    c = duckdb.connect()
    c.sql(f"set memory_limit='7GB'; set threads=8; set temp_directory='{DATA}/duck'; set preserve_insertion_order=false")
    b = ROOT / "data/becker/data/polymarket"
    m = c.sql(f"""select m.id,question,outcome_prices,clob_token_ids,volume,end_date,created_at,g."group" as grp,g.topic from '{b}/markets/markets_*.parquet' m join '{ROOT}/data/categories/polymarket.parquet' g using(id)
                  where closed and outcomes='["Yes", "No"]' and (g.function='world' or g.function is null) and volume>=1000""").df()
    prices = m.outcome_prices.map(json.loads).map(lambda x: (float(x[0]), float(x[1])))
    m["y"] = [1. if a == 1 else 0. if n == 1 else np.nan for a, n in prices]
    m = m[m.y.notna() & m.clob_token_ids.notna() & ~m.question.str.lower().str.contains(r"\bsay\b|mention|tweet|\bpost\b|o/u|over/under|up or down|temperature|spread:")].copy()
    tokens = m.clob_token_ids.map(json.loads)
    tok = pd.DataFrame([(t[0], i, 1) for t, i in zip(tokens, m.id)] + [(t[1], i, 0) for t, i in zip(tokens, m.id)], columns=["token", "id", "yes"])
    m.drop(columns=["clob_token_ids", "outcome_prices"]).to_parquet(DATA / "pm_markets.parquet")
    c.register("tok", tok)
    c.sql(f"""copy (with a as (select block_number,maker,taker,maker_asset_id,taker_asset_id,maker_amount,taker_amount from '{b}/trades/trades_*.parquet'),
        s as (select block_number,taker,maker,taker_asset_id token,maker_amount*1.0/nullif(taker_amount,0) price,maker_amount usdc from a where maker_asset_id='0'
              union all select block_number,taker,maker,maker_asset_id,taker_amount*1.0/nullif(maker_amount,0),taker_amount from a where taker_asset_id='0'),
        t as (select s.block_number,taker,maker,price,usdc,tok.id,tok.yes from s join tok using(token))
        select t.*, try_cast(b.timestamp as timestamptz) ts from t join '{b}/blocks/blocks_*.parquet' b using(block_number)) to '{DATA}/pm_trades_t.parquet' (format parquet)""")
    pm_snapshots()


def pm_snapshots():
    """Fills in one block have no usable order here, so the price is their volume-weighted mean. Volume at the snapshot is kept so the lifetime $1,000 gate can be met without the future."""
    c = duckdb.connect()
    c.sql(f"set memory_limit='7GB'; set threads=8; set temp_directory='{DATA}/duck'; set preserve_insertion_order=false")
    m = pd.read_parquet(DATA / "pm_markets.parquet")
    c.register("mk", m[["id", "created_at", "end_date"]])
    rows = []
    for h, hs in HOURS.items():
        rows.append(c.sql(f"""with f as (select t.id,t.ts,t.usdc,t.taker,case when t.yes=1 then t.price else 1-t.price end p from '{DATA}/pm_trades_t.parquet' t join mk using(id)
                                         where t.price between .001 and .999 and t.ts<=mk.created_at+interval {hs} hour and mk.end_date>mk.created_at+interval {hs} hour),
                                  l as (select id,max(ts) last_ts,count(distinct taker) takers,sum(usdc)/1e6 vol from f group by id)
                              select f.id,'{h}' horizon,sum(f.p*f.usdc)/sum(f.usdc) prob,any_value(l.takers) takers,any_value(l.vol) vol from f join l on f.id=l.id and f.ts=l.last_ts group by f.id""").df())
    pd.concat(rows).merge(m, on="id").to_parquet(DATA / "pm_snap.parquet")


def status_quo_labels():
    jev = {c["ids"][0]: c["probs"]["status_quo_default"] for c in map(json.loads, open(ROOT / "labeling/results/full/manifold_jev.jsonl"))}
    haiku = {}
    for name in ["manifold_haiku.jsonl", "manifold_haiku_back.jsonl"]:
        for line in open(ROOT / "labeling/results/full" / name):
            try:
                r = json.loads(json.loads(line)["result"])
            except (json.JSONDecodeError, KeyError):  # an invalid model answer is left unlabeled, as in the merge
                continue
            haiku[r["id"]] = "yes" if "status_quo_default" in r.get("yes", []) else "unsure" if "status_quo_default" in r.get("unsure", []) else "no"
    return jev, haiku


def data(min_bettors=15):
    jev, haiku = status_quo_labels()
    markets = {m["id"]: m for m in map(json.loads, open(API / "markets.jsonl"))}
    a = load()
    a = a[(a.bettors >= min_bettors) & (a.anchor == "after_creation") & a.horizon.isin(HOURS)].copy()
    a["question"] = a.id.map(lambda i: markets[i]["question"])
    for col in ["createdTime", "closeTime", "resolutionTime"]:
        a[col] = a.id.map(lambda i: markets[i][col])
    a["year"] = pd.to_datetime(a.createdTime, unit="ms").dt.year
    a["t"] = a.createdTime + a.horizon.map(HOURS) * 3600e3
    a["haiku"], a["jev"] = a.id.map(haiku), a.id.map(jev)
    a["neg"] = a.question.map(lambda q: bool(NEG.search(q)))
    a["kind"] = a.question.map(kind)
    dates = {i: deadline(q, c) for i, q, c in a[["id", "question", "createdTime"]].drop_duplicates("id").itertuples(index=False)}
    a["deadline"] = pd.to_datetime(a.id.map(lambda i: dates[i][0]))
    a["clear"] = a.id.map(lambda i: dates[i][1])
    hand = pd.read_csv(HAND / "polarity_hand.csv")
    a["yes_default"] = a.id.isin(hand[hand.yes_default].id)
    a["event"] = (a.haiku == "yes") & ~a.neg
    a["fixed"] = (a.haiku == "no") & (a.jev < .2)
    a["passed"] = a.deadline < COLLECTED - pd.Timedelta(days=60)
    return a


def before_deadline(moves):
    """Prices at fixed times before the deadline written in the title, which doesn't depend on the outcome. 15 people must have moved the price by that moment, and the market must still be open."""
    u = data(min_bettors=0)
    u = u[(u.group == "world") & u.passed].drop_duplicates("id")
    u = u[u.event | u.yes_default]
    rows = []
    g = {i: x for i, x in moves[moves.id.isin(u.id)].groupby("id")}
    for r in u.itertuples():
        x, end = g.get(r.id), r.deadline.timestamp() * 1e3
        if x is None:
            continue
        seen = pd.Series(pd.factorize(x.user)[0]).cummax().to_numpy() + 1
        for name, days in [("1y", 365), ("6m", 182), ("3m", 91), ("1m", 30), ("2w", 14), ("1w", 7), ("3d", 3), ("1d", 1)]:
            t = end - days * 86400e3
            i = np.searchsorted(x.t.values, t, side="right") - 1
            if r.createdTime < t < min(r.resolutionTime, r.closeTime) and i >= 0 and seen[i] >= 15:
                rows.append(dict(id=r.id, before=name, prob=x.pa.values[i], y=r.y, creator=r.creator, clear=r.clear, side="YES means no change" if r.yes_default else "nothing happening means NO"))
    return pd.DataFrame(rows)


def similar_titles(mf, pm):
    """Is a similar title already open on the other platform at the snapshot? Pools are raw market lists: no gate on later outcome, resolution or volume."""
    b = ROOT / "data/becker/data/polymarket"
    pool_pm = duckdb.sql(f"""select m.id,question,created_at,end_date from '{b}/markets/markets_*.parquet' m join '{ROOT}/data/categories/polymarket.parquet' g using(id) where (g.function='world' or g.function is null) and created_at is not null and end_date is not null""").df()
    pool_pm["start"] = pd.to_datetime(pool_pm.created_at, utc=True).map(lambda x: x.timestamp() * 1e3)
    pool_pm["end"] = pd.to_datetime(pool_pm.end_date, utc=True).map(lambda x: x.timestamp() * 1e3)
    every = [json.loads(l) for name in [API / "markets.jsonl", DATA / "unresolved.jsonl"] for l in open(name)]
    pool_mf = pd.DataFrame([dict(id=m["id"], question=m["question"], start=m["createdTime"], end=m.get("resolutionTime") or 4e12) for m in every]).drop_duplicates("id")
    clean = lambda t: t.fillna("").str.lower().str.replace(r"\[.*?\]", "", regex=True).str.replace(r"[^a-z0-9 ]", " ", regex=True)
    vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words="english", min_df=2).fit(pd.concat([clean(pool_pm.question), clean(pool_mf.question)]))
    def match(rows, pool):
        sim = (vec.transform(clean(rows.question)) @ vec.transform(clean(pool.question)).T).tocsr()
        sim.data[sim.data < SIMILAR] = 0
        sim.eliminate_zeros()
        start, end, t = pool.start.to_numpy(), pool.end.to_numpy(), rows.t.to_numpy()
        return [bool(((start[sim[i].indices] <= t[i]) & (end[sim[i].indices] > t[i])).any()) for i in range(sim.shape[0])]
    return match(mf, pool_pm), match(pm, pool_mf)


def pairs(moves, resolved):
    """Hand-verified same-event pairs, priced at the same moment: a fixed time after both markets exist."""
    p = pd.read_csv(HAND / "pairs_hand.csv")
    pm = pd.read_parquet(DATA / "pm_markets.parquet").set_index("id")
    c = duckdb.connect()
    c.sql("set memory_limit='6GB'")
    c.register("ids", p[["pm_id"]].drop_duplicates().astype({"pm_id": str}))
    t = c.sql(f"select t.id pm_id,t.ts,t.yes,t.price,t.usdc from '{DATA}/pm_trades_t.parquet' t join ids on t.id=ids.pm_id where t.price between .001 and .999 order by t.ts").df()
    t["p"] = np.where(t.yes == 1, t.price, 1 - t.price)
    t["ms"] = (pd.to_datetime(t.ts, utc=True) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds() * 1e3
    t["pu"] = t.p * t.usdc
    t = t.groupby(["pm_id", "ms"], as_index=False).agg(pu=("pu", "sum"), usdc=("usdc", "sum"), fills=("p", "size"))  # fills in one block have no usable order
    t["p"], t["n"] = t.pu / t.usdc, t.groupby("pm_id").fills.cumsum()
    gm, gt, rows = dict(tuple(moves[moves.id.isin(p.mf_id)].groupby("id"))), dict(tuple(t.groupby("pm_id"))), []
    for x in p[p.same_rules].astype({"pm_id": str}).itertuples():
        if x.mf_id not in gm or x.pm_id not in gt:
            continue
        a, b, r = gm[x.mf_id], gt[x.pm_id], resolved[x.mf_id]
        for name, days in [("1w", 7), ("2w", 14), ("1m", 30), ("3m", 90)]:
            when = max(r["createdTime"], b.ms.iloc[0]) + days * 86400e3
            i, j = np.searchsorted(a.t.values, when, side="right") - 1, np.searchsorted(b.ms.values, when, side="right") - 1
            if when < r["resolutionTime"] and when < pd.Timestamp(pm.end_date[x.pm_id]).timestamp() * 1e3 and i >= 0 and j >= 0 and b.n.values[j] >= 5 and when - b.ms.values[j] <= 7 * 86400e3:
                rows.append(dict(mf=x.mf_id, pm=x.pm_id, kind=x.kind, copied=x.copied, horizon=name, manifold=a.pa.values[i], polymarket=b.p.values[j], y=float(r["resolution"] == "YES"), y_pm=float(pm.y[x.pm_id])))
    return pd.DataFrame(rows)


def analyze():
    OUT.mkdir(exist_ok=True)
    a = data()
    w = a[a.group == "world"]
    moves = pd.read_parquet(DATA / "moves.parquet")
    metrics, bins = [], []
    add = lambda check, g, by="creator", **extra: metrics.append(dict(check=check, by=by, **extra, **summary(g, by)))
    for h in HOURS:
        x = w[w.horizon == h]
        add("world", x, horizon=h)
        add("old label: status quo", x[x.quo], horizon=h)
        add("old label: other world", x[~x.quo], horizon=h)
        for name, f in [("nothing happening means NO", x.event), ("YES means no change, hand labels", x.yes_default)]:
            add(name, x[f], horizon=h)
            add(f"{name}: no title date", x[f & x.deadline.isna()], horizon=h)
            add(f"{name}: title date", x[f & x.deadline.notna()], horizon=h)
            add(f"{name}: title date passed", x[f & x.passed], horizon=h)
        add("regex still or not, hand said not YES default", x[x.neg & ~x.yes_default], horizon=h)
        add("both labels no default", x[x.fixed], horizon=h)
        add("both labels no default, no title date", x[x.fixed & x.deadline.isna()], horizon=h)
        for k, g in x.groupby("kind"):
            add(f"text rule only: {k}", g, horizon=h)
    coin = a[(a.horizon == "1d") & (a.group == "fixed_chance")]
    add("placebo: fixed_chance", coin, horizon="1d")
    x = a[a.horizon == "1w"]
    for group, g in x[x.group != "world"].groupby("group"):
        add(f"placebo: {group}", g, horizon="1w")
    tr = x[x.group == "traded_elsewhere"]
    add("placebo: traded_elsewhere, by date", tr[tr.event], horizon="1w")
    add("placebo: traded_elsewhere, not by date", tr[tr.haiku == "no"], horizon="1w")

    w1 = w[w.horizon == "1w"].copy()
    ev = w1[w1.event]
    last = moves[moves.id.isin(w1.id)].merge(w1[["id", "t"]], on="id", suffixes=("", "_snap"))
    last = last[last.t <= last.t_snap].sort_values(["id", "t"])
    pb, day = last.groupby("id").pb.last(), last[last.t >= last.t_snap - 86400e3].groupby("id").pa.mean()
    add("artifact: drop closed but unresolved", w1[w1.t < w1.closeTime], horizon="1w")
    add("artifact: price before the last move", w1.assign(prob=w1.id.map(pb)), horizon="1w")
    add("artifact: mean price over the last 24h", w1[w1.id.isin(day.index)].assign(prob=w1.id.map(day)), horizon="1w")
    add("artifact: traded in the last 24h, last price", w1[w1.id.isin(day.index)], horizon="1w")
    add("artifact: 1000+ mana by the snapshot, so the fetch gate needs no future", w1[w1.volume >= 1000], horizon="1w")
    add("artifact: 2000+ mana by the snapshot", w1[w1.volume >= 2000], horizon="1w")
    add("artifact: created before 2025", w1[w1.year < 2025], horizon="1w")
    first = moves.sort_values("t").groupby("id").pb.first()
    add("start price: 50%", ev[ev.id.map(first).between(.49, .51)], horizon="1w")
    add("start price: below 40%", ev[ev.id.map(first) < .4], horizon="1w")
    hand_half = w1.creator.map(lambda c: hash_half(c))
    for half in [0, 1]:
        add(f"holdout creators {half}: YES means status quo", w1[w1.yes_default & (hand_half == half)], horizon="1w")
        add(f"holdout creators {half}: by date", w1[w1.event & (hand_half == half)], horizon="1w")
        add(f"holdout creators {half}: both no, no date", w1[w1.fixed & w1.deadline.isna() & (hand_half == half)], horizon="1w")
    add("by date, resampling deadline months", ev.assign(month=ev.deadline.dt.to_period("M").astype(str)), by="month", horizon="1w")
    for year, g in ev.groupby("year"):
        add(f"nothing means NO, created {year}: all", g, horizon="1w")
        add(f"nothing means NO, created {year}: no title date", g[g.deadline.isna()], horizon="1w")
        add(f"nothing means NO, created {year}: title date", g[g.deadline.notna()], horizon="1w")
        if g.passed.sum() >= 30:
            add(f"nothing means NO, created {year}: title date passed", g[g.passed], horizon="1w")
    for low, high in [(0, 2e3), (2e3, 5e3), (5e3, 2e4), (2e4, 1e9)]:
        add(f"nothing means NO, volume {low:.0f} to {high:.0f}", ev[ev.volume.between(low, high, inclusive="left")], horizon="1w")
    full = {m["id"]: m for m in map(json.loads, open(API / "full.jsonl"))}
    tagged = w1.id.map(lambda i: any("new-year" in t for t in full[i].get("groupSlugs") or []))
    around = pd.to_datetime(w1.resolutionTime, unit="ms").between("2023-12-15", "2024-02-15")
    add("New Year tag: tagged, resolved around that New Year", w1[tagged & around], horizon="1w")
    add("New Year tag: untagged, resolved around that New Year", w1[~tagged & around], horizon="1w")
    add("New Year tag: world without tagged markets", w1[~tagged], horizon="1w")
    train, test = ev[ev.year <= 2023], ev[ev.year >= 2024]
    fitted = wshift(logit(train.prob.to_numpy()), train.y.to_numpy(), np.ones(len(train)))
    moved_p = 1 / (1 + np.exp(-(logit(test.prob) + fitted)))
    loss = lambda p, y: -np.mean(y * np.log(np.clip(p, .001, .999)) + (1 - y) * np.log(1 - np.clip(p, .001, .999)))
    metrics.append(dict(check="shift fitted to 2023 and earlier, tested from 2024: Brier and log loss, raw", by="", horizon="1w", n=len(test), shift=fitted, price=((test.prob - test.y) ** 2).mean(), yes=loss(test.prob, test.y)))
    metrics.append(dict(check="shift fitted to 2023 and earlier, tested from 2024: Brier and log loss, shifted", by="", horizon="1w", n=len(test), shift=fitted, price=((moved_p - test.y) ** 2).mean(), yes=loss(moved_p, test.y)))

    total = (w1.prob - w1.y).sum()
    parts = {"nothing happening means NO": w1.event, "YES means status quo": w1.yes_default, "both no, no date": w1.fixed & w1.deadline.isna()}
    parts["the rest"] = ~(parts["nothing happening means NO"] | parts["YES means status quo"] | parts["both no, no date"])
    for name, f in parts.items():
        metrics.append(dict(check=f"share of the total gap: {name}", by="", horizon="1w", n=int(f.sum()), gap=(w1.prob - w1.y)[f].sum() / total))

    # Time left: if lock-up caused this, the return on NO would grow with the time left.
    rets = ev[(ev.deadline.notna()) & ev.prob.between(.1, .9)].copy()
    rets["left"] = (rets.deadline - pd.to_datetime(rets.t, unit="ms")).dt.days
    rets = rets[rets.left > 0]
    for low, high in [(0, 14), (14, 30), (30, 60), (60, 180), (180, 365), (365, 730), (730, 1e5)]:
        g = rets[rets.left.between(low + 1, high)]
        metrics.append(dict(check=f"NO return, {low} to {high} days left", by="creator", horizon="1w", n=len(g), price=g.prob.mean(), yes=g.y.mean(), gap=(1 - g.y.mean()) / (1 - g.prob.mean()) - 1))

    # Who moves the price: log-odds moved by each kind of trader before the snapshot, against the outcome.
    mm = last.merge(w1[["id", "creator"]], on="id")
    mm["who"] = np.select([mm.user == mm.creator, mm.prior < 20, mm.prior < 500, mm.prior < 5000], ["creator", "under 20 earlier bets", "20 to 500", "500 to 5000"], "over 5000")
    flow = mm.pivot_table(index="id", columns="who", values="dl", aggfunc="sum", fill_value=0)
    moved = mm.assign(a=mm.dl.abs()).pivot_table(index="id", columns="who", values="a", aggfunc="sum", fill_value=0)
    e = ev.set_index("id")
    e = e[e.index.isin(flow.index)]
    fit = sm.GLM(e.y, sm.add_constant(flow.loc[e.index]), family=sm.families.Binomial()).fit(cov_type="cluster", cov_kwds=dict(groups=pd.factorize(e.creator)[0]))
    for name in fit.params.index:
        metrics.append(dict(check=f"trader regression: {name}", by="creator", horizon="1w", shift=fit.params[name], low=fit.conf_int().loc[name, 0], high=fit.conf_int().loc[name, 1], gap=flow.loc[e.index, name].mean() if name != "const" else np.nan, n=len(e)))
    vet = (moved[["500 to 5000", "over 5000"]].sum(axis=1) / moved.sum(axis=1)).reindex(e.index)
    for q, g in e.reset_index().groupby(pd.qcut(vet.values, 5, labels=False, duplicates="drop")):
        add(f"nothing means NO, experienced share of price moves, quintile {q + 1}", g, horizon="1w")

    # What is missing from the fetch.
    every = pd.DataFrame([{k: m.get(k) for k in ["id", "question", "resolution", "volume", "uniqueBettorCount", "createdTime", "probability", "resolutionProbability"]} for m in map(json.loads, open(API / "markets.jsonl"))])
    active = every[every.uniqueBettorCount >= 15]
    gated = active[active.resolution.isin(["YES", "NO"])]
    metrics.append(dict(check="volume gate: 15+ bettors below 1000 mana", by="", n=int((gated.volume < 1000).sum()), yes=(gated[gated.volume < 1000].resolution == "YES").mean()))
    metrics.append(dict(check="volume gate: in the sample", by="", n=int((gated.volume >= 1000).sum()), yes=(gated[gated.volume >= 1000].resolution == "YES").mean()))
    in_gate = active[active.volume >= 1000].assign(kind=lambda d: d.question.map(kind))
    for k, g in in_gate.groupby("kind"):
        metrics.append(dict(check=f"dropped N/A or percent resolutions: {k}", by="", n=len(g), gap=g.resolution.isin(["CANCEL", "MKT"]).mean(), yes=(g[g.resolution.isin(["YES", "NO"])].resolution == "YES").mean()))
    un = pd.DataFrame([{k: m.get(k) for k in ["id", "question", "createdTime", "volume", "uniqueBettorCount", "probability"]} for m in map(json.loads, open(DATA / "unresolved.jsonl"))])
    un = un[(un.uniqueBettorCount >= 15) & (un.volume >= 1000)].assign(year=lambda d: pd.to_datetime(d.createdTime, unit="ms").dt.year)
    all_text = pd.concat([un.assign(state="unresolved"), active[active.volume >= 1000].assign(state=lambda d: np.where(d.resolution.isin(["YES", "NO"]), "resolved", "dropped"))])
    all_text["date"] = pd.to_datetime([deadline(q, c)[0] for q, c in zip(all_text.question, all_text.createdTime)])
    for state, g in all_text.groupby("state"):
        passed = g[g.date < COLLECTED - pd.Timedelta(days=60)]
        metrics.append(dict(check=f"title date passed 60+ days ago: {state}", by="", n=len(passed), price=passed.probability.mean(), gap=g.date.notna().mean()))
        metrics.append(dict(check=f"title date still ahead: {state}", by="", n=int((g.date >= COLLECTED - pd.Timedelta(days=60)).sum()), price=g[g.date >= COLLECTED - pd.Timedelta(days=60)].probability.mean()))
    res = gated[gated.volume >= 1000].assign(year=lambda d: pd.to_datetime(d.createdTime, unit="ms").dt.year).groupby("year").size()
    for year, g in un.groupby("year"):
        metrics.append(dict(check=f"still unresolved, created {year}", by="", n=len(g), price=g.probability.mean(), gap=len(g) / (len(g) + res[year])))

    # Polymarket, and whether a similar title is open on the other platform at the snapshot. Same text rule and same $1,000/1,000 mana at the snapshot on both sides.
    pm = pd.read_parquet(DATA / "pm_snap.parquet")
    pm["end"] = pd.to_datetime(pm.end_date, utc=True)
    pm = pm[(pm.takers >= 15) & (pm.vol >= 1000)].assign(kind=lambda d: d.question.map(kind), creator=lambda d: d.grp.astype(str), year=lambda d: pd.to_datetime(d.created_at, utc=True).dt.year)
    pm["t"] = pd.to_datetime(pm.created_at, utc=True).map(lambda c: c.timestamp() * 1e3) + pm.horizon.map(HOURS) * 3600e3
    for h in ["1d", "1w", "1m"]:
        for k, g in pm[pm.horizon == h].groupby("kind"):
            add(f"polymarket: {k}", g, horizon=h)
    p1 = pm[(pm.horizon == "1w") & (pm.kind == "by_date") & pm.year.between(2023, 2025)].copy()
    m1 = w1[(w1.kind == "by_date") & (w1.volume >= 1000) & w1.year.between(2023, 2025)].copy()
    add("manifold, text rule, 1000+ mana, 2023 to 2025: by date", m1, horizon="1w")
    add("polymarket, $1000+, 2023 to 2025: by date", p1, horizon="1w")
    m1["similar"], p1["similar"] = similar_titles(m1, p1)
    for name, g, word in [("manifold", m1, "Polymarket"), ("polymarket", p1, "Manifold")]:
        add(f"{name}: by date, similar {word} title open then", g[g.similar], horizon="1w")
        add(f"{name}: by date, no similar {word} title open then", g[~g.similar], horizon="1w")
        for year, x in g.groupby("year"):
            add(f"{name}, created {year}: by date, similar title", x[x.similar], horizon="1w")
            add(f"{name}, created {year}: by date, no similar title", x[~x.similar], horizon="1w")
    m1[["id", "similar"]].to_csv(OUT / "similar_manifold.csv", index=False)
    p1[["id", "similar"]].to_csv(OUT / "similar_polymarket.csv", index=False)
    both = pairs(moves, {m["id"]: m for m in map(json.loads, open(API / "markets.jsonl")) if m["id"] in set(pd.read_csv(HAND / "pairs_hand.csv").mf_id)})
    both.to_csv(OUT / "pairs.csv", index=False)
    rng = np.random.default_rng(0)
    for (k, h, name), g in pd.concat([both.assign(sample="all"), both[~both.copied].assign(sample="not copied")]).query("kind != 'persist'").groupby(["kind", "horizon", "sample"]):
        d, c = logit(g.manifold.to_numpy()) - logit(g.polymarket.to_numpy()), pd.factorize(g.pm)[0]
        groups = c.max() + 1
        weights = np.array([np.bincount(rng.integers(0, groups, groups), minlength=groups)[c] for _ in range(2000)])
        brier = (g.manifold - g.y) ** 2 - (g.polymarket - g.y_pm) ** 2
        metrics.append(dict(check=f"pairs, {k}, {name}: Manifold minus Polymarket log-odds", by="polymarket market", horizon=h, n=len(g), price=g.manifold.mean(), yes=g.y.mean(), gap=(g.manifold - g.polymarket).abs().mean(), shift=d.mean(), low=np.percentile(weights @ d / weights.sum(axis=1), 2.5), high=np.percentile(weights @ d / weights.sum(axis=1), 97.5)))
        metrics.append(dict(check=f"pairs, {k}, {name}: Brier, Manifold minus Polymarket", by="polymarket market", horizon=h, n=len(g), price=(g.manifold - g.y).pow(2).mean(), yes=(g.polymarket - g.y_pm).pow(2).mean(), shift=brier.mean(), low=np.percentile(weights @ brier.to_numpy() / weights.sum(axis=1), 2.5), high=np.percentile(weights @ brier.to_numpy() / weights.sum(axis=1), 97.5), gap=(g.manifold - g.polymarket).abs().ge(.1).mean()))
        add(f"pairs, {k}, {name}: Manifold price", g.assign(prob=g.manifold, creator=g.pm), horizon=h)
        add(f"pairs, {k}, {name}: Polymarket price", g.assign(prob=g.polymarket, y=g.y_pm, creator=g.pm), horizon=h)

    audit = pd.read_csv(HAND / "resolution_audit.csv")
    for (s, v), n in audit.groupby(["sample", "verdict"]).size().items():
        metrics.append(dict(check=f"audit {s}: {v}", by="", n=int(n)))
    high = ev[ev.prob.between(.55, .85) & (ev.year <= 2025)]
    metrics.append(dict(check="audit: share of NOs that must be wrong to erase the 55-85% gap", by="", n=len(high), price=high.prob.mean(), yes=high.y.mean(), gap=(high.prob.mean() - high.y.mean()) / (1 - high.y.mean())))

    # Plot data.
    edges = np.arange(0, 1.01, .1)
    series = {"nothing happening means NO": lambda x: x.event, "YES means no change": lambda x: x.yes_default, "both labels no default, no title date": lambda x: x.fixed & x.deadline.isna(),
              "old label: other world": lambda x: ~x.quo, "title date": lambda x: x.event & x.deadline.notna(), "title date passed": lambda x: x.event & x.passed}
    for h in HOURS:
        x = w[w.horizon == h]
        for name, f in series.items():
            for b, g in x[f(x)].groupby(pd.cut(x[f(x)].prob, edges, include_lowest=True, labels=False)):
                bins.append(dict(series=name, horizon=h, bin=b, **{k: v for k, v in summary(g).items() if k in ["n", "price", "yes"]}, yes_low=boot_rate(g)[0], yes_high=boot_rate(g)[1]))
    pd.DataFrame(metrics).to_csv(OUT / "metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(bins).to_csv(OUT / "bins.csv", index=False, float_format="%.4f")
    b = before_deadline(moves)
    order = ["1y", "6m", "3m", "1m", "2w", "1w", "3d", "1d"]
    rows = [dict(side=side, dates=name, before=k, **summary(g[(g.before == k)])) for side, x in b.groupby("side") for name, g in [("clear", x[x.clear]), ("unclear", x[~x.clear])] for k in order if (g.before == k).sum() >= 20]
    pd.DataFrame(rows).to_csv(OUT / "before_deadline.csv", index=False, float_format="%.4f")


def hash_half(creator):
    return int(hashlib.md5(creator.encode()).hexdigest(), 16) % 2


def boot_rate(g, seed=0):
    c, y = pd.factorize(g.creator)[0], g.y.to_numpy()
    w = g.w.to_numpy() if "w" in g else np.ones(len(g))
    rng = np.random.default_rng(seed)
    counts = np.array([np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c] for _ in range(RESAMPLES)])
    return np.percentile(counts @ (w * y) / (counts @ w), [2.5, 97.5])


if __name__ == "__main__":
    dict(unresolved=fetch_unresolved, moves=build_moves, polymarket=polymarket, pm_snapshots=pm_snapshots, analyze=analyze)[sys.argv[1]]()
