"""Haiku labels for Manifold multiple-choice markets: all questions of both binary passes in one call per market.

python manifold_mc/labeling.py prepare -> data/manifold_mc/input.jsonl, committed via publish so labels can be redone without data/
python manifold_mc/labeling.py run [input] -> data/manifold_mc/labels.jsonl, one line per market; safe to restart. input defaults to input.jsonl
python manifold_mc/labeling.py publish -> copies both to manifold_mc/ for committing
Prompt: manifold_mc/system_prompt.txt, built from manifold/labeling/system_prompt.txt (25 questions, without status_quo_default,
which per-option default_side replaces) and labeling/second_pass/system_prompt.txt (7 questions; 4 asked per option).
The input has no prices, outcomes, close or resolution dates; descriptions are cleaned as for binary markets, and tags
with new-year in them are removed (notes/yes_bias_debug.md). The "Other" option is left out.
"""
import hashlib, json, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "manifold")]
from labeling_full import LIMIT, LIMIT_TRIES, WAIT
from labeling_input import LATE_TAGS, clean
from labeling_pilot import claude_call
from labeling_second import ANSWERS

HERE = ROOT / "manifold_mc"
PROMPT, INPUT, LABELS = HERE / "system_prompt.txt", ROOT / "data/manifold_mc/input.jsonl", ROOT / "data/manifold_mc/labels.jsonl"  # kept out of git while a run is in progress
TAGS = {l.split(":")[0] for l in open(ROOT / "manifold/labeling/system_prompt.txt") if re.match(r"[a-z_]+: ", l)} - {"status_quo_default", "substantive_world_question"}
MARKET = {q: ANSWERS[q] for q in ("outside_reference", "general_interest", "prompted_by_news")}
OPTION = {q: ANSWERS[q] for q in ("default_side", "early_side", "early_path")}
WORKERS, TRIES, PASSES = 32, 3, 3
BUDGET = 40  # USD at list price; stops before an estimate this wrong spends much more


def prepare():
    with open(INPUT, "w") as f:
        for m in map(json.loads, open(ROOT / "data/manifold_mc/full.jsonl")):
            tags = [t for t in m.get("groupSlugs") or [] if t not in LATE_TAGS and "new-year" not in t]
            f.write(json.dumps(dict(
                id=m["id"], platform="Manifold", question=m["question"], description=clean(m.get("textDescription")),
                created=datetime.fromtimestamp(m["createdTime"] / 1000, timezone.utc).strftime("%Y-%m-%d"), creator=m["creatorUsername"],
                tags=" ".join(tags) or None, one_winner=bool(m.get("shouldAnswersSumToOne")),
                options=[dict(n=a["index"], text=a["text"]) for a in sorted(m["answers"], key=lambda a: a["index"]) if not a.get("isOther")],
            ), ensure_ascii=False) + "\n")


def valid(result, market):
    """The parsed answer, or None if it breaks the format: a bad answer is retried and never read as a label."""
    try:
        r = json.loads(result)
    except json.JSONDecodeError:
        return None
    date = lambda d: d is None or (isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d))
    options = r.get("options") if isinstance(r.get("options"), list) else []
    good = (r.get("id") == market["id"] and isinstance(r.get("substantive"), int) and 0 <= r["substantive"] <= 100
            and all(isinstance(r.get(k), list) and set(r[k]) <= TAGS for k in ("yes", "unsure")) and all(r.get(q) in a for q, a in MARKET.items())
            and [o.get("n") for o in options if isinstance(o, dict)] == [o["n"] for o in market["options"]]
            and all(o.get(q) in a for o in options for q, a in OPTION.items()) and all(date(o.get("stated_deadline", "missing")) for o in options))
    return r if good else None


def ask(line, version):
    """None means this market keeps failing for a reason other than a limit: it stays missing and the end report counts it."""
    market = json.loads(line)
    for attempt in range(LIMIT_TRIES):
        try:
            answer = claude_call([line], "claude-haiku-5-5", "medium", version, PROMPT)
            if valid(answer["result"], market):
                return answer
            message = answer["result"]
        except (subprocess.SubprocessError, ValueError, KeyError) as e:
            message = f"{e} {getattr(e, 'stdout', '')} {getattr(e, 'stderr', '')}"
        print(f"{market['id']}: {message[:300]}", flush=True)
        limited = LIMIT.search(message)
        if attempt + 1 >= TRIES and not limited:
            return None
        time.sleep(WAIT if limited else 5)
    raise RuntimeError(f"claude still failing after {WAIT * LIMIT_TRIES}s")


def run(path=INPUT):
    lines = [l.strip() for l in open(path)]
    version = hashlib.sha256(PROMPT.read_bytes()).hexdigest()[:8]  # the prompt only, so markets added to the input later keep their labels
    if LABELS.exists():
        data = LABELS.read_bytes()
        LABELS.write_bytes(data[:data.rfind(b"\n") + 1])  # a kill during a write leaves a cut last line
    for attempt in range(PASSES):
        calls = list(map(json.loads, open(LABELS))) if LABELS.exists() else []
        done, spent = {c["ids"][0] for c in calls if c["input_version"] == version}, sum(c["cost"] for c in calls)
        todo = [l for l in lines if json.loads(l)["id"] not in done]
        print(f"pass {attempt + 1}: {len(todo)} of {len(lines)} left, ${spent:.2f} spent", flush=True)
        pool = ThreadPoolExecutor(WORKERS)
        error = None
        with open(LABELS, "a") as f:
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
    calls = [c for c in map(json.loads, open(LABELS)) if c["input_version"] == version]
    print(f"{len(calls)} of {len(lines)} answered, ${sum(c['cost'] for c in calls) / len(calls):.6f} per market at list price")


def publish():
    for f in (INPUT, LABELS):
        shutil.copy(f, HERE / f.name)


if __name__ == "__main__":
    dict(prepare=prepare, publish=publish, run=run)[sys.argv[1]](*sys.argv[2:])
