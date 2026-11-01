# Hand review of Jev's contradictory markets

**Jev's world group looks usable: about 7% of it is garbage. But the 0.8 cutoff is wrong for two of the new tags, and no tag catches some of the empty markets.**

## What we did

Opus 5.5 labeled 600 Manifold markets by hand in one session, about 40 at a time, on all 25 questions, without seeing Jev's answers. The order was shuffled. GPT 6.1 Terra labeled 199 more, also blind, 20 per call, plus 20 of Opus's markets to check agreement. Selection used only Jev's probabilities:

- **222** in Jev's world group with substantive ≤0.2.
- **59** with yes in two conflicting groups.
- **219** (Opus) and **199** (Terra) that Jev called substantive and also ≥0.5 on chance, opinion or not-a-forecast. Opus got the most contradictory ones.
- **100** random markets from Jev's world group, the only sample that says anything about the whole group.

## Results

| Sample | Same group as Opus |
|---|---|
| 100 random world | 93 |
| 222 world, not substantive | 96 |
| 59 two groups | 18 |
| 219 substantive and odd | 195 |

**Garbage in world: 7 of 100** (roughly 3–14%, so we can't yet say it is below Peter's 10% limit). Six are participant markets and one is weather. Most are "Will I..." markets where the creator controls the outcome.

**Jev's substantive ≤0.2 is a clean signal.** Opus scored 204 of those 222 at ≤20. 81 of them stay in world because no tag catches them: "This market resolves YES on March 1", secret markets, empty titles. They are 0.9% of world, so this is small.

**The 0.8 cutoff fails on `status_quo_default`.** On the 100 random markets, Opus says yes on 69 and Jev reaches 0.8 on 7. A cutoff of 0.2 finds 51 of the 69, with 6 false among 57.

**`insider_knowable` and `subjective_resolution` are fine at 0.8.** Insider: 23 flagged, 18 confirmed, 30 total. Subjective: 10 flagged, 7 confirmed, 7 total.

**Jev may miss some existing facts.** On Terra's 199, Terra put 62 in not-a-forecast and Jev only 9. Jev's world holds 536 markets (2%) with `existing_fact` between 0.5 and 0.8.

## How far to trust this

- **These labels aren't the Opus reference.** Opus labeled in batches, and batching pulled Haiku's substantive answers away from single-market ones. Only 1 of the 600 is also in the pilot's Opus run, so we can't measure the difference.
- **Opus's substantive scale here is strict.** It gave 51 of the 100 random markets ≥80 where Jev gave 91, partly because it scored sports around 60. Don't read that gap as Jev's error.
- **Terra and Opus disagree often on hard cases:** same group on 15 of 20, too few to say who is right.
- **The hard samples were chosen for being hard.** Their agreement rates don't describe Jev overall.

## Details

Labels: `labeling/review/opus_labels.txt`, `opus.jsonl`, `terra.jsonl`. Which market came from which sample: `strata.csv`. Rerun: `python src/labeling_review.py score`. Terra ran on high effort through `codex exec`. Selection and analysis are in `src/labeling_review.py`; the cutoff counts above came from a one-off script that isn't committed. The script hasn't had a Sol review.
