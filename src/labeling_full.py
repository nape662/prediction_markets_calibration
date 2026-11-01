"""Label every Manifold market with the cheap labelers. Process and choices: notes/labeling_pilot.md.

python src/labeling_full.py export     -> labeling/manifold_input.jsonl, committed because a cloud session has no data/
python src/labeling_full.py haiku [n]  -> labeling/results/full/manifold_haiku.jsonl, one line per call
python src/labeling_full.py jev [n]    -> labeling/results/full/manifold_jev.jsonl
python src/labeling_full.py haiku-back row -> labeling/results/full/manifold_haiku_back.jsonl: the last input row first, down to row, to meet another run going forward
n stops after that many markets, for a test. Safe to restart: markets with a valid answer are skipped.
Set CLAUDE_BIN as in labeling_pilot.py. Haiku uses the logged-in Claude account; Jev spends the TypeSafe balance.
"""
import hashlib, json, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))  # python -I leaves the script's folder off the path
from labeling_pilot import FIELDS, OUT as PROMPTS, ROOT, claude_call, jev_call, jev_setup, read_calls

OUT = PROMPTS / "results/full"
INPUT = PROMPTS / "manifold_input.jsonl"
BUDGET = dict(haiku=60, jev=4.8)  # USD at list price; stops before an estimate this wrong spends much more, and before Jev's balance runs out
BATCH = dict(haiku=1, jev=1)  # batching is 60% cheaper but pulls Haiku's substantive answers away from Opus's
WORKERS = dict(haiku=12, jev=4)
PASSES = 3  # invalid or skipped answers get retried
WAIT, LIMIT_TRIES, OTHER_TRIES = 300, 72, 3  # a subscription limit resets within 5 hours, so wait out 6; other errors give up
LIMIT = re.compile(r"limit|429|5\d\d\b|overload|rate", re.I)


def export():
    m = pd.read_parquet(ROOT / "data/labeling/manifold.parquet")
    m["created"] = m.created.astype(str).str[:10]
    m["event_title"] = m["outcomes"] = None
    rows = m[FIELDS].astype(object).where(m[FIELDS].notna(), None).sample(frac=1, random_state=0)
    with open(INPUT, "w") as f:
        for r in rows.to_dict("records"):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def markets():
    return {json.loads(l)["id"]: l.strip() for l in open(INPUT)}


def haiku(chunk, version):
    """None means this market keeps failing for a reason other than a limit: it stays missing and the end report counts it."""
    for attempt in range(LIMIT_TRIES):
        try:
            line = claude_call(chunk, "claude-haiku-5-5", "medium", version)
            if '"id"' not in line["result"] and LIMIT.search(line["result"]):
                raise ValueError(line["result"])
            return line
        except (subprocess.SubprocessError, ValueError, KeyError) as e:
            message = f"{e} {getattr(e, 'stdout', '')} {getattr(e, 'stderr', '')}"
            print(f"claude failed, waiting {WAIT}s: {message[:600]}", flush=True)
            if attempt + 1 >= OTHER_TRIES and not LIMIT.search(message):
                return None
            time.sleep(WAIT)
    raise RuntimeError(f"claude still failing after {WAIT * LIMIT_TRIES}s")


def cut_partial_line(path):
    """A kill during a write leaves a cut last line, which would break reading and the next append."""
    data = path.read_bytes()
    path.write_bytes(data[:data.rfind(b"\n") + 1])


def main(kind, limit=None, back_to=None):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"manifold_{kind}{'' if back_to is None else '_back'}.jsonl"
    every = markets()
    todo = dict(list(every.items())[:limit] if back_to is None else list(every.items())[back_to:][::-1])
    text = "".join(every.values())
    if kind == "haiku":
        version = hashlib.sha256(((PROMPTS / "system_prompt.txt").read_text() + text).encode()).hexdigest()[:8]
        work = lambda chunk: haiku(chunk, version)
    else:
        intro, asked, key, prompt = jev_setup()
        version = hashlib.sha256((prompt + text).encode()).hexdigest()[:8]
        work = lambda chunk: jev_call(chunk[0], intro, asked, key, version)
    read = lambda: read_calls(path, need_score=kind == "haiku")
    has_calls = lambda: path.exists() and path.stat().st_size > 0
    if has_calls():
        cut_partial_line(path)
    if has_calls():
        assert read()[3] == {version}, f"{path} was made with another prompt or input"
    error = None
    spent = sum(json.loads(l)["cost"] for l in open(path)) if has_calls() else 0
    for attempt in range(PASSES):
        done = read()[0] if has_calls() else {}
        left = [m for i, m in todo.items() if i not in done]
        print(f"pass {attempt + 1}: {len(left):,} of {len(todo):,} markets left", flush=True)
        chunks = [left[i:i + BATCH[kind]] for i in range(0, len(left), BATCH[kind])]
        pool = ThreadPoolExecutor(WORKERS[kind])
        futures = [pool.submit(work, c) for c in chunks]
        with open(path, "a") as f:
            for n, future in enumerate(as_completed(futures), 1):  # saves each result as it arrives, so a stuck call can't hold others back
                try:
                    line = future.result()
                except Exception as e:  # stop asking, but still save what running calls have paid for
                    error = error or e
                    pool.shutdown(wait=False, cancel_futures=True)
                    continue
                if line:
                    f.write(json.dumps(line) + "\n")
                    f.flush()
                    spent += line["cost"]
                    if spent > BUDGET[kind] and not error:
                        error = RuntimeError(f"stopped at ${spent:.2f}, over the ${BUDGET[kind]} budget")
                        pool.shutdown(wait=False, cancel_futures=True)
                if n % 2000 == 0:
                    print(f"{n:,} calls done", flush=True)
        if error:
            raise error
    answers, bad, cost, _ = read()
    print(f"{kind}: {sum(i in answers for i in todo):,} of {len(todo):,} answered, {bad} invalid lines, ${cost:.6f} per market at list price")


if __name__ == "__main__":
    if sys.argv[1] == "export":
        export()
    elif sys.argv[1] == "haiku-back":
        main("haiku", back_to=int(sys.argv[2]))
    else:
        main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else None)
