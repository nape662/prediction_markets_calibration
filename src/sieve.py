"""Deterministic first-pass labels ("sieve") for Polymarket and Manifold markets.

python src/sieve.py -> data/categories/{polymarket,manifold}.parquet and a printed funnel.

Rules use only question text, event title, tags/topics and series metadata; never prices or outcomes.
Rules run in order; a market gets the first rule that matches. rule = null means "for the LLM".
Labels are per market: a group (used for sampling and compression) can mix functions.
group: Polymarket series slug, else event id, else market id; Manifold creator + question with digits, months and weekdays stripped.
"""
import json, time
from pathlib import Path
import pandas as pd, pyarrow as pa, pyarrow.compute as pc

DATA = Path(__file__).resolve().parents[1] / "data"
FUNCTION = {"random": "random", "meta": "meta", "personal": "personal", "asset_price": "mirror", "sports": "mirror",
            "central_bank": "mirror", "weather": "stat", "stat": "stat", "mentions": "world"}

ASSET = (r"\b(bitcoin|btc|ethereum|eth|ether|solana|sol|xrp|ripple|dogecoin|bnb|cardano|hyperliquid|hype|sui|pepe|shib|avax|chainlink"
         r"|litecoin|ltc|polygon|matic|toncoin|trx|polkadot|aptos|fartcoin|wif|bonk|usdc|usdt|tether|s&p ?500|s&p|spx|nasdaq|ndx|dow jones|dow"
         r"|russell 2000|hang seng|nikkei|ftse|dax|vix|nvda|tsla|aapl|msft|amzn|googl|goog|qqq|spy|gold|silver|crude oil|oil|wti|brent"
         r"|natural gas|copper|treasury yield|yield|dxy|dollar index|yen|euro|ruble|forex)\b|\$[a-z]{2,}\b|\b(usd|eur|gbp|jpy)/[a-z]{3}\b"
         r"|[a-z]{3}/usd\b")
TICKER = r"\([A-Z]{2,5}\)"  # case-sensitive; "(HIGH)"/"(LOW)" are strike labels, not tickers
COMPANY = r"\b(tesla|nvidia|apple|microsoft|amazon|google|alphabet|meta|netflix|palantir|gamestop|coinbase|microstrategy)\b"
STOCK = (r"\bstocks?\b|\bshares?\b|\b(trade|trades|trading|reach|hit|close|closes|above|below)\b[^?]{0,10}\$\d|market cap"
         r"|close (higher|lower|above|below)|all[- ]time high|largest company|nasdaq|nyse")
PRICE = (r"up or down|all[- ]time high|\bath\b|\bflips?\b|market cap|price|largest company|___|\$\s?\d[\d,.]*\s?[kmb]?\b|\d+¢"
         r"|\b(above|below|over|under|reach|hit|dip|drop|fall|close|closes|finish|trade|surpass|exceed|cross|break)\b[^?]{0,25}"
         r"(\d[\d,.]*\s?k\b|\d{1,3}(,\d{3})+|\d{5,}|\b([13-9]\d{3}|2[1-9]\d\d)\b)"
         r"|close (higher|lower|above|below|up|down)|higher than (it|the previous|yesterday)|\d+c\b|yield[^?]{0,30}\d%")
NOT_PRICE = (r"launch|airdrop|\betf\b|rug|burn|listing|\blist(ed)?\b|reserve|holdings|purchase|\bbuy|\bsell|\bsold\b|score|benchmark|\bban\b"
             r"|hack|net worth|billionaire|richest|tariff|announce|release|deliver|beat (its )?(quarterly )?(earnings|eps)|earnings call|revenue"
             r"|\bsales\b|provision|valuation|\bsay\b|mention|acqui|\bipo\b|publicly trad"
             r"|starts trading|gas price|gwei|hashprice|trademark|lawsuit|\bsue|last digit|shareholders? vote|wikipedia|market share|trends"
             r"|price (hike|cut|increase)|starting price|\binvest|silver bulletin|\bfees\b|gpt|\bai\b")
