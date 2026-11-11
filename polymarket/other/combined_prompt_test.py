"""Do the 13 old filter questions change Haiku's answers to the 7 second-pass questions when asked in the same call?

python polymarket/other/combined_prompt_test.py -> polymarket/other/combined_test_prompt.txt, polymarket/other/combined_test_results.jsonl and a printed comparison.
200 random Manifold markets, medium effort, one per call, compared with their stored answers from the two separate runs. Safe to restart.
"""
import hashlib, json, random, subprocess, sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "manifold")]
from labeling_pilot import claude_call, questions, read_calls
from labeling_second import ANSWERS, valid

HERE = ROOT / "polymarket/other"
PROMPT, RESULTS = HERE / "combined_test_prompt.txt", HERE / "combined_test_results.jsonl"
SECOND = ROOT / "manifold/labeling/second_pass"
SCORED = "substantive_world_question"
TAGS = ["fixed_chance", "crypto_price", "other_asset_price", "sports_match", "sports_tournament", "sports_performance", "sports_award", "central_bank_rate",
        "weather_measurement", "scheduled_release", "speech_or_posts", "existing_fact"]
N, WORKERS, BUDGET = 200, 12, 1  # USD at list price
STABLE = dict(default_side=96, early_side=96, general_interest=94, stated_deadline=93, prompted_by_news=86, outside_reference=71)  # same answer on 100 reruns of the second-pass prompt, notes/findings_reference.md


def prompt():
    second = (SECOND / "system_prompt.txt").read_text().split("\n\nThe input is one market.")[0]
    old = dict(questions())
    fields = '"default_side":"...","outside_reference":"...","stated_deadline":"..." or null,"early_side":"...","early_path":"...","general_interest":"...","prompted_by_news":"..."'
    block = "\n\n".join(f"{q}: {old[q]}" for q in [*TAGS, SCORED])
    return (f"{second}\n\nThen answer these classification questions about the kind of question. Answer each one independently: yes, no, or unsure. Multiple yes answers are allowed. "
            "Use unsure when you are below about 80% sure of either yes or no. Use no when the text clearly describes a different kind of question. "
            f"Event titles and topic tags provide context, but do not automatically label every market in the event.\n\n{block}\n\n"
            f'The input is one market. Return one JSON line and nothing else, no code fences: {{"id":"<market id>",{fields},"substantive":<integer 0-100>,"yes":[classification question IDs answered yes],"unsure":[classification question IDs answered unsure]}}. '
            '"substantive" answers substantive_world_question as a score: 0 means clearly no, 50 means torn, 100 means clearly yes. Do not list that question in yes or unsure. '
            "Every other classification question you do not list counts as no.\n")


def good(result, market_id):
    r = valid(result, market_id)
    if not r or type(r.get("substantive")) not in (int, float) or not 0 <= r["substantive"] <= 100:
        return None
    return r if all(isinstance(r.get(k), list) and set(r[k]) <= set(TAGS) for k in ("yes", "unsure")) else None


def ask(line, version):
    market_id = json.loads(line)["id"]
    for _ in range(3):
        try:
            answer = claude_call([line], "claude-haiku-5-5", "medium", version, PROMPT)
        except (subprocess.SubprocessError, ValueError, KeyError) as e:
            print(f"{market_id}: {e} {getattr(e, 'stdout', '')[:300]}", flush=True)
            continue
        if good(answer["result"], market_id):
            return answer
        print(f"{market_id}: invalid {answer['result'][:300]}", flush=True)
    return None


def value(a, tag):
    return "yes" if tag in a["yes"] else "unsure" if tag in a["unsure"] else "no"


def world(a):
    return not set(a["yes"]) & set(TAGS) and a["substantive"] > 20


PROMPT.write_text(prompt())
lines = [l.strip() for l in open(SECOND / "full.jsonl")]
sample = random.Random(20261104).sample(lines, N)
version = hashlib.sha256((PROMPT.read_text() + "".join(sample)).encode()).hexdigest()[:8]
done = {json.loads(l)["ids"][0] for l in open(RESULTS)} if RESULTS.exists() else set()
todo = [l for l in sample if json.loads(l)["id"] not in done]
spent = sum(json.loads(l)["cost"] for l in open(RESULTS)) if RESULTS.exists() else 0
print(f"{len(todo)} of {N} left, prompt {len(PROMPT.read_text()):,} characters", flush=True)
with ThreadPoolExecutor(WORKERS) as pool, open(RESULTS, "a") as f:
    for answer in pool.map(lambda l: ask(l, version), todo):
        if answer:
            f.write(json.dumps(answer) + "\n")
            f.flush()
            spent += answer["cost"]
            assert spent < BUDGET, f"stopped at ${spent:.2f}"

calls = list(map(json.loads, open(RESULTS)))
assert {c["input_version"] for c in calls} == {version}
new = {c["ids"][0]: json.loads(c["result"]) for c in calls}
stored = {json.loads(l)["ids"][0]: json.loads(json.loads(l)["result"]) for l in open(SECOND / "full_results.jsonl")}
first = {}
for name in ["manifold_haiku.jsonl", "manifold_haiku_back.jsonl"]:
    first.update(read_calls(ROOT / "manifold/labeling/results/full" / name, need_score=True)[0])
for a in first.values():
    a["substantive"] = 100 if SCORED in a["yes"] else 0 if SCORED not in a["unsure"] else 50

both = [i for i in new if i in stored]
print(f"\n{len(new)} of {N} answered. ${sum(c['cost'] for c in calls) / len(calls):.6f} per market, {sum(c['seconds'] for c in calls) / len(calls):.1f}s per call, "
      f"{sum(c['usage']['claude-haiku-5-5']['thinkingTokens'] for c in calls) / len(calls):.0f} thinking tokens")
print(f"\nSecond-pass questions, same answer as stored, {len(both)} markets (same-prompt reruns gave, of 100):")
for q in [*ANSWERS, "stated_deadline"]:
    same = sum(new[i][q] == stored[i][q] for i in both)
    print(f"  {q:20s}{same:4d} = {same / len(both):.1%}   baseline {STABLE.get(q, 'not measured')}")
print("default_side, stored -> new:", sorted(Counter((stored[i]["default_side"], new[i]["default_side"]) for i in both if stored[i]["default_side"] != new[i]["default_side"]).items()))
for i in both:
    if stored[i]["default_side"] != new[i]["default_side"]:
        print(f"  {stored[i]['default_side']} -> {new[i]['default_side']}: {next(json.loads(l)['question'] for l in sample if json.loads(l)['id'] == i)}")

old = [i for i in new if i in first]
print(f"\nOld questions, same answer as the first Haiku run, {len(old)} markets:")
for t in TAGS:
    print(f"  {t:22s}{sum(value(new[i], t) == value(first[i], t) for i in old):4d}   yes: new {sum(value(new[i], t) == 'yes' for i in old)}, stored {sum(value(first[i], t) == 'yes' for i in old)}")
print(f"  world by these questions: same on {sum(world(new[i]) == world(first[i]) for i in old)} of {len(old)}; new {sum(world(new[i]) for i in old)}, stored {sum(world(first[i]) for i in old)}")
