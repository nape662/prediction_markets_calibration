"""Build the text the LLM labelers will see (notes/classifier_questions.md).

python src/labeling_input.py -> data/labeling/
  manifold.parquet              one row per market (37,680)
  polymarket_markets.parquet    market id -> template, for markets closed before Becker's trades end
  polymarket_templates.parquet  one representative market per question template (what gets labeled)

Descriptions are cleaned of text written after creation (Manifold's dated "Update ..." blocks, "Update:/EDIT:" lines,
"(resolved NO)"-style notes). Only the creation date is kept: close and resolution times would hint at the outcome.
"""
import json, re
from pathlib import Path
import pandas as pd

DATA = Path(__file__).resolve().parents[1] / "data"
OUT = DATA / "labeling"
BECKER_END = "2026-02-02T18:27:46Z"  # last block in Becker's Polymarket trades
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
DAYS = "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday"
# Text added after creation is usually appended at the end, so everything from its first marker on is dropped:
# Manifold's "Update 2026-03-25 (PST)" blocks, "UPDATE:/EDIT:" headings, "Resolving YES", "Feb 21, 11:35am:" timestamps.
LATER = re.compile(rf"Update \d{{4}}-\d{{2}}-\d{{2}}|^\W*(update|edit|upd|eta)\b|^\W*(resolving|resolved)( to| as)? (yes|no|n/?a)\b"
                   rf"|^\W*({MONTHS})\.? \d{{1,2}}(,? \d{{4}})?,? \d{{1,2}}(:\d{{2}})?\s*(am|pm)?\s*:", re.I | re.M)
LEAK_LINE = re.compile(r"\((already )?resolved( to)? (yes|no|n/?a)\)|\b(it|this( market| question)?) (has )?resolved( to| as)? (yes|no|n/?a)\b"
                       r"|\bthe resolution is (yes|no|n/?a)\b", re.I)


def clean(text):
    text = LATER.split(text or "", maxsplit=1)[0]
    text = "\n".join(l for l in text.splitlines() if not LEAK_LINE.search(l))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def utc(t):
    return pd.to_datetime(t, utc=True) if t else pd.NaT


def template(question):
    t = re.sub(rf"\b({MONTHS}|{DAYS})\b\.?", "@", question)  # case-sensitive, so the verb "may" survives
    t = re.sub(r"[$€£]?\d[\d,]*(\.\d+)?(\s?(k|m|b|bn)\b|%|¢|(st|nd|rd|th|am|pm)\b)?", "#", t.lower())
    t = re.sub(r"\$(?=[a-z])", "", t)  # "$BTC" = "BTC"
    t = re.sub(r"@ #(,? #)?", "@", t)  # "May 3" = "May 3, 2025"
    return re.sub(r"\s+", " ", t).strip()


def manifold():
    rows = [json.loads(l) for l in open(DATA / "manifold/api/full.jsonl")]
    pd.DataFrame(dict(
        id=[m["id"] for m in rows], platform="Manifold", question=[m["question"] for m in rows],
        description=[clean(m.get("textDescription")) for m in rows],
        created=pd.to_datetime([m["createdTime"] for m in rows], unit="ms", utc=True),
        creator=[m["creatorUsername"] for m in rows], tags=[" ".join(m.get("groupSlugs") or []) for m in rows],
    )).to_parquet(OUT / "manifold.parquet", index=False)
    print(f"manifold: {len(rows):,} markets")


def polymarket():
    templates, markets, reps, n = {}, [], [], 0
    for line in open(DATA / "polymarket/api/markets.jsonl"):
        n += 1
        m = json.loads(line)
        if not m.get("closedTime") or utc(m["closedTime"]) >= utc(BECKER_END):
            continue
        e = (m.get("events") or [{}])[0]
        # the scheduled length goes into the key so "ETH above $X on <date>" over 16 hours and over a month aren't merged
        days = (utc(m.get("endDate")) - utc(m.get("createdAt"))).days
        key = (template(m["question"] or e.get("title") or ""), "?" if pd.isna(days) else min(days, 7) if days < 30 else 30)
        if key not in templates:
            templates[key] = [len(templates), 0]
            reps.append(dict(template=templates[key][0], id=m["id"], platform="Polymarket", question=m["question"],
                             event_title=e.get("title"), outcomes=m.get("outcomes"), description=clean(m.get("description")),
                             created=m.get("createdAt"), tags=" ".join(t.get("label", "") for t in m.get("tags") or [])))
        templates[key][1] += 1
        markets.append((m["id"], templates[key][0], e.get("id"), m.get("createdAt"), m["closedTime"], m.get("endDate"),
                        float(m.get("volumeNum") or 0), bool(e.get("negRisk"))))
        if n % 500_000 == 0:
            print(f"read {n:,}, kept {len(markets):,}, templates {len(templates):,}", flush=True)
    cols = ["id", "template", "event_id", "created", "closed_time", "end_date", "volume", "neg_risk"]
    pd.DataFrame(markets, columns=cols).to_parquet(OUT / "polymarket_markets.parquet", index=False)
    reps = pd.DataFrame(reps)
    reps["n_markets"] = reps.template.map({i: c for i, c in templates.values()})
    reps.to_parquet(OUT / "polymarket_templates.parquet", index=False)
    print(f"polymarket: read {n:,}, kept {len(markets):,} closed before {BECKER_END}, {len(reps):,} templates")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    manifold()
    polymarket()
