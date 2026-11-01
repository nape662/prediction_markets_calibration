"""Pilot of the LLM labelers (notes/classifier_questions.md). Process and choices: notes/labeling_pilot.md.

python src/labeling_pilot.py prepare                       -> labeling/system_prompt.txt, labeling/pilot_sample.jsonl
python src/labeling_pilot.py run <name> <model> <effort> <markets per call> -> labeling/results/<name>.jsonl, one line per call
python src/labeling_pilot.py score <reference> <name>...   -> labeling/results/scores.csv, disagreements.csv

Text lives in labeling/, outside the gitignored data/, because a cloud session only sees what is committed.
Calls go through `claude -p` with no tools and our own system prompt; Claude Code adds only ~150 tokens to it.
Set CLAUDE_BIN to a Claude Code of at least 2.1.280: older ones refuse Opus 5.5 and misprice Haiku 5.5.
"""
import hashlib, json, os, re, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "labeling"
QUESTIONS = ROOT / "notes/classifier_questions.md"
SEED = 0
PER_RULE = 6  # markets from each kind the old sieve caught, so sport and crypto can't fill the sample
MANIFOLD, POLYMARKET = 150, 50
GROUPS = [("opinion", {"direct_opinion"}), ("fixed_chance", {"fixed_chance"}),
          ("not_forecast", {"existing_fact", "fermi_estimate", "puzzle_or_math"}),
          ("traded_elsewhere", {"crypto_price", "short_crypto_price", "other_asset_price", "sports_match", "sports_tournament",
                                "sports_performance", "central_bank_rate", "sports_award", "weather_measurement",
                                "scheduled_release", "speech_or_posts"}),
          ("participants", {"platform_metric", "constructed_game", "creator_influence", "trader_influence"})]


def questions():
    return re.findall(r"^\*\*`(\w+)`\*\*.*?\n\n> (.+)$", QUESTIONS.read_text(), re.M)


def system_prompt():
    blocks = re.findall(r"```text\n(.*?)```", QUESTIONS.read_text(), re.S)
    assert len(blocks) == 2 and len(questions()) == 23, (len(blocks), len(questions()))
    lines = "\n\n".join(f"{q}: {body}" for q, body in questions())
    return f"{blocks[0].strip()}\n\nQuestions:\n\n{lines}\n\n{blocks[1].strip()}\n"


def sample():
    m = pd.read_parquet(ROOT / "data/labeling/manifold.parquet")
    m = m.merge(pd.read_parquet(ROOT / "data/categories/manifold.parquet")[["id", "rule"]], on="id")
    caught = m[m.rule.notna()].groupby("rule").sample(frac=1, random_state=SEED).groupby("rule").head(PER_RULE)
    rest = m[m.rule.isna()].sample(MANIFOLD - len(caught), random_state=SEED)
    t = pd.read_parquet(ROOT / "data/labeling/polymarket_templates.parquet")
    t = t.sample(POLYMARKET, random_state=SEED)  # one row per template, so 17k identical Bitcoin bets count once
    rows = pd.concat([caught, rest, t]).sample(frac=1, random_state=SEED)
    rows["created"] = rows.created.astype(str).str[:10]
    fields = ["id", "platform", "question", "description", "created", "creator", "tags", "event_title", "outcomes"]
    return rows[fields].astype(object).where(rows[fields].notna(), None).to_dict("records")


