"""Haiku labels for Polymarket: 5 second-pass questions word for word, plus 11 of the old questions, in one call per market. Prompt: polymarket/system_prompt.txt.

python polymarket/labeling.py prepare -> polymarket/input.jsonl, polymarket/cohorts.csv; run locally, committed because a cloud session has no data/
python polymarket/labeling.py run [n] -> polymarket/results.jsonl, one line per market; safe to restart
python polymarket/labeling.py score   -> answer counts

Cohorts live in cohorts.csv, never in the input, so Haiku can't see them:
  closed_by_feb: closed before Becker's trades end, resolved Yes/No, $1,000+ lifetime volume. Runs first.
  open_in_feb:   open on Feb 2 and closed by our fetch (polymarket/open_in_feb.py), $1,000 or 15 takers by Feb 2. Runs last, and is analysed separately.
The sieve removes only asset_price, sports and weather; markets from its other rules go to Haiku. The input has no prices, outcomes, close or resolution dates.
"""
import csv, hashlib, json, os, re, subprocess, sys, threading, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from labeling_pilot import FIELDS, claude_call

HERE = ROOT / "polymarket"
PROMPT, INPUT, RESULTS, FAILED, COHORTS = HERE / "system_prompt.txt", HERE / "input.jsonl", HERE / "results.jsonl", HERE / "failed.jsonl", HERE / "cohorts.csv"
REMOVE = {"asset_price", "sports", "weather"}
MIN_VOLUME, MIN_TAKERS = 1000, 15
ANSWERS = dict(default_side={"YES", "NO", "NONE"}, outside_reference={"yes", "no", "unsure"}, early_side={"YES_EARLY", "NO_EARLY", "BOTH", "NEITHER"}, early_path={"NORMAL", "SHOCK", "NONE"})
TAGS = {"crypto_price", "other_asset_price", "sports_match", "sports_tournament", "sports_performance", "central_bank_rate", "weather_measurement", "scheduled_release", "speech_or_posts", "existing_fact"}
WORKERS, TRIES, PASSES = 12, 3, 2
BUDGET = 45  # USD at list price. The credit is $52 and the estimate about $30
WAIT, LIMIT_TRIES = 60, 360  # a usage limit resets within 5 hours, so wait out 6; overload passes much sooner
LIMIT = re.compile(r"limit|429|\b5\d\d\b|overload", re.I)
REFUSED = re.compile(r"usage polic|refus|\[bio\]", re.I)  # the last run mistook these for limits and would have waited 6 hours
NO_CREDIT = re.compile(r"credit balance|out of credit|insufficient", re.I)
CHECK_AFTER, MIN_ANSWERED = 200, 0.9  # a broken prompt stops the run here instead of spending the budget on retries
lock = threading.Lock()
wasted = [0.]  # paid for by replies that failed the format check