SPORTS_TAG = (r"sports|\bnfl\b|\bnba\b|\bmlb\b|\bnhl\b|\bufc\b|\bmma\b|soccer|football|basketball|baseball|hockey|tennis|\bgolf\b|formula-?1|\bf1\b"
              r"|motorsports|auto-racing|boxing|cricket|\bipl\b|\bepl\b|la-liga|champions-league|uefa|fifa|world-cup|premier|serie-a|bundesliga"
              r"|\bmls\b|ncaa|\bcfb\b|\bcbb\b|cwbb|college-(football|basketball)|march-madness|counter-?strike|dota|league-of-legends|\blol\b"
              r"|valorant"
              r"|chess|olympics|wnba|nascar|cycling|bicycle-racing|tour-de-france|rugby|darts|snooker|pga-tour|horse-racing|super-bowl|euros-20")
SPORTS_Q = (r"\bvs\.?\b|\bv\.? |o/u|over/under|spread|moneyline|parlay|\bbeat\b|\bwins?\b|\blose\b|\bdefeat|\bwinner|\bmatch|\bplay\b|\bfight"
            r"|\bchampion|grand prix|super bowl|world series|stanley cup|nba finals|world cup|\bcup\b|playoffs?|postseason|season|\bmvp\b|of the year"
            r"|heisman|draft|touchdowns?|passing yards|rushing|home run|\bpitch|knockout|\bko\b|submission|\bscore|\bgoals?\b|\bpoints\b|rebounds"
            r"|assists|\bmaps?\b|\bset\b|\bseed|top \d|relegat|qualif|medals?|podium|\bpole\b|\brace\b|\btitle\b|\brecord\b|finish|finals?\b|make the"
            r"|shut ?out|penalt|\bstart\b|tournament|the international|worlds\b|\b(over|under) \d|both teams|halftime|scorigami|triple[- ]double"
            r"|double[- ]double|🏈|⚽|🏀|⚾|🏒")
NOT_SPORTS = (r"releas|attend|half-?time show|commercial|\badvert|anthem|trump|biden|taylor swift|video game|hmmt|vision pro|suspen|\btraded?\b"
              r"|\bsign(s|ed)?\b|\bsales\b|topshot|perform|\bsongs\b|broadcast|exclusiv|announcer|(head|next) coach|retire|arrest|fired|frostbite")
CENTRAL_BANK = (r"(\bfed\b|federal reserve|fomc|\becb\b|\bbank of \w+|\bboe\b|\bpboc\b|\bboj\b|reserve bank|central bank|fed funds"
                r"|base rate|cash rate|interest rates?)[^?]*\b(rates?|cuts?|hikes?|raise|lower|bps|basis points|decision|increase|decrease|pause)\b"
                r"|\b(rate (cut|hike)s?|bps|basis points)\b[^?]*(\bfed\b|fomc|\becb\b|bank of|\bboe\b|\bboj\b)|fed decision|fed interest")
NOT_CENTRAL_BANK = r"\bsay|mention|dissent|\bvote|chair|nominat|fire|confirm|\bif\b|recession|gdp|self-certify|\bwear|odds|favou?red|derivative"
WEATHER = (r"(highest|high|low|lowest|average|global) temperature|temperature increase|heat increase|°[cf]|ºc|precipitation|rainfall"
           r"|inches of (rain|snow)|snowfall|air quality|white christmas|\bsnow\b|hottest|warmest|coldest")
NOT_WEATHER = r"superconduct|snow-?plow|deaths?|\bif\b"
STAT = (r"# of|number of|how many (tweets|posts)|\btweets? \d|\d+\+? (new )?(tweets|posts)\b|truth social posts|executive orders"
        r"|\d[\d,.]*\s?[kmb]?\+? (million |billion )?views|\bviews\b[^?]{0,40}\d"
        r"|\d\S* (million |billion )?(streams|plays)\b|box office|opening weekend|\bgross(es|ed|ing)?\b|rotten tomatoes|approval rating"
        r"|approval up or down|approval [^?]{0,30}\d+(\.\d+)?%"
        r"|\d[\d,.]*\s?[kmb]?\+? (\w+ )?cases\b|\bcases\b[^?]{0,40}\d|inflation|\bcpi\b|jobs (added|report)|unemployment|\bgdp\b|jobless claims"
        r"|egg prices|dozen eggs|gas prices?|\btsa\b"
        r"|etf (net )?flows|beat (its )?(quarterly )?(earnings|eps)|(#\d+|top|number one).{0,40}(app store|netflix)|#1 (song|album|app|free|paid)"
        r"|top song|billboard (hot|200|chart|global)|spotify (charts?|top|wrapped)|top .{0,30}spotify|subscribers|best ai model|top ai model"
        r"|ai model end of|(best|top|second|third|#\d) ai company|style control|lmarena|chatbot arena|baby names|girl names|boy names")
