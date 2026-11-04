# Manifold calibration: full findings reference

This is a source document for writing a paper or post. It is deliberately long and repetitive. It is not itself a draft. Every number comes from the files named in section 19. Written 2026-11-04.

**Evidence tags used below:**
- **[measured]** computed from the data in this repo.
- **[reasoned]** an argument I believe, not tested.
- **[from note]** copied from an older note, and not recomputed today.
- **[web]** found online, not checked against our data.

**Which numbers are current.** All tables here use the bettor counts as fixed on 2026-11-04 (section 16, first item). `notes/yes_bias_debug.md` and `notes/second_pass_results.md` still quote the old counts. The gaps differ by at most about 0.2 points. When they disagree, use this file.

**Sample sizes differ slightly between tables, for a known reason.** The re-sorted analysis (`second_pass_analysis.py`) also requires the market to be still open at the snapshot, giving 9,762 world markets at 1 week. The older analysis (`yes_bias.py`) and overall calibration don't, giving 9,913. Section 3 shows the steps.

---

## 1. The answer in one page

**The question of the project:** do Manifold probabilities match how often things happen, on real questions about the world rather than mass-produced gambling?

**The answer:** Manifold closely tracks the truth, apart from a small YES bias.

- **Prices carry a lot of information.** One week after creation, the world-market Brier score is 0.148, against 0.219 for always guessing the base rate. One day before resolution it is 0.049 against 0.223. [measured]
- **The bias is real, and small next to that information.** One week after creation, the mean price is 39.9% and 32.3% resolve YES, a gap of 7.6 points. A correction learned from older markets improves Brier by only 0.004 to 0.009. [measured]
- **Nearly all of the bias belongs to one kind of question.** Where nothing happening means NO, markets are priced 36.3% and resolve YES 26.8% of the time. These are 79% of markets and 97% of the gap. [measured]
- **The sign flips with the meaning of YES.** Where nothing happening means YES, markets are priced 69.7% and resolve YES 76.6%, on 534 markets. So this isn't a bias toward the word YES. It's a bias toward "something happens". [measured]
- **It isn't a counting bug.** Coin-flip markets are exact: priced 49.9%, resolved 49.9% on 475 markets. Stale prices, closed markets, fetch rules and dropped resolutions each move the result very little. [measured]
- **Close to resolution the picture reverses, and this is mostly not real.** One day before resolution, markets where only YES can finish early look underpriced. Picking the moment from the resolution date selects on the outcome. A perfectly calibrated market would show this too. [measured pattern, reasoned cause]
- **Far from resolution, the overpricing is largest.** A year before resolution, "nothing means NO" markets are priced 31.1% and resolve YES 17.5%, on 3,063 markets. [measured]
- **I don't know why it exists.** Early finish, niche questions and news prompts don't account for it. Time left and outside references are partial leads. [measured]
- **Polymarket: no claim yet.** Only a rough text-rule comparison exists (section 13). The labeling hasn't been run there.

**How large is "small"?** Both framings are true, and a paper should give both. By information it's small: the fix barely changes Brier. By price it isn't negligible on the affected side: at 1 week, those priced 40–50% resolve YES 34.7% of the time, and at 1 year before resolution, those priced 70–80% resolve YES 47% of the time (168 markets).

---

## 2. Data

**Manifold** [measured]
- Source: Manifold's public API, fetched by 2026-10-30. Stored in `data/manifold/api/` (`markets.jsonl`, `full.jsonl`, one bets file per market). Gitignored.
- **Fetch gate:** resolved binary YES/NO markets with at least 15 lifetime bettors and at least 1,000 lifetime mana of volume: **37,680 markets**. This gate uses the future, because lifetime counts include trades after any snapshot.
- Excluded by the gate, and checked in section 12: markets still open at fetch (a separate fetch found them), N/A and percent resolutions, and low-volume markets.

**Plot groups from the first labeling pass** (`labeling/results/full/manifold_final.jsonl`, section 4):

| Group | Markets (merged labels) | Meaning |
|---|---|---|
| world | 27,752 (27,748 with second-pass labels) | The main sample: everything not caught below |
| traded_elsewhere | 7,782 | Sport, prices, weather, scheduled numbers |
| not_substantive | 1,146 | Games about the market, empty questions |
| fixed_chance | 571 | Coin flips, dice, lotteries |
| not_forecast | 391 | Existing facts and similar |
| opinion | 38 | Direct opinion polls |

**Polymarket** [measured]
- Becker on-chain trades dataset (`data/becker/`), with data ending in February 2026. Same text rule as Manifold. Outside sport and crypto. Covers on-chain trades, not order books or midpoints.
- 2,024 by-date markets created 2023–2025 at the 1-week snapshot with 15+ takers and $1,000+.

**Hand-made data** in `labeling/review/yes_bias/`
- `polarity_hand.csv`: 514 titles labeled by me, without prices or outcomes, 302 of them "YES means no change". I may remember how famous events ended.
- `pairs_hand.csv`: 142 same-event Manifold/Polymarket pairs, with same_rules, copied and rule_similarity. 8 dropped because rules differ.
- `resolution_audit.csv`: 90 resolutions read by hand, which necessarily saw outcomes.

---

## 3. How a market gets into a plot

**A snapshot** (`src/snapshots.py`) is the `probAfter` of the last non-redemption bet that moved the price, at or before a moment. Each market counts once per panel.

- **After creation:** moment = creation + horizon, and the market must be unresolved then. Traders can see that a market is unresolved, so this doesn't depend on the outcome.
- **Before resolution:** moment = resolution − horizon. Which moment a market gets depends on when its outcome arrived. See section 7.
- **Horizons:** 12h, 1d, 1w, 1m (30 days), 3m (91), 6m (182), 1y (365).
- **15+ bettors by then:** distinct users with a nonzero fill at or before the snapshot. It uses no future information.

**Why only about 10,000 of 27,748 world markets appear at 1 week** [measured]

| Step, 1 week after creation | World markets |
|---|---|
| Labeled world markets | 27,748 |
| Unresolved and with a price at 1 week | 24,868 |
| 15+ bettors by that moment (old count 10,085) | 9,911 |
| Still open at that moment | 9,762 |

All 27,748 reach 15 bettors eventually, but most need more than a week. Before resolution has more markets, because by then most have their bettors: 24,972 at 1 day before, 21,375 at 1 week, 16,404 at 1 month, 11,699 at 3 months, 8,536 at 6 months and 3,805 at 1 year. **So the after-creation and before-resolution plots compare different sets of markets.**

**Before-resolution plots keep markets already closed at that moment,** at their last price. The "still open" filter is outcome-dependent there, because NO markets often sit closed waiting for the creator (section 7).

---

## 4. Labels

**Principle.** Labels are independent tags from text only. Models see no price, outcome, close date or resolution date. Close dates are withheld because Manifold overwrites them on early resolution, and early resolution leans YES.

**First pass** [from note: `notes/labeling_pilot.md`, `notes/labeling_review.md`]
- 25 yes/no/unsure questions, full text in `notes/classifier_questions.md`.
- Jev on all markets, Haiku 5.5 medium in a cloud session, and hand labels by Opus 5.5 (758) and GPT 6.1 Terra (357) on contradictory or sampled markets.
- `manifold_final.jsonl` holds one answer per market: Opus on 758, Terra on 357 and Jev on 36,565. Haiku isn't merged into it.
- Opus at high effort is treated as the reference. No human gold labels exist, so agreement shows models copy Opus, not that either is right.
- Direct measure of garbage in world: none. Closest: Opus scored 9 of 100 random world markets at ≤20 on "substantive", and 5 of those are about one streamer, which is niche rather than junk.
- Jev under-detects existing facts. More may remain in world.
- Old label `status_quo_default` was broken for this question: it doesn't say which side wins by default. "Status quo vs other" is not a useful split.