def prepare():
    import pandas as pd, sieve
    from labeling_input import clean
    old = pd.read_parquet(ROOT / "data/polymarket/open_in_feb/markets.parquet", columns=["id"]).merge(pd.read_parquet(ROOT / "data/polymarket/open_in_feb/activity.parquet"), on="id", validate="1:1")
    old = set(old[(old.vol >= MIN_VOLUME) | (old.takers >= MIN_TAKERS)].id)
    end = datetime.fromisoformat("2026-02-02T18:27:46Z")
    rows = []
    for line in open(ROOT / "data/polymarket/api/markets.jsonl"):
        m = json.loads(line)
        if not m.get("closedTime") or json.loads(m.get("outcomes") or "[]") != ["Yes", "No"]:
            continue
        if m["id"] in old:
            cohort = "open_in_feb"
        else:
            p = json.loads(m.get("outcomePrices") or "[]")
            if datetime.fromisoformat(m["closedTime"]) >= end or len(p) != 2 or max(map(float, p)) < 0.99 or float(m.get("volumeNum") or 0) < MIN_VOLUME:
                continue
            cohort = "closed_by_feb"
        e = (m.get("events") or [{}])[0]
        text = m.get("description") or ""
        game = m.get("sportsMarketType") or e.get("gameId")
        rows.append(dict(id=m["id"], cohort=cohort, question=m.get("question"), event_title=e.get("title"), series=e.get("seriesSlug") or ((e.get("series") or [{}])[0]).get("slug"),
                         category=m.get("category"), tags=" ".join(t.get("slug", "") for t in m.get("tags") or []), game=None if game is None else str(game),
                         description=text if "polymarket.com/event" in text or "data.polymarket" in text else None,
                         text=clean(text), labels=" ".join(t.get("label", "") for t in m.get("tags") or []), outcomes=m["outcomes"], created=(m.get("createdAt") or "")[:10], volume=float(m.get("volumeNum") or 0)))
    d = pd.DataFrame(rows).reset_index(drop=True)
    d["rule"] = None
    for rule, hit in sieve.rules(d, True).items():
        d.loc[hit & d.rule.isna(), "rule"] = rule
    print(d.groupby("cohort").rule.value_counts(dropna=False).to_string())
    d = d[~d.rule.isin(REMOVE)]
    d = d.sample(frac=1, random_state=0).sort_values("cohort", kind="stable")  # closed_by_feb first, so a run stopped by the budget loses only the side sample
    with open(INPUT, "w") as f:
        for r in d.itertuples():
            f.write(json.dumps(dict(id=r.id, platform="Polymarket", question=r.question, description=r.text, created=r.created, creator=None, tags=r.labels or None, event_title=r.event_title, outcomes=r.outcomes), ensure_ascii=False) + "\n")
    d[["id", "cohort", "rule", "volume"]].to_csv(COHORTS, index=False)
    print(d.cohort.value_counts().to_string(), f"\n{INPUT.stat().st_size / 1e6:.0f} MB, mean description {d.text.str.len().mean():.0f} characters (Manifold's input has a shorter text)")


def valid(result, market_id):
    """The parsed answer, or None if it breaks the format: a bad answer is retried and never read as a label."""
    try:
        r = json.loads(result)
    except json.JSONDecodeError:
        return None
    if not isinstance(r, dict) or r.get("id") != market_id or not all(isinstance(r.get(q), str) and r[q] in a for q, a in ANSWERS.items()):
        return None
    date = r.get("stated_deadline", "missing")
    if not (date is None or (isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date))):
        return None
    if type(r.get("substantive")) not in (int, float) or not 0 <= r["substantive"] <= 100:
        return None
    return r if all(isinstance(r.get(k), list) and all(isinstance(t, str) and t in TAGS for t in r[k]) for k in ("yes", "unsure")) else None


def failure_text(e):
    """The model's or the CLI's own message: the full JSON has numbers like 512 that a pattern could read as a server error."""
    out = getattr(e, "stdout", "") or ""
    try:
        return f"{json.loads(out)['result']}"
    except (ValueError, KeyError, TypeError):
        return f"{e} {out} {getattr(e, 'stderr', '')}"


def ask(line, version):
    """None means this market keeps failing for a reason other than a limit: it stays missing and the end report counts it."""
    market_id = json.loads(line)["id"]
    tries = 0
    for _ in range(LIMIT_TRIES):
        try:
            answer = claude_call([line], "claude-haiku-5-5", "medium", version, PROMPT)
            if valid(answer["result"], market_id):
                return answer
            message, error = answer["result"], False
            with lock, open(FAILED, "a") as f:
                wasted[0] += answer["cost"]
                f.write(json.dumps(dict(id=market_id, cost=answer["cost"], result=message)) + "\n")
        except (subprocess.SubprocessError, ValueError, KeyError) as e:
            message, error = failure_text(e), True
        print(f"{market_id}: {message[:300]}", flush=True)
        if error and NO_CREDIT.search(message):  # only a failed call: an answer's own text may contain these words
            raise RuntimeError(f"out of credit: {message[:300]}")
        if error and LIMIT.search(message) and not REFUSED.search(message):
            time.sleep(WAIT)
            continue
        tries += 1
        if tries >= TRIES:
            return None
        time.sleep(5)
    raise RuntimeError(f"claude still failing after {WAIT * LIMIT_TRIES}s")


