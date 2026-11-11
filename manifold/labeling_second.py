"""Second Haiku pass: only the new questions in notes/second_pass_questions.md, Manifold only.

python manifold/labeling_second.py prepare     -> manifold/labeling/second_pass/full.jsonl, pilot.jsonl; run locally, committed because a cloud session has no data/
python manifold/labeling_second.py run pilot [n] -> manifold/labeling/second_pass/pilot_results.jsonl, one line per market; safe to restart
python manifold/labeling_second.py run full [n]  -> manifold/labeling/second_pass/full_results.jsonl
python manifold/labeling_second.py run check   -> manifold/labeling/second_pass/check_results.jsonl: 100 pilot markets again, after early_likelihood became early_path
python manifold/labeling_second.py score <pilot|check|full> -> compares with the hand labels in manifold/other/labeling_review/yes_bias/polarity_hand.csv; the pilot was scored with the old field name, see pilot_score.txt
The input has no prices, outcomes, close or resolution dates. Tags with new-year in them are removed, because that tag depends on the outcome (notes/yes_bias_debug.md).
"""
import csv, hashlib, json, random, re, subprocess, sys, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
sys.path[:0] = [str(Path(__file__).parent), str(Path(__file__).resolve().parents[1] / "src")]
from labeling_full import LIMIT, LIMIT_TRIES, WAIT
from labeling_pilot import OUT, claude_call

DIR = OUT / "second_pass"
PROMPT = DIR / "system_prompt.txt"
HAND = OUT.parent / "other/labeling_review/yes_bias/polarity_hand.csv"
ANSWERS = dict(default_side={"YES", "NO", "NONE"}, outside_reference={"yes", "no", "unsure"}, early_side={"YES_EARLY", "NO_EARLY", "BOTH", "NEITHER"},
               early_path={"NORMAL", "SHOCK", "NONE"}, general_interest={"yes", "no", "unsure"}, prompted_by_news={"yes", "no", "unsure"})
PILOT_HAND, PILOT_RANDOM, WORKERS, TRIES, PASSES = 150, 150, 12, 3, 3
BUDGET = 40  # USD at list price, about twice the estimate; stops before an estimate this wrong spends much more


def prepare():
    DIR.mkdir(exist_ok=True)
    rows = []
    for line in open(OUT / "manifold_input.jsonl"):
        m = json.loads(line)
        m["tags"] = " ".join(t for t in (m["tags"] or "").split() if "new-year" not in t) or None
        rows.append(m)
    with open(DIR / "full.jsonl", "w") as f:
        f.writelines(json.dumps(m, ensure_ascii=False) + "\n" for m in rows)
    hand = {r["id"] for r in csv.DictReader(open(HAND))}
    rng = random.Random(20261103)
    labeled = [m for m in rows if m["id"] in hand]
    others = [m for m in rows if m["id"] not in hand]
    pilot = rng.sample(labeled, PILOT_HAND) + rng.sample(others, PILOT_RANDOM)
    rng.shuffle(pilot)
    with open(DIR / "pilot.jsonl", "w") as f:
        f.writelines(json.dumps(m, ensure_ascii=False) + "\n" for m in pilot)


def valid(result, market_id):
    """The parsed answer, or None if it breaks the format: a bad answer is retried and never read as a label."""
    try:
        r = json.loads(result)
    except json.JSONDecodeError:
        return None
    date = r.get("stated_deadline", "missing")
    good = r.get("id") == market_id and all(r.get(q) in a for q, a in ANSWERS.items()) and (date is None or (isinstance(date, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)))
    return r if good else None


def ask(line, version):
    """None means this market keeps failing for a reason other than a limit: it stays missing and the end report counts it."""
    market_id = json.loads(line)["id"]
    for attempt in range(LIMIT_TRIES):
        try:
            answer = claude_call([line], "claude-haiku-5-5", "medium", version, PROMPT)
            if valid(answer["result"], market_id):
                return answer
            message = answer["result"]
        except (subprocess.SubprocessError, ValueError, KeyError) as e:
            message = f"{e} {getattr(e, 'stdout', '')} {getattr(e, 'stderr', '')}"
        print(f"{market_id}: {message[:300]}", flush=True)
        limited = LIMIT.search(message)
        if attempt + 1 >= TRIES and not limited:
            return None
        time.sleep(WAIT if limited else 5)
    raise RuntimeError(f"claude still failing after {WAIT * LIMIT_TRIES}s")


def run(name, limit=None):
    lines = [l.strip() for l in open(DIR / f"{name}.jsonl")]
    lines = lines[:limit] if limit else lines
    path = DIR / f"{name}_results.jsonl"
    version = hashlib.sha256((PROMPT.read_text() + "".join(lines)).encode()).hexdigest()[:8]
    if path.exists():
        data = path.read_bytes()
        path.write_bytes(data[:data.rfind(b"\n") + 1])  # a kill during a write leaves a cut last line
    for attempt in range(PASSES):
        calls = list(map(json.loads, open(path))) if path.exists() else []
        assert all(c["input_version"] == version for c in calls), f"{path} was made with another prompt or input"
        done, spent = {c["ids"][0] for c in calls}, sum(c["cost"] for c in calls)
        todo = [l for l in lines if json.loads(l)["id"] not in done]
        print(f"pass {attempt + 1}: {len(todo)} of {len(lines)} left, ${spent:.2f} spent", flush=True)
        pool = ThreadPoolExecutor(WORKERS)
        error = None
        with open(path, "a") as f:
            for n, future in enumerate(as_completed([pool.submit(ask, l, version) for l in todo]), 1):
                try:
                    answer = future.result()
                except Exception as e:  # stop asking, but still save what running calls have paid for
                    error = error or e
                    pool.shutdown(wait=False, cancel_futures=True)
                    continue
                if answer:
                    f.write(json.dumps(answer) + "\n")
                    f.flush()
                    spent += answer["cost"]
                    if spent > BUDGET and not error:
                        error = RuntimeError(f"stopped at ${spent:.2f}, over the ${BUDGET} budget")
                        pool.shutdown(wait=False, cancel_futures=True)
                if n % 500 == 0:
                    print(f"{n} calls done, ${spent:.2f} spent", flush=True)
        if error:
            raise error
    calls = list(map(json.loads, open(path)))
    print(f"{len(calls)} of {len(lines)} answered, ${sum(c['cost'] for c in calls) / len(calls):.6f} per market at list price")


def score(name):
    calls = [json.loads(json.loads(l)["result"]) for l in open(DIR / f"{name}_results.jsonl")]
    hand = {r["id"]: r["yes_default"] == "True" for r in csv.DictReader(open(HAND))}
    print("default_side against hand YES-default:", sorted(Counter((hand[c["id"]], c["default_side"]) for c in calls if c["id"] in hand).items()))
    for q in [*ANSWERS, "pair"]:
        print(q, Counter((c["early_side"], c["early_path"]) if q == "pair" else c[q] for c in calls).most_common())
    print("deadline given:", sum(c["stated_deadline"] is not None for c in calls), "of", len(calls))


if __name__ == "__main__":
    if sys.argv[1] == "run":
        run(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else None)
    elif sys.argv[1] == "score":
        score(sys.argv[2])
    else:
        prepare()
