"""Hand review of the markets where Jev contradicts itself, plus a random sample of its world group.

python src/labeling_review.py select   -> labeling/review/{strata.csv, opus_input.jsonl, terra_input.jsonl}
python src/labeling_review.py terra n  -> labeling/review/terra.jsonl, GPT 6.1 Terra's answers, n markets per call
python src/labeling_review.py opus     -> labeling/review/opus.jsonl from opus_labels.txt, which Opus 5.5 wrote by hand in a session
python src/labeling_review.py score    -> prints how Jev and Terra compare with Opus
Reviewers never see Jev's answers, and the input files are shuffled so they can't tell the strata apart.
"""
import json, re, subprocess, sys, tempfile
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))  # python -I leaves the script's folder off the path
from labeling_pilot import GROUPS, OUT as PROMPTS, group, questions, read_calls, value

OUT = PROMPTS / "review"
JEV = PROMPTS / "results/full/manifold_jev.jsonl"
INPUT = PROMPTS / "manifold_input.jsonl"
SCORED, YES, NO = "substantive_world_question", 0.8, 0.2
GROUP_TAGS = {name: tags for name, tags in GROUPS}
OPUS, TERRA, RANDOM_WORLD, OVERLAP = 500, 200, 100, 20  # OVERLAP: markets Terra also gets from Opus's set, to measure agreement
SHORT = dict(fc="fixed_chance", cp="crypto_price", scp="short_crypto_price", oa="other_asset_price", sm="sports_match",
             st="sports_tournament", sp="sports_performance", cb="central_bank_rate", sa="sports_award", w="weather_measurement",
             sr="scheduled_release", pw="speech_or_posts", bo="bookmaker_odds", pm="platform_metric", cg="constructed_game",
             ci="creator_influence", ti="trader_influence", sj="subjective_resolution", ef="existing_fact", fe="fermi_estimate",
             pz="puzzle_or_math", op="direct_opinion", sq="status_quo_default", ik="insider_knowable")


def strata():
    rows = []
    for call in map(json.loads, open(JEV)):
        p, top = call["probs"], {name: max(call["probs"][t] for t in tags) for name, tags in GROUPS}
        yes_groups = {name for name, v in top.items() if v >= YES}
        answer = dict(yes=[t for t, v in p.items() if v >= YES])
        odd = max(top["fixed_chance"], top["opinion"], top["not_forecast"])
        rows.append(dict(id=call["ids"][0], substantive=p[SCORED], world=group(answer) == "world",
                         not_substantive_world=p[SCORED] <= NO and not yes_groups,
                         two_groups=len(yes_groups) > 1 and yes_groups != {"traded_elsewhere", "participants"},
                         contradiction=min(p[SCORED], odd) if p[SCORED] >= YES and odd >= 0.5 else 0.0))
    return pd.DataFrame(rows)


def select():
    d = strata().sample(frac=1, random_state=0).reset_index(drop=True)  # breaks ties in contradiction at random
    d["always"] = d.not_substantive_world | d.two_groups
    ranked = d[~d.always & (d.contradiction > 0)].sort_values("contradiction", ascending=False, kind="stable").id.tolist()
    fill = OPUS - d.always.sum()
    d["contradiction_opus"] = d.id.isin(ranked[:fill])
    d["contradiction_terra"] = d.id.isin(ranked[fill:fill + TERRA])
    d["random_world"] = d.id.isin(d[d.world].sample(RANDOM_WORLD, random_state=1).id)
    d["opus"] = d.always | d.contradiction_opus | d.random_world
    d["terra"] = d.contradiction_terra & ~d.opus
    d["overlap"] = d.id.isin(d[d.opus].sample(OVERLAP, random_state=2).id)
    OUT.mkdir(exist_ok=True)
    d[d.opus | d.terra].to_csv(OUT / "strata.csv", index=False)
    lines = {json.loads(l)["id"]: l for l in open(INPUT)}
    (OUT / "opus_input.jsonl").write_text("".join(lines[i] for i in d[d.opus].sample(frac=1, random_state=3).id))
    (OUT / "terra_input.jsonl").write_text("".join(lines[i] for i in d[d.terra | d.overlap].sample(frac=1, random_state=4).id))