def run(limit=None):
    text = PROMPT.read_text()
    assert all(f"\n{t}: " in text for t in [*TAGS, *ANSWERS, "stated_deadline", "substantive_world_question"]), "prompt is missing a question"
    lines = [l.strip() for l in open(INPUT)]
    lines = lines[:limit] if limit else lines
    version = hashlib.sha256((text + "".join(lines)).encode()).hexdigest()[:8]
    if RESULTS.exists():
        os.truncate(RESULTS, RESULTS.read_bytes().rfind(b"\n") + 1)  # a kill during a write leaves a cut last line
    wasted[0] = sum(json.loads(l)["cost"] for l in open(FAILED)) if FAILED.exists() else 0.
    for attempt in range(PASSES):
        calls = list(map(json.loads, open(RESULTS))) if RESULTS.exists() else []
        assert all(c["input_version"] == version for c in calls), f"{RESULTS} was made with another prompt or input"
        done, spent = {c["ids"][0] for c in calls}, sum(c["cost"] for c in calls)
        todo = [l for l in lines if json.loads(l)["id"] not in done]
        print(f"pass {attempt + 1}: {len(todo):,} of {len(lines):,} left, ${spent + wasted[0]:.2f} spent", flush=True)
        assert spent + wasted[0] < BUDGET, f"already spent ${spent + wasted[0]:.2f}, over the ${BUDGET} budget"
        error, answered = None, 0

        def stop(reason):  # the workers drop cancelled markets from the queue; running calls finish and get saved
            nonlocal error
            error = error or reason
            for x in futures:
                x.cancel()

        with ThreadPoolExecutor(WORKERS) as pool, open(RESULTS, "a") as f:
            futures = [pool.submit(ask, l, version) for l in todo]
            for n, future in enumerate(as_completed(futures), 1):
                if future.cancelled():
                    continue
                try:
                    answer = future.result()
                except Exception as e:
                    stop(e)
                    continue
                if answer:
                    answered += 1
                    f.write(json.dumps(answer) + "\n")
                    f.flush()
                    spent += answer["cost"]
                if spent + wasted[0] > BUDGET:
                    stop(RuntimeError(f"stopped at ${spent + wasted[0]:.2f}, over the ${BUDGET} budget"))
                if n == CHECK_AFTER and attempt == 0 and answered < MIN_ANSWERED * n:
                    stop(RuntimeError(f"only {answered} of the first {n} markets answered validly"))
                if n % 500 == 0:
                    print(f"{n:,} calls done, ${spent + wasted[0]:.2f} spent", flush=True)
        if error:
            raise error
    calls = list(map(json.loads, open(RESULTS)))
    print(f"{len(calls):,} of {len(lines):,} answered, ${sum(c['cost'] for c in calls) / len(calls):.6f} per market at list price, ${sum(c['cost'] for c in calls) + wasted[0]:.2f} in all, ${wasted[0]:.2f} of it on replies that failed the format check")


def score():
    calls = [json.loads(json.loads(l)["result"]) for l in open(RESULTS)]
    cohort = {r["id"]: r["cohort"] for r in csv.DictReader(open(COHORTS))}
    print(Counter(cohort[c["id"]] for c in calls))
    for q in ANSWERS:
        print(q, Counter(c[q] for c in calls).most_common())
    print("deadline given:", sum(c["stated_deadline"] is not None for c in calls), "of", len(calls))
    print("yes:", Counter(t for c in calls for t in c["yes"]).most_common())
    print("substantive at or below 20:", sum(c["substantive"] <= 20 for c in calls), "at or above 80:", sum(c["substantive"] >= 80 for c in calls))


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "run":
        run(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    else:
        score()
