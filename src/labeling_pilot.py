"""Pilot of the LLM labelers (notes/classifier_questions.md). Process and choices: notes/other/labeling_pilot.md.

python src/labeling_pilot.py prepare                       -> manifold/labeling/system_prompt.txt, manifold/labeling/pilot_sample.jsonl
python src/labeling_pilot.py run <name> <model> <effort> <markets per call> -> manifold/labeling/results/<name>.jsonl, one line per call
python src/labeling_pilot.py jev <name>                     -> the same on TypeSafe's Jev, with its raw probabilities
python src/labeling_pilot.py score <reference> <name>...   -> manifold/labeling/results/scores.csv, disagreements.csv, groups.csv
PILOT_SEED=1 before any of these uses a second sample, disjoint from the first, with results in manifold/labeling/results/seed1/.

Text lives in manifold/labeling/, outside the gitignored data/, because a cloud session only sees what is committed.
Calls go through `claude -p` with no tools and our own system prompt; Claude Code adds only ~150 tokens to it.
Set CLAUDE_BIN to a Claude Code of at least 2.1.280: older ones refuse Opus 5.5 and misprice Haiku 5.5.
"""
import hashlib, http.client, json, os, re, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manifold/labeling"
QUESTIONS = ROOT / "notes/classifier_questions.md"
SEED = int(os.environ.get("PILOT_SEED", 0))
SAMPLE = OUT / f"pilot_sample{SEED or ''}.jsonl"
RESULTS = OUT / "results" / (f"seed{SEED}" if SEED else "")
JEV_PRICE = 0.042 / 1e6  # USD per input token; output is free
JEV_YES, JEV_NO = 0.8, 0.2  # between them is "unsure", as in the prompt's "below about 80% sure"; also cuts Haiku's 0-100 score
SCORED = "substantive_world_question"  # Haiku answers this one with a score
FIELDS = ["id", "platform", "question", "description", "created", "creator", "tags", "event_title", "outcomes"]
PER_RULE = 6  # markets from each kind the old sieve caught, so sport and crypto can't fill the sample
MANIFOLD, POLYMARKET = 150, 50
GROUPS = [("opinion", {"direct_opinion"}), ("fixed_chance", {"fixed_chance"}),
          ("not_forecast", {"existing_fact", "fermi_estimate", "puzzle_or_math"}),
          ("traded_elsewhere", {"crypto_price", "short_crypto_price", "other_asset_price", "sports_match", "sports_tournament",
                                "sports_performance", "central_bank_rate", "sports_award", "weather_measurement",
                                "scheduled_release", "speech_or_posts"})]


def questions():
    return re.findall(r"^\*\*`(\w+)`\*\*.*?\n\n> (.+)$", QUESTIONS.read_text(), re.M)


def system_prompt():
    blocks = re.findall(r"```text\n(.*?)```", QUESTIONS.read_text(), re.S)
    assert len(blocks) == 2 and len(questions()) == 25, (len(blocks), len(questions()))
    lines = "\n\n".join(f"{q}: {body}" for q, body in questions())
    return f"{blocks[0].strip()}\n\nQuestions:\n\n{lines}\n\n{blocks[1].strip()}\n"


def sample():
    m = pd.read_parquet(ROOT / "data/labeling/manifold.parquet")
    m = m.merge(pd.read_parquet(ROOT / "data/categories/manifold.parquet")[["id", "rule"]], on="id")
    seen = {json.loads(l)["id"] for l in open(OUT / "pilot_sample.jsonl")} if SEED else set()
    m = m[~m.id.isin(seen)]
    caught = m[m.rule.notna()].groupby("rule").sample(frac=1, random_state=SEED).groupby("rule").head(PER_RULE)
    rest = m[m.rule.isna()].sample(MANIFOLD - len(caught), random_state=SEED)
    t = pd.read_parquet(ROOT / "data/labeling/polymarket_templates.parquet")
    t = t[~t.id.isin(seen)].sample(POLYMARKET, random_state=SEED)  # one row per template, so 17k identical Bitcoin bets count once
    rows = pd.concat([caught, rest, t]).sample(frac=1, random_state=SEED)
    rows["created"] = rows.created.astype(str).str[:10]
    return rows[FIELDS].astype(object).where(rows[FIELDS].notna(), None).to_dict("records")


def prepare():
    OUT.mkdir(exist_ok=True)
    (OUT / "system_prompt.txt").write_text(system_prompt())
    with open(SAMPLE, "w") as f:
        for r in sample():
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def claude_call(markets, model, effort, version, prompt=OUT / "system_prompt.txt"):
    env = {**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",  # otherwise each call adds a paid helper request
           "FORCE_PROMPT_CACHING_5M": "1"}  # market text is never read back, so its cache write should cost 1.25x, not 2x
    out = subprocess.run([os.environ.get("CLAUDE_BIN", "claude"), "-p", "--model", model, "--effort", effort,
                          "--output-format", "json", "--no-session-persistence", "--tools", "", "--strict-mcp-config",
                          "--setting-sources", "", "--system-prompt-file", str(prompt)],
                         input="\n".join(markets), capture_output=True, text=True, check=True, env=env, timeout=900)
    d = json.loads(out.stdout)
    if d["is_error"]:
        raise subprocess.CalledProcessError(1, "claude", out.stdout, out.stderr)
    return dict(input_version=version, ids=[json.loads(m)["id"] for m in markets], result=d["result"], cost=d["total_cost_usd"],
                usage=d["modelUsage"], seconds=d["duration_ms"] / 1000)