NOT_STAT = r"seats|\bvotes?\b|\bsay\b|mention|republicans|democrats|reduction act"
MENTION = (r"\b(say|says|said|mention|mentions|use the (word|phrase|term))\b[^?]{0,30}[\"“]|\b(tweet|tweets|post|posts|write|writes)\s+[\"“]"
           r"|[\"“][^\"”]+[\"”]\s+(be\s+)?(said|mentioned|tweeted|posted|used)\b")
RANDOM = r"(^|[^-])coin ?(flip|toss)|heads or tails|\bdice\b|roll (a|the) d|random number generator|random\.org|\blottery\b"
NOT_RANDOM = r"lottery pick|non-coinflip|liquidity|ponzi|pay prizes|\brules?\b|\balter|interesting|factoriz|newcomb|ultimatum|responder"
META = (r"\bmanifold\b|\bmana\b|\bmanalinks?\b|(creator|trader|profit|all-time)s? leaderboard|\b(bronze|silver|gold|platinum|diamond"
        r"|masters?)\b[^?]{0,10}\bleague"
        r"|\b(promot|demot)\w*\b[^?]{0,15}\b(bronze|silver|gold|platinum|diamond|masters?|league|\?\?)|\bdemote\?|\b(masters|diamond"
        r"|platinum) .*season"
        r"|trustworthy[- .]*ish|\bbadges?\b|market reviews|\d+\+? (or more |or fewer |more |new )?(unique )?(traders|bettors|predictors|holders"
        r"|participants)\b"
        r"|unique (traders|bettors|predictors)|\bmarkets?\b[^?]{0,40}\bresolves?\b|[\"“'].{5,}[\"”'] (market|question)|\bmisresolv"
        r"|market creators?\b|^(this|the) market resolves|^resolves (yes|no)|whales vs\.? minnows|ponzi|team (yes|no)\b"
        r"|\b(yes|no) (holders|shares)|(mana|lifetime|all-time|trading|betting|league) profits?\b|most profitable (trader|user|bettor|proofnik)"
        r"|\b(i|my)\b[^?]{0,40}\bprofit(s|able)?\b"
        r"|@\w+[^?]{0,40}\bprofit|profit[^?]{0,30}\bmarkets?\b|\bmy account\b|(my|total) portfolio|portfolio value|tug of war"
        r"|more holders|\breferrals?\b|(m\$|ṁ) ?\d|\d ?(m\$|ṁ)|shares held|\bfollow(ing|ers?)?\b[^?]{0,20}@\w|\bleagues? (season|s\d|prize)"
        r"|prize in leagues"
        r"|\b(create|creat\w*|make|made|resolv\w*)\b[^?]{0,25}\bmarkets?\b|my [^?]{0,40}\bmarkets?\b|resolve this\b|follower count|\b(\d+"
        r"|my) followers\b|#\d+ in (the |my )?[\w ]{0,30}league|(betting|trading|prediction|manifold) streak"
        r"|at market close")
PM_DERIVATIVE = (r"is priced|\bpriced (over|above|below|under|at)|(is|becomes|as) the favou?rite|midpoint|\d+¢"  # in descriptions that link
                 r"|price of the .{0,30}(option|outcome|market)")                                            # another Polymarket market