def terra(batch):
    """Restart to retry: markets with a valid answer are skipped."""
    path, done = OUT / "terra.jsonl", set()
    if path.exists():
        done = set(read_calls(path, need_score=True)[0])
    left = [l.strip() for l in open(OUT / "terra_input.jsonl") if json.loads(l)["id"] not in done]
    prompt = (PROMPTS / "system_prompt.txt").read_text()
    for i in range(0, len(left), batch):
        chunk = left[i:i + batch]
        with tempfile.TemporaryDirectory() as empty:  # no project instructions in Terra's context
            result = Path(empty) / "out.txt"
            subprocess.run(["codex", "exec", "-m", "gpt-6.1-terra", "-c", "model_reasoning_effort=high", "--sandbox", "read-only",
                            "--ephemeral", "--skip-git-repo-check", "-C", empty, "-o", str(result), "-"],
                           input=prompt + "\nMarkets:\n" + "\n".join(chunk), text=True, check=True, capture_output=True, timeout=1800)
            line = dict(ids=[json.loads(m)["id"] for m in chunk], result=result.read_text(), cost=0)
        with open(path, "a") as f:
            f.write(json.dumps(line) + "\n")
        print(i + len(chunk), "of", len(left), flush=True)


def opus():
    """Each line of opus_labels.txt: <row in opus_input.jsonl> <substantive 0-100> <yes tags> / <unsure tags>."""
    ids = [json.loads(l)["id"] for l in open(OUT / "opus_input.jsonl")]
    rows = [re.match(r"(\d+) (\d+) ?(.*?) ?/ ?(.*)$", l).groups() for l in open(OUT / "opus_labels.txt")]
    assert [int(r[0]) for r in rows] == list(range(len(ids)))
    with open(OUT / "opus.jsonl", "w") as f:
        for n, score, yes, unsure in rows:
            a = dict(id=ids[int(n)], substantive=int(score), yes=[SHORT[t] for t in yes.split()], unsure=[SHORT[t] for t in unsure.split()])
            f.write(json.dumps(dict(ids=[a["id"]], result=json.dumps(a), cost=0)) + "\n")


def jev_answers():
    answers = {}
    for call in map(json.loads, open(JEV)):
        p = call["probs"]
        answers[call["ids"][0]] = dict(yes=[t for t, v in p.items() if v >= YES], unsure=[t for t, v in p.items() if NO < v < YES])
    return answers


def compare(name, reference, other, ids):
    tags = [q for q, _ in questions()]
    same = sum(group(reference[i]) == group(other[i]) for i in ids)
    print(f"\n{name}: {len(ids)} markets, same group {same} ({same / len(ids):.0%})")
    print(pd.crosstab(pd.Series([group(reference[i]) for i in ids], name="reference"), pd.Series([group(other[i]) for i in ids], name="other")))
    rows = [dict(tag=t, ref_yes=sum(value(reference[i], t) == "yes" for i in ids), other_yes=sum(value(other[i], t) == "yes" for i in ids),
                 both_yes=sum(value(reference[i], t) == value(other[i], t) == "yes" for i in ids),
                 same=sum(value(reference[i], t) == value(other[i], t) for i in ids)) for t in tags]
    print(pd.DataFrame(rows).set_index("tag").to_string())


def score():
    d = pd.read_csv(OUT / "strata.csv").set_index("id")
    o, t, j = read_calls(OUT / "opus.jsonl", need_score=True)[0], read_calls(OUT / "terra.jsonl", need_score=True)[0], jev_answers()
    assert len(o) == d.opus.sum()
    compare("Random Jev-world markets, Jev vs Opus", o, j, list(d[d.random_world].index))
    print("substantive by Opus:", pd.cut([o[i]["substantive"] for i in d[d.random_world].index], [-1, 20, 79, 100]).value_counts().to_dict())
    for stratum in ["not_substantive_world", "two_groups", "contradiction_opus"]:
        compare(f"{stratum}, Jev vs Opus", o, j, list(d[d[stratum] & ~d.random_world].index))
    compare("Overlap, Terra vs Opus", o, t, list(d[d.overlap].index))
    compare("Terra's own set, Jev vs Terra", t, j, list(d[d.terra].index))


if __name__ == "__main__":
    dict(select=select, opus=opus, score=score, terra=lambda: terra(int(sys.argv[2])))[sys.argv[1]]()