**Second pass** (`labeling/second_pass/`, `src/labeling_second.py`)
- Haiku 5.5, medium effort, one market per call, in a cloud session using `claude -p`. Ran 2026-11-03, about 5 hours.
- **37,672 of 37,680 labeled, $19.19 at list price.** All one prompt version.
- Of the 8 missing, 4 are rot13 "planecrash" titles whose calls failed, and 4 returned the invalid `early_side: NONE`. The cloud session's note says all 8 were refusals, which is wrong for at least those 4. 3 of the 8 fall in the 1-week sample.
- Tags containing `new-year` were removed from the input, because that tag depends on the outcome (section 11).

**The questions, verbatim from `system_prompt.txt`:**

> **default_side:** If nothing new happens and the current state of affairs simply continues until the deadline, how does this market resolve? Answer YES, NO, or NONE. Answer NONE when the outcome is decided by a scheduled event, measurement or decision that will happen anyway, such as an election, a vote count or an award. Examples: "Will X launch by June?" is NO. "Will X still be CEO at year end?" is YES. "Will X win the election?" is NONE.
>
> **outside_reference:** When this market was created, could a careful person find a directly relevant forecast or number for this exact event elsewhere: another prediction market, bookmaker odds, a poll, an official schedule or a published expert forecast? Answer yes, no or unsure. Judge the kind of event and do not invent sources.
>
> **stated_deadline:** What is the last date by which this question must be decided, according to its text? Answer an ISO date (YYYY-MM-DD), or null if none is stated. Use the end of the named period for "in 2025" or "by March". Do not use the market's creation date or any date not in the text.
>
> **early_side:** Can one outcome become certain well before the deadline while the other must wait? Answer YES_EARLY if a YES outcome can be established early while NO must wait, NO_EARLY if the reverse, BOTH if either can, NEITHER if the answer only arrives at one scheduled moment. Examples: "Will X happen by June?" is YES_EARLY. "Will X still be CEO at year end?" is NO_EARLY. "Will X win the election?" with no early exit in view is NEITHER.
>
> **early_path:** Is that early finish a normal way for this question to end, or does it need an unrelated shock such as the death of a named person? Answer NORMAL, SHOCK or NONE. Ignore how likely the event itself is: "Will X be impeached by August?" is NORMAL even if impeachment is unlikely, because the event happening is what ends it early. NONE goes with NEITHER. Example: "Will Biden be the next president?" is early_side NO_EARLY, early_path SHOCK.
>
> **general_interest:** Would most well-informed news readers recognize the subject of this question without knowing the community it comes from? Answer no for a streamer's drama, one forecaster's personal life or a prediction-site feature. Answer yes, no or unsure.
>
> **prompted_by_news:** Does the text show the question was prompted by a specific recent news item, rumor, announcement or statement? Answer yes, no or unsure.

An earlier `early_likelihood` wording was dropped because Haiku rated how unlikely the event was rather than how freakish the path was. 37 of 38 changed answers moved to NORMAL. So "how surprising is the early finish" is asked only as normal path vs. unrelated shock.

**Answer counts, all 37,672 markets:**

| Question | Answers |
|---|---|
| default_side | NO 23,963; NONE 11,872; YES 1,837 |
| early_side | YES_EARLY 22,197; NEITHER 11,193; NO_EARLY 2,784; BOTH 1,498 |
| early_path | NORMAL 25,774; NONE 11,245; SHOCK 653 |
| outside_reference | yes 14,709; no 14,145; unsure 8,818 |
| general_interest | yes 22,761; no 11,611; unsure 3,300 |
| prompted_by_news | no 25,605; yes 8,389; unsure 3,678 |
| stated_deadline | given on 26,390 |

**How much to trust them** [measured]
- **Rerun stability, 100 markets, same answer:** default_side 96, early_side 96, general_interest 94, stated_deadline 93, prompted_by_news 86, outside_reference 71. Treat `outside_reference` only as a lead.
- **default_side against my 514 hand labels:** of 302 hand YES-default, Haiku said YES on 284, NONE on 10, NO on 8. Of 212 others, it said NO on 140, NONE on 47, YES on 25.
- **stated_deadline against an unambiguous title date:** within a day on 97.0% of 4,130 markets. 116 give no deadline though the title has one. 1,785 give a deadline with no date in the title, which regex couldn't find. 31 impossible dates or dates before creation are treated as missing.
- **early_side against actual timing, 300-market pilot:** YES_EARLY markets: YES resolved early in 67% of those going YES, NO in 7% of those going NO. NO_EARLY: NO early 57%, YES early 6%. NEITHER: 24% both.

**The two main labels overlap heavily.** Phi correlation between "means NO" and "only YES can finish early" is 0.78 on all labeled markets and 0.74 on world.

| World markets | Only YES can finish early | Otherwise |
|---|---|---|
| Nothing happening means NO | 18,632 | 2,322 |
| Otherwise | 687 | 6,107 |

**Known weakness of `default_side`: steady cadence.** "Nothing new happens" is read literally, so a new release always counts as new. All 66 OpenAI release questions my title search found got `default_side` NO and `early_side` YES_EARLY, including "OpenAI release a model called 5.2 in December 2025?". You could argue the real status quo is OpenAI keeps shipping. 26 of the 66 resolved YES (39%). The prompt has no way to express this. I don't know how many markets are affected.

**Labels could remember the future.** Haiku is told not to use what it knows, but it may recall how old events ended. A text rule with no model finds the same flip (section 6), which argues against this being the cause. I didn't test the new labels on events after Haiku's knowledge cutoff.

---

## 5. Measures

- **Gap:** arithmetic mean of prices minus arithmetic mean of outcomes (YES = 1). Positive means overpriced YES. In points.
- **Bins:** 10-point-wide price bins, each with mean price against share resolved YES. Each market counts once. The current plots drop bins under 30 markets and print the count by each dot.
- **Shift:** the one number added to every price's log-odds that makes the group's mean price equal its YES rate. Zero is calibrated. −0.65 means YES odds overstated about 1.9 times. It's fitted, not an average, and it clips prices to 1–99%.
- **Line:** logit(YES) = alpha + beta × logit(price). beta above 1 means prices are squeezed toward 50%.
- **Brier and log loss:** used in sections 5, 10 and 13.
- **"Corrected" / "deadline passed":** keeps only markets whose stated deadline passed at least 60 days before the fetch. It removes most of the skew from still-open markets, and also every market with no stated deadline, so the mix changes.