def prepare():
    OUT.mkdir(exist_ok=True)
    (OUT / "system_prompt.txt").write_text(system_prompt())
    with open(OUT / "pilot_sample.jsonl", "w") as f:
        for r in sample():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def run(name, model, effort, batch):
    markets = [l.strip() for l in open(OUT / "pilot_sample.jsonl")]
    (OUT / "results").mkdir(exist_ok=True)
    version = hashlib.sha256(((OUT / "system_prompt.txt").read_text() + "".join(markets)).encode()).hexdigest()[:8]
    env = {**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}  # otherwise each call adds a paid helper request
    with open(OUT / "results" / f"{name}.jsonl", "w") as f:
        for i in range(0, len(markets), batch):
            chunk = markets[i:i + batch]
            out = subprocess.run([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--model", model, "--effort", effort,
                                  "--output-format", "json", "--no-session-persistence", "--tools", "", "--strict-mcp-config",
                                  "--setting-sources", "", "--system-prompt-file", str(OUT / "system_prompt.txt")],
                                 input="\n".join(chunk), capture_output=True, text=True, check=True, env=env)
            d = json.loads(out.stdout)
            f.write(json.dumps(dict(input_version=version, ids=[json.loads(m)["id"] for m in chunk], result=d["result"], cost=d["total_cost_usd"],
                                    usage=d["modelUsage"], seconds=d["duration_ms"] / 1000)) + "\n")
            f.flush()


def valid(answer, call, seen, tags):
    return (isinstance(answer, dict) and answer.get("id") in call["ids"] and answer["id"] not in seen
            and all(isinstance(answer.get(k), list) and set(answer[k]) <= tags for k in ("yes", "unsure")))


def load(name):
    """id -> answer, the number of invalid output lines, cost per market sent, input version.
    An invalid answer stays missing; it never turns into "no"."""
    answers, bad, cost, sent, versions = {}, 0, 0, 0, set()
    tags = {q for q, _ in questions()}
    for call in map(json.loads, open(OUT / "results" / f"{name}.jsonl")):
        cost += call["cost"]
        sent += len(call["ids"])
        versions.add(call.get("input_version"))
        for line in re.sub(r"```(json)?", "", call["result"]).splitlines():
            if line.strip():
                try:
                    a = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if isinstance(a, dict) and "unknown" in a:  # runs saved before the answer was renamed to "unsure"
                    a["unsure"] = a.pop("unknown")
                if valid(a, call, answers, tags):
                    answers[a["id"]] = a
                else:
                    bad += 1
    return answers, bad, cost / sent, versions


def value(answer, tag):
    return "yes" if tag in answer["yes"] else "unsure" if tag in answer["unsure"] else "no"


def group(answer):
    """Plot group, first match wins (notes/classifier_questions.md). "unsure" counts as not yes."""
    yes = set(answer["yes"])
    for name, tags in GROUPS:
        if yes & tags:
            return name
    return "world"


def score(reference, names):
    tags = [q for q, _ in questions() if q != "junk_reason"]
    ids = {m["id"]: m for m in map(json.loads, open(OUT / "pilot_sample.jsonl"))}
    runs = {n: load(n) for n in [reference, *names]}
    summary, rows = [], []
    for n, (answers, bad, cost, versions) in runs.items():
        both = [i for i in ids if i in answers and i in runs[reference][0]]
        row = dict(run=n, input_version=" ".join(map(str, versions)), usd_per_market=cost, markets_answered=len(answers),
                   markets_compared=len(both), bad_lines=bad)
        row["markets_fully_agree"] = sum(all(value(answers[i], t) == value(runs[reference][0][i], t) for t in tags) for i in both)
        for t in tags:
            row[f"yes_{t}"] = sum(value(answers[i], t) == "yes" for i in answers)
            row[f"differs_{t}"] = sum(value(answers[i], t) != value(runs[reference][0][i], t) for i in both)
        summary.append(row)
    pd.DataFrame(summary).set_index("run").T.to_csv(OUT / "results" / "scores.csv")
    for i, m in ids.items():
        for t in tags:
            vals = {n: value(a[i], t) if i in a else "MISSING" for n, (a, *_) in runs.items()}
            if len(set(vals.values())) > 1:
                rows.append(dict(id=i, platform=m["platform"], question=m["question"], tag=t, **vals))
    pd.DataFrame(rows).to_csv(OUT / "results" / "disagreements.csv", index=False)
    groups = pd.DataFrame([dict(id=i, platform=m["platform"], question=m["question"],
                                **{n: group(a[i]) if i in a else "MISSING" for n, (a, *_) in runs.items()}) for i, m in ids.items()])
    groups.to_csv(OUT / "results" / "groups.csv", index=False)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    else:
        score(sys.argv[2], sys.argv[3:])
