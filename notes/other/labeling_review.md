# Hand review of Jev's contradictory markets

**The 0.8 cutoff is wrong for `status_quo_default`, and this review doesn't measure how much garbage is in Jev's world group. Because of what it found, the "participants" group is gone: world now excludes only markets with substantive `no`, and holds 27,840 markets on Jev's labels instead of 25,949. With the reviewers' answers merged in, it holds 27,752.**

## What we did

Opus 5.5 labeled 600 Manifold markets by hand in one session, about 40 at a time, on all 25 questions, without seeing Jev's answers. The order was shuffled. GPT 6.1 Terra labeled 199 more, also blind, 20 per call, plus 20 of Opus's markets to check agreement. Selection used only Jev's probabilities:

- **222** in Jev's world group with substantive ≤0.2.
- **59** with yes in two conflicting groups.
- **219** (Opus) and **199** (Terra) that Jev called substantive and also ≥0.5 on chance, opinion or not-a-forecast. Opus got the most contradictory ones.
- **100** random markets from Jev's world group, the only sample that says anything about the whole group.

## Results

| Sample | Same group as Opus |
|---|---|
| 100 random world | 90 |
| 222 world, not substantive | 189 |
| 59 two groups | 18 |
| 219 substantive and odd | 195 |

**An earlier version of this report was wrong.** Under the old groups, 7 of the 100 random markets left world, and it called them garbage. Six carried participant tags and one was weather, and influence on the outcome doesn't make a question unsubstantive. Opus scored five of the seven at ≥55, for example "Will I have a convincing video call with a fully synthetic AI avatar before July 2025?" at 80. Peter deleted the group as a result. The four tags stay saved for later queries and aren't used for now.

**We have no direct measure of garbage yet.** The closest number: Opus scored 9 of the 100 at ≤20, and 5 of those are about the streamer Destiny, which is niche rather than junk. The other difference is the weather market. The 100 were drawn from the old world group, so the 2,113 markets that just joined world haven't been sampled.

**Jev's substantive ≤0.2 is a clean signal.** Opus scored 204 of those 222 at ≤20. They include markets no tag catches: "This market resolves YES on March 1", secret markets, empty titles. The new rule removes these, 1,141 markets in all.

**The 0.8 cutoff fails on `status_quo_default`.** On the 100 random markets, Opus says yes on 69 and Jev reaches 0.8 on 7. A cutoff of 0.2 finds 51 of the 69, with 6 false among 57.

**`insider_knowable` and `subjective_resolution` are fine at 0.8.** Insider: 23 flagged, 18 confirmed, 30 total. Subjective: 10 flagged, 7 confirmed, 7 total.

**Jev may miss some existing facts.** On Terra's 199, Terra put 62 in not-a-forecast and Jev only 9. Jev's world holds 536 markets (2%) with `existing_fact` between 0.5 and 0.8.

## Second round and the merged labels

Opus and Terra then labeled the remaining 316 contradictory markets, 158 each, split at random, plus 20 more shared markets. **`manifold/labeling/results/full/manifold_final.jsonl` now holds one answer per market:** Opus's on 758, Terra's on 357 and Jev's on the other 36,565. Opus wins where both labeled. Each row records its source, so the merge can be undone.

| Group | Jev alone | Merged |
|---|---|---|
| world | 27,840 | 27,752 |
| traded_elsewhere | 7,750 | 7,782 |
| not_substantive | 1,141 | 1,146 |
| fixed_chance | 567 | 571 |
| not_forecast | 345 | 391 |
| opinion | 37 | 38 |

The merge changes the group of 245 markets. The main effect is real: Jev misses existing facts. In this round Opus moved 32 of its 158 from Jev's world to not-a-forecast, and Terra moved 19 of its 158. Only markets Jev scored ≥0.8 on substantive were checked for this, so more of these probably remain in world.

## How far to trust this

- **Reviewed markets follow a different labeler from the rest.** Merging fixes these 1,115 markets, but it doesn't make world's unreviewed markets as clean. The 100 random world markets were also relabeled, so 9 of them moved to not_substantive under Opus's strict scale, 5 about the streamer Destiny. That breaks Peter's rule that niche isn't junk, and they stay there until someone rescores them.

- **These labels aren't the Opus reference.** Opus labeled in batches, and batching pulled Haiku's substantive answers away from single-market ones. Only 1 of the 600 is also in the pilot's Opus run, so we can't measure the difference.
- **Opus's substantive scale here is strict.** It gave 51 of the 100 random markets ≥80 where Jev gave 91, partly because it scored sports around 60. Don't read that gap as Jev's error.
- **Terra and Opus disagree often on hard cases:** same group on 29 of 40, too few to say who is right.
- **The hard samples were chosen for being hard.** Their agreement rates don't describe Jev overall.

## Details

Labels: `manifold/other/labeling_review/opus_labels.txt`, `opus.jsonl`, `terra.jsonl`. Which market came from which sample: `strata.csv`. Rerun: `python manifold/other/labeling_review.py score`. Terra ran on high effort through `codex exec`. Selection and analysis are in `manifold/other/labeling_review.py`; the cutoff counts above came from a one-off script that isn't committed. Sol reviewed the merge code on high and found no bugs. Rerun the merge: `python manifold/other/labeling_review.py final`.