def run(name, model, effort, batch):
    markets = [l.strip() for l in open(SAMPLE)]
    RESULTS.mkdir(parents=True, exist_ok=True)
    version = hashlib.sha256(((OUT / "system_prompt.txt").read_text() + "".join(markets)).encode()).hexdigest()[:8]
    with open(RESULTS / f"{name}.jsonl", "w") as f:
        for i in range(0, len(markets), batch):
            f.write(json.dumps(claude_call(markets[i:i + batch], model, effort, version)) + "\n")
            f.flush()


def jev_request(body, key):
    request = urllib.request.Request("https://api.typesafe.ai/v1/systemone", json.dumps(body).encode(),
                                     {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    for wait in (1, 5, 30, 120, None):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if (e.code != 429 and e.code < 500) or wait is None:  # rate limits and server errors pass; an empty balance doesn't
                raise
        except (OSError, http.client.HTTPException, ValueError):  # dropped connections, cut or garbled replies
            if wait is None:
                raise
        time.sleep(wait)


def jev_setup():
    """Jev can't answer "unsure", so its text drops the sentences that mention it."""
    drop = lambda text: re.sub(r"[^.\n]*\bunsure\b[^.\n]*\.", "", re.sub(r"; answer unsure[^.]*", "", text))
    intro = drop(re.findall(r"```text\n(.*?)```", QUESTIONS.read_text(), re.S)[0]).strip()
    asked = {q: dict(type="noul", instructions=drop(text)) for q, text in questions()}
    key = Path("~/.config/jev_key").expanduser().read_text().strip()
    return intro, asked, key, hashlib.sha256((json.dumps(asked) + intro).encode()).hexdigest()[:8]


def jev_call(market, intro, asked, key, version):
    """All tags in one request per market: Jev bills the state once and the docs mention no prompt cache."""
    market = json.loads(market)
    d = jev_request(dict(model="jev-latest", state=dict(instructions=intro, market=market), questions=asked), key)
    probs = {q: a["noul"] for q, a in d["answers"].items()}
    assert probs.keys() == asked.keys() and all(0 <= p <= 1 for p in probs.values()), d  # a missing answer must not become "no"
    answer = dict(id=market["id"], yes=[q for q, p in probs.items() if p >= JEV_YES],
                  unsure=[q for q, p in probs.items() if JEV_NO < p < JEV_YES])
    return dict(input_version=version, ids=[market["id"]], result=json.dumps(answer), probs=probs, model=d["model"],
                cost=d["usage"]["input_tokens"] * JEV_PRICE, usage=d["usage"])


def jev(name):
    setup = jev_setup()
    RESULTS.mkdir(parents=True, exist_ok=True)
    with open(RESULTS / f"{name}.jsonl", "w") as f:
        for market in open(SAMPLE):
            f.write(json.dumps(jev_call(market, *setup)) + "\n")
            f.flush()


def valid(answer, call, seen, tags, need_score):
    if not (isinstance(answer, dict) and answer.get("id") in call["ids"] and answer["id"] not in seen
            and all(isinstance(answer.get(k), list) and all(isinstance(t, str) and t in tags for t in answer[k]) for k in ("yes", "unsure"))):
        return False
    score = answer.get("substantive")
    return score is None and not need_score or type(score) in (int, float) and 0 <= score <= 100


def load(name):
    return read_calls(RESULTS / f"{name}.jsonl")


def read_calls(path, need_score=False):
    """id -> answer, the number of invalid output lines, cost per market sent, input versions.
    An invalid answer stays missing; it never turns into "no"."""
    answers, bad, cost, sent, versions = {}, 0, 0, 0, set()
    tags = {q for q, _ in questions()}
    for call in map(json.loads, open(path)):
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
                if valid(a, call, answers, tags, need_score):
                    if "substantive" in a:
                        p = a["substantive"] / 100
                        a["yes"] = [t for t in a["yes"] if t != SCORED] + [SCORED] * (p >= JEV_YES)
                        a["unsure"] = [t for t in a["unsure"] if t != SCORED] + [SCORED] * (JEV_NO < p < JEV_YES)
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
    return "not_substantive" if value(answer, SCORED) == "no" else "world"


def score(reference, names):
    tags = [q for q, _ in questions()]
    ids = {m["id"]: m for m in map(json.loads, open(SAMPLE))}
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
    pd.DataFrame(summary).set_index("run").T.to_csv(RESULTS / "scores.csv")
    for i, m in ids.items():
        for t in tags:
            vals = {n: value(a[i], t) if i in a else "MISSING" for n, (a, *_) in runs.items()}
            if len(set(vals.values())) > 1:
                rows.append(dict(id=i, platform=m["platform"], question=m["question"], tag=t, **vals))
    pd.DataFrame(rows).to_csv(RESULTS / "disagreements.csv", index=False)
    groups = pd.DataFrame([dict(id=i, platform=m["platform"], question=m["question"],
                                **{n: group(a[i]) if i in a else "MISSING" for n, (a, *_) in runs.items()}) for i, m in ids.items()])
    groups.to_csv(RESULTS / "groups.csv", index=False)


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "run":
        run(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]))
    elif sys.argv[1] == "jev":
        jev(sys.argv[2])
    else:
        score(sys.argv[2], sys.argv[3:])