**Error bars** (`boot_rate`, `summary`, `src/yes_bias.py`)
- 95% percentile interval from a cluster bootstrap: 500 draws of creators with replacement, within the markets of that bin or group. Only creators with a market in that bin can be drawn.
- **Model:** creators are independent draws from a large population. Each brings a bundle: N_c markets, Y_c resolved YES. The statistic is θ̂ = ΣY_c / ΣN_c. Markets from one creator may depend on each other in any way.
- **Method:** the plug-in principle. Replace the unknown creator distribution with the empirical one. Sampling from it is drawing names with replacement.
- **Equivalent formula:** Var(θ̂) ≈ Σ_c (Y_c − θ̂·N_c)² / (Σ_c N_c)². With one market per creator this becomes θ̂(1−θ̂)/n, the usual coin-flip formula.
- **References** (from memory, check before citing): Efron 1979; Bickel & Freedman 1981; Cameron, Gelbach & Miller 2008.
- **What it covers:** which creators and questions we happened to get. **What it doesn't:** two creators asking about one election share one outcome, and shared shocks like an election year. So bars are probably somewhat too narrow.
- **Small bins:** runs narrow. When every market in a bin has the same outcome, resampling can't vary, so no bar is drawn. Zero of 11 still fits a true rate of up to about 28%.
- **Robustness:** resampling deadline months instead of creators gives −0.82 to −0.42 for "means NO" with a stated deadline at 1 week, against −0.79 to −0.61 resampling creators. Wider, same conclusion.

---

## 5b. Overall calibration [measured]

World markets, 15+ bettors by then. Brier of the market against always guessing that panel's YES share. That constant is known only afterward, which flatters it slightly.

| Moment | Markets | YES share | Market Brier | Constant Brier |
|---|---|---|---|---|
| 12h after creation | 3,875 | 33.7% | 0.164 | 0.223 |
| 1d after creation | 6,137 | 33.8% | 0.160 | 0.224 |
| 1w after creation | 9,913 | 32.3% | 0.148 | 0.219 |
| 1m after creation | 10,194 | 29.5% | 0.136 | 0.208 |
| 3m after creation | 9,212 | 26.6% | 0.130 | 0.195 |
| 6m after creation | 8,454 | 25.8% | 0.118 | 0.192 |
| 1y after creation | 5,462 | 24.1% | 0.085 | 0.183 |
| 1y before resolution | 3,805 | 24.3% | 0.132 | 0.184 |
| 6m before resolution | 8,537 | 25.1% | 0.111 | 0.188 |
| 3m before resolution | 11,701 | 27.0% | 0.099 | 0.197 |
| 1m before resolution | 16,407 | 29.0% | 0.082 | 0.206 |
| 1w before resolution | 21,378 | 31.4% | 0.064 | 0.215 |
| 1d before resolution | 24,976 | 33.6% | 0.049 | 0.223 |
| 12h before resolution | 25,833 | 34.1% | 0.043 | 0.225 |

Other groups at 1 week after creation: traded_elsewhere Brier 0.172 (constant 0.246, 1,447 markets, gap +0.8 points); fixed_chance at 1 day 0.246 (constant 0.250, 475 markets, gap 0.0).

**World calibration by bin, 1 week after creation** (mean price → YES share, markets): 1.2→0.0 (267), 3.5→2.3 (574), 7.4→4.1 (888), 14.8→8.5 (1,596), 24.7→17.2 (1,235), 34.9→23.8 (1,027), 44.8→36.4 (807), 55.1→42.8 (762), 65.2→50.3 (733), 74.9→63.5 (723), 85.0→78.7 (701), 92.4→91.2 (328), 96.5→96.2 (156), 98.9→99.1 (116). Full table: `plots/calibration_15_bettors_by_then_bins.csv`.

---

## 6. Main finding: sorted by default side, after creation [measured]

Plot: `plots/second_pass/by_side.png`. Still open at the snapshot, 15+ bettors by then.

**1 week after creation:**

| If nothing happens | Markets | Mean price | Resolved YES | Gap | Shift (95%) | Share of total gap |
|---|---|---|---|---|---|---|
| Resolves NO | 7,699 | 36.3% | 26.8% | +9.5 | −0.65 (−0.73 to −0.57) | 97.1% |
| Resolves YES | 534 | 69.7% | 76.6% | −6.9 | +0.52 (+0.32 to +0.74) | −4.9% |
| No default side | 1,529 | 48.1% | 44.2% | +3.9 | −0.23 (−0.35 to −0.11) | 7.9% |
| All world | 9,762 | 40.0% | 32.3% | +7.7 | −0.51 (−0.57 to −0.45) | 100% |

**Across after-creation horizons** (gap in points; no still-open filter here, so 1w differs by about 0.1):

| Side | 1d | 1w | 1m | 3m | 6m | 1y |
|---|---|---|---|---|---|---|
| Resolves NO | +8.6 | +9.4 | +9.7 | +10.5 | +10.7 | +7.0 |
| Resolves YES | −6.7 | −7.0 | −7.0 | −8.3 | −8.2 | −7.6 |
| No default side | +4.4 | +3.5 | +4.7 | +7.8 | +5.9 | +4.0 |
| All | +7.1 | +7.6 | +7.9 | +9.0 | +8.9 | +5.7 |
| Markets, all | 6,136 | 9,911 | 10,193 | 9,211 | 8,452 | 5,462 |

Markets per side at 1w: NO 7,797, NONE 1,573, YES 541. At 1y: NO 4,316, NONE 829, YES 317.

**Bins at 1 week (mean price → YES share, markets):**
- **Resolves NO:** 5.4→3.0 (1,468), 14.9→7.8 (1,385), 24.6→15.1 (1,056), 34.9→22.6 (848), 44.8→34.7 (643), 55.1→39.0 (562), 65.2→45.9 (523), 74.8→57.4 (467), 84.8→74.6 (425), 94.6→91.6 (322).
- **Resolves YES:** 55.8→63.6 (44), 65.8→77.1 (61), 75.4→85.7 (91), 85.6→89.0 (118), 94.5→98.3 (118). Lower bins have under 30 markets each.
- **No default:** 4.5→2.5 (162), 14.8→11.8 (187), 24.9→29.4 (153), 34.9→25.3 (154), 44.9→40.7 (135), 55.0→49.4 (158), 65.1→57.4 (148), 75.2→66.9 (154), 84.9→82.0 (150), 94.8→95.3 (128).

**It's a shift, not a squeeze.** Slope of the line for "resolves NO": beta 0.99 (0.95 to 1.04) at 1w, 1.00 (0.95 to 1.05) at 1m, 0.93 (0.87 to 0.98) at 1d. Alpha −0.65 at 1w. So error has about the same log-odds size at every price. "Resolves YES": beta 1.12 (0.93 to 1.32) at 1w, 1.24 (1.04 to 1.45) at 1m. No default: 0.98 (0.87 to 1.09) at 1w.

**"No default side" isn't clean, but no deadline nearly is.**
- No stated deadline: 788 markets, +1.6 points, −0.10 (−0.24 to +0.06).
- Stated deadline: 741 markets, +6.3 points, −0.38 (−0.56 to −0.19).
- "Resolves NO" without a stated deadline: 1,555 markets, +6.6 points, −0.46. With one: 6,144 markets, +10.2 points, −0.69.

**Replications of the flip:**
- **On markets I didn't hand-label as such:** default YES and not hand-YES: 256 markets, +0.42 (+0.11 to +0.78). Includes some I labeled the other way.
- **Hand labels, independent of Haiku:** YES means no change, 297 markets, 73.2% vs 79.5%, −6.3 points, +0.47 (+0.15 to +0.80).
- **Text rule with no model:** by-date −0.74 (3,978 markets), still-or-remain +0.40 (+0.08 to +0.72, 320 markets), no-date −0.30 (3,339).
- **Two halves of creators, by hash:** resolves NO −0.58 and −0.72. Resolves YES +0.64 and +0.39. No default −0.23 and −0.25.
- **Labels agreeing and disagreeing:** older regex+Haiku says change and new label says NO: 6,696 markets, −0.71. Older says change but new label says not NO: 508 markets, −0.13 (−0.33 to +0.06), so these look calibrated, and the new label is sorting better. New NO only: 1,003 markets, −0.30.