THIS_MARKET = r"this (market|question|prediction|poll)\b"
TIME_REF = r"(before|by|until|prior to|of|when|after|at|on) (this|the) (market|question)('s)? (close|closes|closing|open|opens|creation|end|ends|resolution)"
NOT_META = r"non-?profit|for-profit|stock market|market cap|subsid|bounty|\bwin (the )?(m\$|ṁ)"
PERSONAL = r"\bI\b|\bI'(m|ll|ve|d)\b|\b[Mm]y\b|\bme\b|\b[Mm]yself\b|\([Pp]ersonal\)"
NOT_PERSONAL = r"\b(Artemis|Voyager|War|Part|Phase|Act|Book|Chapter|Volume|Division|Elizabeth|Charles) I\b|\b[A-Z]{2,} I\b|\bA\.I\.|\bI/O\b|[\"“][^\"”]*[\"”]"
TOPICS = [("sports", SPORTS_TAG), ("crypto", r"crypto|bitcoin|ethereum|solana|memecoin|airdrop|\bnft|defi|stablecoin|token|\bxrp\b|doge"),
          ("ai", r"(^|[\s-])ai([\s-]|$)|openai|anthropic|llm|chatgpt|gpt|claude|gemini|deepmind|\bagi\b|grok"),
          ("economy", r"econom|financ|stocks|equities|\bfed\b|fed-|inflation|interest-rates|business|earnings|ipo|commodities|macro-|\bjobs\b|gdp|tariff"),
          ("politics", r"politic|election|trump|biden|kamala|congress|senate|geopolitic|\bwars?\b|ukraine|russia|israel|gaza|iran|china|middle-east"
                       r"|world|government|supreme-court|court"),
          ("science", r"science|space|spacex|physics|climate|weather|health|pandemic|covid|medicine|disease|math"),
          ("tech", r"tech|apple|google|tesla|internet|elon-musk|twitter|social-media"),
          ("culture", r"culture|movies|music|awards|entertainment|celebrit|youtube|tweets|gaming|games|\btv\b|netflix|books?\b|destiny|stream"
                      r"|eurovision|oscars|emmys|grammys|anime|one-piece")]


def has(s, pat, case=False):
    return pd.Series(pc.match_substring_regex(pa.array(s.fillna("")), pat, ignore_case=not case).to_numpy(zero_copy_only=False), index=s.index)


def checkpoint_size():  # the fetch may still be appending and rewriting state.json
    for _ in range(20):
        try:
            return json.loads((DATA / "polymarket/api/state.json").read_text())["size"]
        except json.JSONDecodeError:
            time.sleep(0.5)
    raise RuntimeError("state.json stays unreadable")


def load_polymarket():
    size, rows = checkpoint_size(), []
    with open(DATA / "polymarket/api/markets.jsonl", "rb") as f:
        for line in f:
            if f.tell() > size: break
            m = json.loads(line)
            e = (m.get("events") or [{}])[0]
            desc = m.get("description") or ""  # kept only when it points to another Polymarket market, to save memory
            desc = desc if "polymarket.com/event" in desc or "data.polymarket" in desc else None
            rows.append(dict(id=m["id"], description=desc, question=m.get("question"), event_title=e.get("title"), event_id=e.get("id"),
                             series=e.get("seriesSlug") or ((e.get("series") or [{}])[0]).get("slug"), category=m.get("category"),
                             tags=" ".join(t.get("slug", "") for t in m.get("tags") or []),
                             game=m.get("sportsMarketType") or e.get("gameId")))
    d = pd.DataFrame(rows)
    d["group"] = ("s:" + d.series).fillna("e:" + d.event_id).fillna("m:" + d.id.astype(str))
    return d


def load_manifold():
    d = pd.read_json(DATA / "manifold/api/full.jsonl", lines=True, dtype=False)[["id", "question", "creatorUsername", "groupSlugs"]]
    d["tags"] = d.groupSlugs.map(lambda g: " ".join(g) if isinstance(g, list) else "")
    months = r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|june?|july?|aug(ust)?|sep(t|tember)?|oct(ober)?|nov(ember)?|dec(ember)?"
    t = d.question.str.lower().str.replace(rf"\b({months}|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", "@", regex=True)
    t = t.str.replace(r"\d+(st|nd|rd|th)?", "#", regex=True).str.replace(r"#([.,:]#)+", "#", regex=True).str.replace(r"\s+", " ", regex=True)
    d["group"] = d.creatorUsername + "|" + t.str.strip()
    return d


