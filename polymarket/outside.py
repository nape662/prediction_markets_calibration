"""Follow-up to outside_reference: one question, forced choice, in batches. Prompt: polymarket/outside_prompt.txt. Notes: notes/polymarket_outside_source.md.

python polymarket/outside.py sample          -> polymarket/outside_test.csv: 300 random markets to hand-label (column hand), not in unsure_review.csv
python polymarket/outside.py run test        -> polymarket/outside_test_results.jsonl, for the 300 test markets plus the 200 of unsure_review.csv
python polymarket/outside.py run all         -> polymarket/outside_results.jsonl, every market, the old "unsure" ones first; safe to restart
python polymarket/outside.py score           -> agreement of old and new answers with the hand labels
"""
import hashlib, json, random, sys, threading, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
from labeling import HERE, INPUT, LIMIT, NO_CREDIT, RESULTS, claude_call, failure_text

PROMPT, TEST, HOLDOUT = HERE / "outside_prompt.txt", HERE / "outside_test.csv", HERE / "outside_holdout.csv"
SOURCES = {"poll", "odds", "finance", "data_series", "schedule", "forecast", "none"}
BATCH, WORKERS, TRIES = 25, 8, 3
BUDGET = float(sys.argv[3]) if len(sys.argv) > 3 else 20.  # USD at list price; the credit runs out first if it is lower


def old_answers():
    return {r["id"]: r["outside_reference"] for r in (json.loads(json.loads(l)["result"]) for l in open(RESULTS))}


def sample():
    lines = [json.loads(l) for l in open(INPUT)]
    skip = set(pd.read_csv(HERE / "unsure_review.csv", dtype=str).id)
    pick = random.Random(1).sample([m for m in lines if m["id"] not in skip], 300)
    pd.DataFrame([dict(id=m["id"], event_title=m["event_title"], question=m["question"], hand="") for m in pick]).to_csv(TEST, index=False)


def parse(text, ids):
    """The answers, or None if any market is missing or malformed: the whole batch is then retried."""
    got = {}
    for line in text.strip().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            return None
        if not isinstance(r, dict) or r.get("source") not in SOURCES:
            return None
        got[r.get("id")] = r["source"]
    return got if set(got) == set(ids) else None


def ask(batch, version):
    ids = [json.loads(l)["id"] for l in batch]
    for attempt in range(TRIES * 60):
        try:
            a = claude_call(batch, "claude-haiku-5-5", "low", version, PROMPT)
            got = parse(a["result"], ids)
            if got:
                return dict(a, answers=got)
            message, error = a["result"][:200], False
            a["cost"] and wasted.__setitem__(0, wasted[0] + a["cost"])
        except Exception as e:
            message, error = failure_text(e), True
        print(f"{ids[0]}..: {message[:200]}", flush=True)
        if error and NO_CREDIT.search(message):
            raise RuntimeError(f"out of credit: {message[:200]}")
        if error and LIMIT.search(message):
            time.sleep(60)
            continue
        if attempt >= TRIES:
            return None
        time.sleep(5)


wasted = [0.]


def run(name):
    text = PROMPT.read_text()
    lines = {json.loads(l)["id"]: l.strip() for l in open(INPUT)}
    if name == "test":
        ids = [i for f in (TEST, HOLDOUT, HERE / "unsure_review.csv") for i in pd.read_csv(f, dtype=str).id]
    else:
        old = old_answers()
        ids = sorted(lines, key=lambda i: (old[i] != "unsure", random.Random(i).random()))  # old "unsure" first, so a run cut short by the credit covers them
    out = HERE / ("outside_test_results.jsonl" if name == "test" else "outside_results.jsonl")
    version = hashlib.sha256((text + name).encode()).hexdigest()[:8]
    done = {i for l in open(out) for i in json.loads(l)["answers"]} if out.exists() else set()
    spent = sum(json.loads(l)["cost"] for l in open(out)) if out.exists() else 0.
    todo = [i for i in ids if i not in done]
    batches = [[lines[i] for i in todo[k:k + BATCH]] for k in range(0, len(todo), BATCH)]
    print(f"{len(todo):,} of {len(ids):,} left in {len(batches):,} batches, ${spent:.2f} spent", flush=True)
    lock, error = threading.Lock(), None
    with ThreadPoolExecutor(WORKERS) as pool, open(out, "a") as f:
        futures = [pool.submit(ask, b, version) for b in batches]
        for n, fut in enumerate(as_completed(futures), 1):
            if fut.cancelled():
                continue
            try:
                a = fut.result()
            except Exception as e:
                error = error or e
                [x.cancel() for x in futures]
                continue
            if a:
                with lock:
                    f.write(json.dumps(a) + "\n")
                    f.flush()
                spent += a["cost"]
            if spent + wasted[0] > BUDGET and not error:
                error = RuntimeError(f"stopped at ${spent + wasted[0]:.2f}, over the ${BUDGET} budget")
                [x.cancel() for x in futures]
            if n % 50 == 0:
                print(f"{n:,} batches done, ${spent + wasted[0]:.2f} spent", flush=True)
    print(f"${spent + wasted[0]:.2f} spent, ${wasted[0]:.2f} of it on malformed replies", flush=True)
    if error:
        raise error


def score(name="outside_test_results.jsonl"):
    hand = pd.concat([pd.read_csv(TEST, dtype=str).assign(set="random"), pd.read_csv(HOLDOUT, dtype=str).assign(set="holdout, labeled after v2"), pd.read_csv(HERE / "unsure_review.csv", dtype=str).assign(set="old unsure")])
    hand = hand[hand.hand.isin(["yes", "no"])]
    new = {i: s for l in open(HERE / name) for i, s in json.loads(l)["answers"].items()}
    old = old_answers()
    hand["new"] = hand.id.map(lambda i: "no" if new.get(i) == "none" else "yes" if i in new else None)
    hand["old"] = hand.id.map(old)
    for s, g in hand.groupby("set"):
        print(f"{s}: {len(g)} hand-labeled, {g.new.notna().sum()} with a new answer")
        print("  old answer vs hand:", dict(Counter(zip(g.old, g.hand))))
        print("  new answer vs hand:", dict(Counter(zip(g.new, g.hand))))
        print(f"  new agrees with hand: {(g.new == g.hand).mean():.0%}")


if __name__ == "__main__":
    {"sample": sample, "run": lambda: run(sys.argv[2]), "score": lambda: score(*sys.argv[2:])}[sys.argv[1]]()