**Outside world:**
- traded_elsewhere: default NO 645 markets, +3.7 points, −0.23 (−0.46 to −0.03). Default NONE 651 markets, −1.3 points, +0.07.
- not_substantive default NO: 180 markets, +0.40. not_forecast default NO: 150 markets, −0.82.
- So it isn't specific to world, but the size varies.

**By creation year, "resolves NO", 1 week:**

| Created | Uncorrected: markets, shift | Corrected: markets, shift |
|---|---|---|
| 2022 | 930, −0.95 | 735, −0.98 (−1.27 to −0.73) |
| 2023 | 3,110, −0.77 | 2,482, −0.87 (−1.00 to −0.75) |
| 2024 | 2,368, −0.52 | 1,748, −0.68 (−0.83 to −0.54) |
| 2025 | 908, −0.45 | 698, −0.71 (−0.92 to −0.52) |
| 2026 | 382, −0.23 | 216, −0.79 (−1.17 to −0.43) |

The apparent recent improvement is mostly still-open markets. With the correction there's some improvement from 2022–23 to 2024, and none clearly since.

**With the correction, 1 week:**

| If nothing happens | Markets | Mean price | Resolved YES | Gap | Shift (95%) |
|---|---|---|---|---|---|
| Resolves NO | 5,880 | 35.5% | 23.9% | +11.6 | −0.81 (−0.90 to −0.72) |
| Resolves YES | 439 | 70.0% | 76.3% | −6.3 | +0.47 (+0.26 to +0.72) |
| No default side | 701 | 48.1% | 41.9% | +6.1 | −0.37 (−0.58 to −0.16) |
| All world | 7,020 | 38.9% | 29.0% | +9.9 | −0.67 (−0.74 to −0.60) |

So removing the still-open skew makes the bias larger. The uncorrected numbers understate it.

---

## 7. Before resolution, and why it looks reversed

Plot: `plots/second_pass/before_resolution.png`, rows by default side and by early side, six horizons. `before_resolution_metrics.csv` also holds "still open" and "deadline passed" versions; those plots were deleted at Peter's request.

**Gap in points** [measured]

| Group | 1d | 1w | 1m | 3m | 6m | 1y |
|---|---|---|---|---|---|---|
| Resolves NO | −1.2 | −0.1 | +2.8 | +6.9 | +11.0 | +13.6 |
| Resolves YES | +1.4 | +1.2 | −0.7 | −5.6 | −10.2 | −14.2 |
| No default side | +1.0 | +2.0 | +3.5 | +5.8 | +6.0 | +6.0 |
| Only YES can finish early | −1.7 | −0.6 | +2.5 | +6.7 | +11.0 | +13.6 |
| Only NO can finish early | +2.2 | +2.6 | +1.6 | −0.9 | −3.8 | −5.1 |
| Neither can finish early | +1.8 | +2.6 | +4.1 | +6.2 | +6.4 | +7.8 |
| **All three default sides pooled** | −0.7 | +0.3 | +2.7 | +6.0 | +9.0 | +11.0 |

**Markets:**

| Group | 1d | 1w | 1m | 3m | 6m | 1y |
|---|---|---|---|---|---|---|
| Resolves NO | 19,063 | 16,470 | 12,806 | 9,302 | 6,821 | 3,063 |
| Resolves YES | 1,460 | 1,283 | 1,006 | 714 | 525 | 214 |
| No default side | 4,449 | 3,622 | 2,592 | 1,683 | 1,190 | 528 |
| Only YES early | 17,562 | 15,246 | 11,859 | 8,638 | 6,346 | 2,815 |
| Only NO early | 1,946 | 1,694 | 1,315 | 922 | 669 | 318 |
| Neither early | 4,695 | 3,783 | 2,719 | 1,773 | 1,278 | 565 |

The early-side groups exclude BOTH, so they don't sum to all markets.

**Shift, resolves NO:** +0.19, +0.02, −0.29, −0.63 (−0.69 to −0.56), −0.94 (−1.02 to −0.87), −1.08.

**Mean price and YES share, resolves NO:** 1d 26.4/27.6, 1w 24.7/24.8, 1m 25.1/22.3, 3m 27.1/20.2, 6m 28.9/17.9, 1y 31.1/17.5.

**With the correction, gap:** Resolves NO −1.2, 0.0, +3.7, +8.6, +13.6, +18.0. Resolves YES +1.5, +1.5, −0.8, −5.5, −10.6, −14.4. No default +1.4, +2.9, +5.1, +7.2, +8.0, +8.0. 1y corrected "resolves NO": 2,428 markets, 28.7% vs 10.7%.

**Only still-open markets, gap at 1d:** Resolves NO −2.9, only YES early −3.5, only NO early +3.3. So that filter makes the 1-day reversal about twice as large.

**The reversal is in the middle bins.** Only YES can finish early, mean price → YES share (markets):
- 1d: 3.1→1.2 (11,111), 14.0→16.4 (1,204), 24.5→35.8 (452), 34.5→52.2 (299), 44.8→71.4 (287), 55.2→79.5 (229), 65.1→83.3 (311), 75.3→90.8 (446), 85.7→95.8 (695), 96.7→99.0 (2,528).
- 1w: 3.9→1.4 (9,011), 14.0→11.5 (1,655), 24.3→31.0 (668), 34.6→43.9 (408), 44.8→63.4 (339), 54.9→69.9 (309), 65.2→77.0 (326), 75.6→87.8 (459), 85.4→92.9 (621), 96.0→98.3 (1,450).

Only NO can finish early, 1d: 2.4→0.2 (506), 14.7→9.5 (74), 24.2→11.6 (43), 34.6→20.5 (39), 65.7→43.3 (30), 74.6→64.3 (56), 85.6→71.6 (81), 97.5→99.2 (1,066). Thin in the middle.

**Pooled across labels at 1w before resolution** (world, mean price → YES share, markets): 24.5→26.1 (971), 34.8→37.3 (657), 44.8→51.1 (577), 54.8→63.1 (558), 65.2→68.8 (558), 75.4→80.7 (775).

**Why: the outcome chooses the moment measured.** [reasoned]

Toy example. 100 by-date markets all sit at 40% on January 1, deadline December 31. They're perfectly calibrated at every calendar moment, so 40 will go YES.

- The 60 NOs resolve at the deadline. One day before that is December 30, when almost no time is left, so they're at 1–2%.
- The 40 YESes resolve when the event happens, on any date. The day before, it often isn't fully foreseen, so some are still around 40%.

So on "1 day before resolution", the 40% bin holds almost only markets about to go YES. They all resolve YES, though nothing was mispriced. The NOs that were once at 40% have already decayed into the low bins.

The reverse holds when only NO can finish early: YESes wait for the deadline and climb to about 99%, and the middle bins fill with markets about to go NO.

This is an artifact of measuring from resolution, and it's the same pitfall the project's `AGENTS.md` lists under "forecast time that depends on the outcome".

**Supporting numbers: the two outcomes separate as resolution nears.** Mean price, "resolves NO" markets [measured]