def rules(d, polymarket):
    q, tags = d.question.fillna(""), d.tags
    t = q + " || " + d.event_title.fillna("") if polymarket else q
    if polymarket:  # resolves on another Polymarket market's price
        out = {"meta": has(d.description, PM_DERIVATIVE)}
    else:  # on Polymarket questions these patterns only produce false hits
        out = {"meta": (has(q, META) | has(q, THIS_MARKET) & ~has(q, TIME_REF)) & ~has(q, NOT_META)}
        out["personal"] = has(q.str.replace(NOT_PERSONAL, "", regex=True), PERSONAL, case=True) | has(q, r"^\W*(will|can|do|did|am|should|have) i\b")
    out["mentions"] = (has(t, MENTION) & ~has(t, r"index says")) | (has(tags, r"\bmention-markets\b") if polymarket else False)
    out["random"] = (has(q, RANDOM) | has(tags, r"fairlyrandom|pure-chance|dailycoinflip")) & ~has(q, NOT_RANDOM)
    price_tags = r"crypto-prices|stock-prices|equities|indicies|memecoins|stablecoins|commodities|sccsq4|sp-500"
    ticker = has(t, TICKER, case=True) & ~has(t, r"\((HIGH|LOW)\)", case=True)
    out["asset_price"] = (has(t, ASSET) | ticker | has(t, COMPANY) & has(t, STOCK) | has(tags, price_tags)) & has(t, PRICE) & ~has(t, NOT_PRICE)
    if polymarket:
        out["asset_price"] |= has(tags, r"\bup-or-down\b") & ~has(t, r"approval|market cap")
        sports_meta = d.game.notna() | has(tags + " " + d.series.fillna(""), SPORTS_TAG) | d.category.isin(["Sports", "NBA Playoffs", "Olympics", "Chess"])
        out["sports"] = sports_meta & has(t, SPORTS_Q) & ~has(t, NOT_SPORTS)
    else:
        out["sports"] = has(tags, SPORTS_TAG) & has(q, SPORTS_Q) & ~has(q, NOT_SPORTS)
    out["central_bank"] = has(t, CENTRAL_BANK) & ~has(t, NOT_CENTRAL_BANK)
    out["weather"] = has(t, WEATHER) & ~has(t, NOT_WEATHER) & (has(tags, r"weather|climate|global-temp|heat|science|\ball\b") if polymarket else True)
    out["stat"] = has(t, STAT) & ~has(t, NOT_STAT)
    return out


def sieve(d, polymarket, name):
    d["rule"] = None
    events = f" in {d.event_id.nunique():,} events" if "event_id" in d else ""
    print(f"\n{name}: {len(d):,} markets{events} in {d.group.nunique():,} groups\n{'rule':14s}{'function':10s}{'markets':>9s}{'groups':>8s}")
    for rule, hit in rules(d, polymarket).items():
        new = hit & d.rule.isna()
        d.loc[new, "rule"] = rule
        print(f"{rule:14s}{FUNCTION[rule]:10s}{new.sum():9,d}{d[new].group.nunique():8,d}")
    left = d.rule.isna()
    print(f"{'left for LLM':24s}{left.sum():9,d}{d[left].group.nunique():8,d}")
    d["function"] = d.rule.map(FUNCTION)
    d["topic"] = None
    for topic, pat in reversed(TOPICS):  # earlier topics win
        d.loc[has(d.tags, pat), "topic"] = topic
    mixed = d.groupby("group").rule.agg(lambda r: r.fillna("").nunique() > 1)
    print(f"groups with markets under different rules: {mixed.sum():,} of {len(mixed):,}")
    (DATA / "categories").mkdir(exist_ok=True)
    d[["id", "group", "rule", "function", "topic"]].to_parquet(DATA / f"categories/{name}.parquet", index=False)


if __name__ == "__main__":
    sieve(load_polymarket(), True, "polymarket")
    sieve(load_manifold(), False, "manifold")