| Before resolution | Went YES | Went NO |
|---|---|---|
| 1d | 78.3% | 6.6% |
| 1w | 71.8% | 9.2% |
| 1m | 66.6% | 13.2% |
| 3m | 63.7% | 17.8% |
| 6m | 63.1% | 21.4% |
| 1y | 60.4% | 24.9% |

So most YESes were largely seen coming: at 1d they average 78%. Predictable events sit at 99% and land in the top bin. The middle bins hold only the unforeseen remainder.

**Why the 1-month line looks calibrated.** It's near the diagonal likely because two errors cancel: the timing skew pushes YES rates up, and the real overpricing pushes them down. [reasoned] I predicted that if this is right, the 1-year line would show clear overpricing. It does, +13.6, and 3m and 6m climb steadily with no jump. Peter predicted underpricing at 1 year. That prediction held only on the small "resolves YES" side. This fits but doesn't prove the idea.

**The fairest before-resolution line is "neither can finish early"** [reasoned]: these resolve on a schedule, so the moment doesn't depend on the outcome. It's overpriced throughout, from +1.8 at 1d to +7.8 at 1y.

**Longer horizons change the population.** Only markets that lived that long get in. Part of the growth could be which markets are counted, not time. 1y after creation has +5.7 pooled and 1y before resolution +11.0, on different markets.

**Before the stated deadline instead** (`plots/second_pass/before_deadline.csv`; does not depend on the outcome; market still open, 15 people moved the price by then; deadline passed 60+ days before fetch; each point a different set of markets, since those whose event already happened are gone) [measured]

| Before stated deadline | Resolves NO: markets, price, YES, shift | Resolves YES: markets, price, YES, shift |
|---|---|---|
| 1y | 2,419, 31.7%, 18.7%, −1.03 | 183, 70.1%, 81.4%, +1.00 |
| 6m | 5,296, 27.7%, 14.5%, −1.20 | 421, 76.0%, 86.2%, +1.05 |
| 3m | 6,669, 23.7%, 11.8%, −1.30 | 529, 79.0%, 86.6%, +0.91 |
| 1m | 8,230, 18.4%, 9.6%, −1.21 | 677, 81.0%, 85.8%, +0.73 |
| 2w | 9,316, 15.6%, 9.1%, −1.05 | 756, 83.1%, 86.0%, +0.54 |
| 1w | 9,749, 13.7%, 8.3%, −1.02 | 802, 84.1%, 86.4%, +0.52 |
| 3d | 10,149, 12.3%, 7.9%, −0.95 | 836, 84.8%, 87.3%, +0.73 |
| 1d | 9,967, 11.0%, 7.1%, −0.98 | 788, 85.4%, 87.4%, +0.64 |

This is the cleanest evidence that overpricing persists close to the deadline. The same reversal does not appear here, which supports the timing explanation. No plot exists for this.

---

## 8. The early-finish question [measured]

Peter's hypothesis: the asymmetry in when each outcome can arrive drives the bias.

**Early finish doesn't look like the driver, but the data can only partly separate them,** since 89% of "resolves NO" markets are also "only YES can finish early".

**Within "resolves NO", 1 week after creation, shift:**

| Early side | Markets | Uncorrected | Corrected (markets) |
|---|---|---|---|
| Only YES | 6,857 | −0.68 (−0.76 to −0.60) | −0.82 (5,427) |
| Neither | 418 | −0.57 (−0.81 to −0.33) | −0.78 (259) |
| Both | 245 | −0.32 (−0.69 to +0.01) | −0.43 (88), interval includes 0 |
| Only NO | 179 | −0.17 (−0.62 to +0.22) | −0.34 (106), interval includes 0 |

Neither side can finish early, and it's still as overpriced. Both and only-NO look smaller but on few markets.

**Within "no default side":** only YES early +0.04 (171), only NO early −0.44 (98), both −0.63 (62), neither −0.24 (1,198). The direction is opposite to what the asymmetry predicts, with wide intervals.

**Within "resolves YES":** only NO early +0.54 (445), neither +0.47 (49).

**By `early_side` alone, ignoring default:** only YES −0.65 (7,054), only NO +0.21 (722), neither −0.30 (1,665), both −0.36 (321).

**By `early_path`:** only YES + normal −0.65 (6,952). Only YES + shock −1.22 (102), mean price 15.6%. Only NO + normal +0.15 (544). Only NO + shock +0.60 (160), mean price 77%. Both + normal −0.37 (319). So shock-path markets sit at extremes, and few of them exist.

The early-finish asymmetry is what produces the *before-resolution* reversal (section 7). It doesn't appear to produce the *after-creation* bias.

---

## 9. Other splits within "resolves NO" [measured]

Plot: `plots/second_pass/within_no.png`. Shift at 1 week, 95% in brackets.

| Split | Value | Markets | Uncorrected | Corrected |
|---|---|---|---|---|
| General interest | no | 2,439 | −0.73 (−0.85 to −0.62) | −0.80 (−0.94 to −0.65) |
| | unsure | 687 | −0.88 | −1.11 (−1.38 to −0.86) |
| | yes | 4,573 | −0.56 (−0.66 to −0.46) | −0.76 (−0.88 to −0.65) |
| Outside reference | no | 3,424 | −0.83 (−0.94 to −0.71) | −0.94 (−1.07 to −0.80) |
| | unsure | 2,346 | −0.58 | −0.81 |
| | yes | 1,929 | −0.40 (−0.54 to −0.27) | −0.59 (−0.76 to −0.44) |
| Prompted by news | yes | 2,700 | −0.79 (−0.92 to −0.66) | −0.89 (−1.02 to −0.76) |
| | unsure | 997 | −0.53 | −0.65 |
| | no | 4,002 | −0.59 (−0.68 to −0.49) | −0.79 (−0.90 to −0.69) |

- **Thin attention as measured by general interest fails.** The uncorrected difference mostly goes away once still-open markets are removed.
- **Outside reference is a partial lead.** The gap of about 0.35 survives, but it's the least stable label and a large overpricing remains with a reference.
- **News prompt:** overlapping intervals once corrected. Not established.

**Time left at the snapshot, "resolves NO" with a stated deadline, 1 week after creation:**

| Days left | Markets, corrected | Shift, corrected | Return on NO, corrected | Shift, uncorrected (markets) |
|---|---|---|---|---|
| Under 14 | 528 | −0.49 (−0.81 to −0.19) | 9.7% | −0.48 (541) |
| 14–30 | 694 | −0.67 (−0.89 to −0.44) | 15.3% | −0.67 (707) |
| 30–90 | 854 | −0.72 (−0.94 to −0.50) | 17.7% | −0.73 (861) |
| 90–365 | 2,337 | −0.85 (−0.99 to −0.74) | 19.9% | −0.77 (2,395) |
| Over 365 | 1,279 | −1.01 (−1.18 to −0.87) | 22.3% | −0.65 (1,450) |

Return on NO = (1 − YES rate) / (1 − mean price) − 1, before costs.

Within creation years, corrected: 2023 goes −0.21, −0.64, −0.68, −0.98, −1.13. 2024 goes −0.53, −0.68, −0.59, −0.68, −0.82. 2022 has −0.57, −1.15, −1.20, −1.09, −0.92, flatter. 2025 is noisy: −0.90, +0.03, −0.70, −0.90. So it's not only a year effect, though it's not perfectly clean.

**This reopens lock-up as a partial explanation.** More time left goes with more overpricing, which capital lock-up predicts. Lock-up can't explain a 10% return in under two weeks, and returns grow much slower than time. So it could explain part of the long-dated excess, not the short-dated overpricing. The older note `yes_bias_debug.md` rejected lock-up because returns looked flat at 17–28% across time left. That table used regex dates and had missing long-dated markets (its last row, 2 years+, shows 2%).

**Loans may matter.** An EA Forum thread argues Manifold's loans once offset the cost of locked mana (section 14). Not tested here.

---

## 10. A correction learned on old markets, tested on later ones [measured]

Plot: `plots/second_pass/recalibrated.png`. **This is a correction to prices, so the plot shows raw and corrected.**

**Design.** Fit one log-odds shift per default side on what was known at the start of 2024, then apply to markets created from 2024 on.
- **Uncorrected version:** train on markets resolved before 2024; test on all created from 2024. This training set sees early YES resolutions but not those still open, so it under-corrects.
- **Corrected version:** train on those with a stated deadline passed 60+ days before 2024; test on those with a deadline passed 60+ days before fetch.

**Fitted shifts at 1 week:** corrected NO −0.76 (1,077 markets), NONE −0.04 (88), YES +0.71 (81). Uncorrected NO −0.27 (2,049), NONE −0.06 (387), YES +0.36 (148).

**Test results:**

| Version, horizon | Markets | Raw gap | Fixed gap | Raw Brier | Fixed Brier | Brier change (95%) | Raw log loss | Fixed log loss |
|---|---|---|---|---|---|---|---|---|
| Corrected, 1w | 3,250 | +8.3 | +0.1 | 0.140 | 0.131 | −0.009 (−0.014 to −0.006) | 0.432 | 0.404 |
| Corrected, 1m | 3,034 | +9.0 | −1.2 | 0.132 | 0.120 | −0.012 (−0.016 to −0.007) | 0.411 | 0.380 |
| Corrected, 1d | 2,292 | +6.7 | −3.5 | 0.151 | 0.147 | −0.004 (−0.009 to +0.001) | 0.461 | 0.447 |
| Uncorrected, 1w | 4,773 | +5.6 | +2.6 | 0.147 | 0.143 | −0.004 (−0.005 to −0.003) | 0.449 | 0.438 |
| Uncorrected, 1m | 4,370 | +5.8 | +3.2 | 0.138 | 0.135 | −0.004 (−0.004 to −0.003) | 0.426 | 0.417 |
| Uncorrected, 1d | 3,462 | +4.2 | −0.3 | 0.157 | 0.155 | −0.002 (−0.004 to −0.001) | 0.476 | 0.468 |

**The default-side label adds little to the fix.** One shift for all markets gets most of the gain: at corrected 1w, −0.008 vs −0.009. Per-side minus one-shift: −0.002 (−0.004 to +0.001). Most markets are on the same side.

**How to phrase this:** the error is stable enough that a simple adjustment learned earlier works later. It isn't shown to be tradable. Fees, spread and locked mana aren't counted. This isn't evidence of market inefficiency in the profit sense.

**A note on an earlier mistake:** the first version fit on markets *created* by 2023, and 2,452 of 5,138 of those resolved in 2024 or later, so it used outcomes not yet known. Sol caught this. The version here is forward-looking. `yes_bias.py`'s older test ("fit on 2023 and earlier", Brier 0.140→0.137) still has that flaw.

---

## 11. Explanations tested, with sizes

**Fail, or too small** [measured unless tagged]

| Explanation | Test | Result |
|---|---|---|
| Pipeline bug | Coin flips at 1 day | 475 markets, 49.9% vs 49.9% |
| Pipeline bug | Prices vs stored prices | Last price matches stored within 1 point in 99.9%; 0.4% of markets have a jump over 2 points between moves |
| Frozen prices | Drop closed but unresolved | 7.6→7.7 points |
| Trade impact | Price before last move | Shift −0.51 vs −0.50 |
| Stale last price | Mean over last 24h (5,537 markets) | Shift −0.46 |
| Fetch gate | Markets with 15+ bettors under 1,000 mana (2,258) | YES 39.2% vs 38.6% in sample |
| Fetch gate | Require 1,000 mana at the snapshot, no future (6,797) | Shift −0.45, gap +6.3 |
| Dropped resolutions | N/A or percent among by-date | 2.0% of markets. Even if all were YES, about 2 of 9.5 points |
| Wrong resolutions | Share of NOs that must be wrong to erase the 55–85% gap | 34%. Read 60: 6 disputed, 5 subjective or inactive-creator, 49 look right. Low-priced YES also disputed, 7 of 30. My reading, no outside check |
| 50% start | Started below 40% vs at 50% (older run) | Shift about −0.65 either way, on 93 markets (−1.43 to −0.10). Creators choose those starts, so weak. About 98% start at 50%, about 1% still within 0.5 points at 1 week [from note] |
| New traders alone | Regression on log-odds moved per trader type | Coefficients 0.91 to 1.03 on every type (all carry about the right information), constant −0.65 left over. New traders push +0.20 on average, experienced push down |
| Delayed fills | Excluding orders with later fills [from note] | Barely changes. Source paths don't replace a resting order's `probAfter`. 2 versions checked |
| Stale prices | Price updated within a day [from note] | Roughly 7 points remain |
| Large topics | Remove politics, AI, culture, top 20 templates and 4 storylines, 64% of markets [from note] | Gaps 7.8→7.5 and 7.2→6.1 (old status-quo and other) |
| One event | Resampling deadline months | Interval widens (section 5), same conclusion |

**Partial: more trading helps but doesn't finish it** [measured]
- "Means NO" (older label) by volume at snapshot: under 2,000: −0.75 (4,082). 2,000–5,000: −0.67 (1,660). 5,000–20,000: −0.36 (1,161). Over 20,000: −0.35 (385).
- Where experienced traders make most moves, −0.44; where they make the least, −0.86. Quintiles: −0.86, −0.78, −0.51, −0.68, −0.44. Differences between sets of markets, not causal.
- All world by volume, after creation [from note, gap]: 1m: 3,000+ +5.4, 10,000+ +3.1, 20,000+ +3.0. 6m: +6.9, +5.6, +5.5. 1y at 20,000+ touches zero. 83 markets reach 20,000 by 1m and are open at 1y: resolved YES 17%, price 28%→16%, a lead only.

**Don't use: outcome-dependent filter.** `new-years-resolutions-2024` looked like a large fix: removing it moves world from 7.6 to 5.8 points. But it depends on the outcome: tagged markets resolved around that New Year went YES 12.8% (1,002), untagged 43.5% (315). Removing them would be p-hacking.

**Not tested:**
- Markets Manifold deleted or hid.
- Whether labels leak on post-cutoff events.
- Effects of the loan system.
- Why creators ask what they ask. The natural story (questions get asked because someone finds the event plausible, and few bother to bet NO on a niche question that pays nothing until the deadline) has no direct evidence. A trader comment in the audit says "things generally don't happen", so traders do know the pattern.

---

## 12. What's missing from the data [measured]

Markets still open at fetch aren't in the sample. A separate fetch (`data/yes_bias/unresolved.jsonl`) counted active ones: 15+ bettors and 1,000+ mana.

- **Scale:** 7,708 active markets unresolved: 749 / 2,877 / 2,135 / 978 / 969 for creation years 2022–26, or 13% / 14% / 18% / 22% / 33% of each year.
- **With a title date still ahead:** 3,756 unresolved and only 827 resolved, at a mean final price of 63%. So that part of the data leans YES.
- **With a title date passed 60+ days ago:** 453 unresolved, 19,136 resolved, 368 N/A or percent. Nearly complete. Residual about 2%.
- **Effect:** "means NO" (older label) shift −0.66 for all, −0.73 with a title date, −0.86 with that date passed. Gap 9.6 → 10.7 → 12.3 points. So the first step is question mix and the second is the correction.

This is why uncorrected recent years look better than they are.

Dropped N/A and percent resolutions by text rule: by-date 2.0% (12,351 markets), no-date 4.0% (16,647), other 2.9%, still-or-remain 2.3%.

---

## 13. Polymarket and direct comparison [measured]

**No labels on Polymarket yet. So there's no claim beyond this.**

**One text rule on both, by-date markets, created 2023–2025, 1 week after creation, 1,000 mana or $1,000 by the snapshot:**

| Platform | Markets | Mean price | YES | Gap | Shift (95%) |
|---|---|---|---|---|---|
| Manifold | 2,193 | 33.3% | 23.9% | +9.4 | −0.71 (−0.86 to −0.59) |
| Polymarket | 2,024 | 32.1% | 28.1% | +4.1 | −0.39 (−0.56 to −0.24) |

Polymarket by-date all years: 1d −0.20, 1w −0.36, 1m −0.42. No-date: −0.23, −0.17, −0.13. Other: −0.37, −0.25, −0.50. Still-or-remain: only 36 at 1w (−0.36, −1.25 to +0.81), so the flip can't be tested there. Polymarket has no default starting price, so a 50% start isn't the cause there.

**Similar title open on the other platform at the snapshot (TF-IDF cosine ≥ 0.42, unverified):**
- Manifold: with −0.07 (−0.59 to +0.42, 173), without −0.76 (2,020). Polymarket: with −0.22 (−0.54 to +0.05, 621), without −0.47 (1,403).
- Unstable: on Manifold 2025 it reverses in an earlier run. A lead only.

**Same event, same moment, 1 week after both exist** (hand-verified pairs, blind to prices and outcomes):

| Pair type | Pairs | Manifold minus Polymarket log-odds | Manifold Brier | Polymarket Brier | Difference (95%) |
|---|---|---|---|---|---|
| By-date, all | 81 | −0.09 (−0.27 to +0.08) | 0.154 | 0.130 | +0.024 (−0.016 to +0.062) |
| By-date, not copied | 42 | −0.05 (−0.27 to +0.18) | 0.145 | 0.121 | +0.024 (−0.037 to +0.083) |
| Fixed-date, all | 40 | +0.19 (−0.09 to +0.49) | 0.170 | 0.126 | +0.043 (+0.015 to +0.068) |
| Fixed-date, not copied | 34 | +0.26 (−0.06 to +0.59) | 0.188 | 0.140 | +0.049 (+0.015 to +0.077) |

- Prices differ by 8.7 points on average; 26% of by-date pairs differ by 10+.
- A margin of ±0.25 was fixed before looking. By-date slightly exceeds it, so they can't be called equal.
- 43 of 91 by-date Manifold markets copy Polymarket's rules or say they resolve the same way.
- These pairs aren't overpriced on either platform: 25% priced, 33% YES, shift about +0.58. High-profile events selected for being on both, so they say little about typical markets.
- Fixed-date pairs are mostly elections, where Manifold is clearly less accurate.

---

## 14. What others have said [web]

Checked 2026-11-03. **I found nothing from Manifold that splits the lean by question type.** The search wasn't exhaustive.

- **Manifold's [calibration page](https://manifold.markets/calibration):** samples past trades on resolved binary questions with 15+ traders, trade-weighted, Brier 0.17371 when checked. Doesn't mention a YES lean.
- **Manifold newsletter, Nov 2022, [Above the Fold](https://news.manifold.markets/p/above-the-fold-midterms-special):** says markets are well calibrated on average, using price halfway through a market's life, with analysis credited to Vincent (vluzko). Halfway through a market's life is itself an outcome-dependent moment [my reading].
- **LessWrong, [Are Manifold prediction markets well-calibrated?](https://www.lesswrong.com/posts/oPsyqfqfDGrZ6hwpf/are-manifold-prediction-markets-well-calibrated):** found YES overestimated by about 8 points early on, 6 at midpoint, 1 near resolution, and attributed it to a base rate of about 36%. **I read only search excerpts of this; the page blocked my fetch. Read it before citing.**
- **Manifold market, [YES-bias on at least 8/9 categories](https://manifold.markets/Loppukilpailija/manifold-calibration-yesbias-on-at):** users noticed the lean across the calibration chart. Example: markets at 20% resolving YES 15%. It resolved YES, and no cause is discussed.
- **EA Forum, [Manifold markets isn't very good](https://forum.effectivealtruism.org/posts/EaR9xFxspmYRkm3eo/manifold-markets-isn-t-very-good), Robin, June 2024:** says "a clear systematic bias towards predicting things will happen", and that it can be algorithmically fixed. Manifold's James Grugett replies that any bias "can also be rectified with trading strategies". A commenter says it's an old bias that has improved. Our corrected numbers show no clear improvement since 2024. The thread also discusses loans and time value. I read this through a mirror and a summarizing tool, so verify quotes.
- **[Bayesian Investor, Feb 2024](https://bayesianinvestor.com/blog/index.php/2024/02/01/manifold-markets/):** prices too close to 50%, worst in low-attention markets. Doesn't discuss YES bias.
- **arXiv [2503.03312](https://arxiv.org/pdf/2503.03312), "How manipulable are prediction markets?":** a field experiment on 817 Manifold markets, described in a search result as finding them well calibrated. I didn't read it.

Literature in the project's scope, with methodology pitfalls, is listed in `AGENTS.md`: Dickerson et al. PNAS 2026, Reichenbach & Walther SSRN 2026, Bürgi Deng & Whelan, Cardozo & Rivero-Wildemauwe, Yurchyna, and Themis. R&W separate longshot and default (YES) bias, which is the nearest prior framing to ours. Their default overpricing is 0.2–0.8 points on Polymarket. Not compared directly to ours.

**What seems new here, as far as I could find:** that the lean belongs to "something must happen", that it flips sign when YES means no change, and that before-resolution calibration hides it through an outcome-dependent timing artifact.

---

## 15. How this design handles the pitfalls in `AGENTS.md`

| Pitfall | What we did |
|---|---|
| Market vs trade as unit | One price per market per panel |
| Winner-only selection | Binary YES/NO markets only |
| Non-independent rows | Creator bootstrap, with deadline-month resampling as a check. Only partial. No event clustering |
| Underpowered independence checks | Removing large groups [from note]. No fully deduplicated sample |
| Outcome-dependent timing | After-creation and before-deadline views. Before-resolution shown with the artifact explained |
| Trade price vs displayed probability | Manifold `probAfter` is the displayed price. Polymarket uses last-block on-chain trades, not midpoints |
| Pooled diagonal hides errors | Split by group and side. Tails in the 14-bin world table |
| Recalibration and exploitability | Forward-looking test, explicitly not a profit claim |

---

## 16. Corrections and mistakes along the way

**Should be disclosed or at least known.**

1. **Stale bettor counts, found 2026-11-04.** A Nov 1 fix stopped zero-amount fills counting as bettors, and `activity_analysis/README.md` flagged the file needed rebuilding. It wasn't rebuilt until 2026-11-04. So plots and reports before then used inflated counts. Prices never changed. About 2% of markets fall below the 15-bettor rule: 1w world from 10,085 to 9,913. "Means NO" gap stays +9.4, "means YES" −7.1→−7.0. 49,788 snapshot rows changed in bettors, 1,849 crossed the 15 threshold. All tables here use fixed counts. `src/activity_analysis.py` "reads the original saved parquet", so rerunning it no longer reproduces the original count figures.
2. **Fit used the future.** See section 10. Fixed in the new analysis, still present in the older test.
3. **Snapshot past close.** 149 of 9,911 world snapshots at 1w came after the market's recorded close. Fixed in `second_pass_analysis.py`. `yes_bias.py` has it as a labeled artifact check (moves nothing).
4. **Zero-width bars.** See section 5. Bars now omitted there.
5. **Claims I had to reverse:**
   - "Status quo vs other" was the wrong split.
   - An earlier "Manifold isn't worse" was reversed by the paired Brier comparison.
   - The similar-title lead weakened under a stricter pool.
   - Thin attention failed once labels covered everything.
   - Lock-up was rejected too firmly.
6. **Sol found six bugs in the first analysis**: "by date" group included undated markets; a parser made "before May 1" into May 31; before-deadline used future bettor counts and closed markets; the Polymarket $1,000 gate used final volume; last-trade ties arbitrary; pairs dropped on disagreeing outcomes. All fixed. **Astra** found four over-strong claims, which are tested above.
7. **Reviews:** Sol's review of the first analysis's fixes didn't run (usage limit), so that code had only my reading. Sol reviewed `second_pass_analysis.py` and found five issues: three fixed (items 2–4), two stated as limits (residual unresolved markets, before-deadline composition). Those fixes, `second_pass_before_resolution.py` and the snapshot rebuild had no outside review.
8. **Plots deleted at Peter's request:** `by_side_corrected.png`, `before_resolution_open.png`, `before_resolution_corrected.png`. Git has them, and the CSVs hold the numbers. If the paper follows the project's rule of showing corrected and uncorrected plots side by side, they'd need redrawing: restore the removed lines in the two scripts.
9. **Not independently recomputed.** The gap and bins are simple means. I checked the pipeline with coin flips and stored prices, but never recomputed from scratch separately, and never tested the shift on a case with a known answer. Worth doing before publication: about 20 minutes.

---

## 17. Limitations to state in a paper

- **Selection:** resolved binary only, 15+ lifetime bettors, 1,000+ lifetime volume. The gate uses the future. Effects checked in sections 11 and 12, not eliminated.
- **Unreviewed resolutions:** 90 read by hand, not by an outside check. Creator-resolved.
- **Labels:** one LLM from text, no human gold standard beyond my 514. `default_side` reads "nothing new" literally. Possible leakage on old events.
- **Dependence:** intervals ignore different creators sharing an event, and shared shocks. Probably somewhat too narrow.
- **Different market sets across horizons:** both before and after.
- **Play money:** mana isn't money. Polymarket by-date is overpriced too, but smaller, by one rough rule.
- **Before resolution:** the timing explanation is reasoned, not tested. A simulation of a perfectly calibrated market would test it directly and cheaply. Not done.
- **No causal claims:** volume, experienced traders, time left and outside reference are all comparisons between sets of markets.

---

## 18. Open threads

- **Polymarket labels:** planned for 2026-11-04, batches at low effort, $52 of credit expiring 2026-11-05 08:59 GMT+1. See `src/labeling_second.py` for the Manifold version. Then the flip can be tested there properly.
- **Simulation of the timing artifact.**
- **Independent recomputation** (section 16, item 9).
- **Loans:** split by the dates Manifold changed the loan system.
- **Cadence:** how many `default_side` NO markets have a steady cadence, and whether they behave differently.
- **Post-cutoff label check.**
- **Mechanism:** still open. Most direct next test is probably who takes the NO side and when, on "means NO" markets.
- **Earlier idea not used:** `event_key` to group ladders, for better intervals (`notes/second_pass_questions.md`).

---

## 19. Files

**Reports and notes**
- `notes/second_pass_results.md`: short report on the re-sort (old counts).
- `notes/yes_bias_debug.md`: short report on the first debugging (old counts; update note at top).
- `notes/second_pass_questions.md`: why each new question was asked.
- `notes/labeling_pilot.md`, `notes/labeling_review.md`, `notes/classifier_questions.md`: first-pass labels.
- `notes/selection_audit.md`, `notes/related_outcomes.md`, `notes/timing_luna_audit.md`, `plots/activity_analysis/README.md`, `plots/high_volume_after_creation/README.md`: older checks. Numbers tagged [from note] come from these. Not rerun on 2026-11-04.
- Luna audit, short version: 6 of 100 "no default" markets flagged by GPT-6 Luna for outcome-dependent timing, with clear misses, such as a market explicitly allowing early NO if Biden drops out. It motivated `early_side`.
- `human_notes.md`: Peter's own notes. Holds his original reasoning about default side and timing.

**Code**
- `src/snapshots.py`: builds `data/manifold/snapshots.parquet`.
- `src/plot_calibration.py`: overall calibration, Brier.
- `src/yes_bias.py`, `src/yes_bias_plots.py`: first analysis, artifact checks, Polymarket, pairs, audit.
- `src/labeling_second.py`: second pass.
- `src/second_pass_analysis.py`, `src/second_pass_plots.py`: re-sort, after creation.
- `src/second_pass_before_resolution.py`: before resolution.

**Numbers**
- `plots/second_pass/metrics.csv`, `bins.csv`, `before_deadline.csv`, `before_resolution_metrics.csv`, `before_resolution_bins.csv`.
- `plots/yes_bias/metrics.csv`, `bins.csv`, `before_deadline.csv`, `pairs.csv`, `similar_*.csv`.
- `plots/calibration_15_bettors_by_then_bins.csv`, `_brier.csv`. These now also hold 3m and 6m rows; the plots still draw the original five horizons.

**Plots**
- `plots/second_pass/by_side.png`: main finding, after creation, three horizons.
- `plots/second_pass/before_resolution.png`: six horizons, default side and early side.
- `plots/second_pass/recalibrated.png`: fix tested on later markets, raw vs. fixed, with and without correction.
- `plots/second_pass/within_no.png`: splits within "resolves NO".
- `plots/yes_bias/`: `resorted.png`, `what_moves_it.png`, `censoring.png`, `platforms.png`, `before_deadline.png`.
- `plots/calibration_after_creation_15_bettors_by_then.png`, `plots/calibration_before_resolution_15_bettors_by_then.png`: overall, per group.

**To rerun everything, in a tmux session, from the repo root:**

```
.venv/bin/python src/snapshots.py
PYTHONPATH=src .venv/bin/python src/second_pass_analysis.py
.venv/bin/python src/second_pass_plots.py
.venv/bin/python src/second_pass_before_resolution.py
PYTHONPATH=src .venv/bin/python src/yes_bias.py analyze
.venv/bin/python src/yes_bias_plots.py
.venv/bin/python src/plot_calibration.py
```

Git: all of this is on branch `second-pass-pilot`, about 50 commits ahead of `master`, and not pushed past what the cloud run pushed.
