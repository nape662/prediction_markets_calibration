# Labeling pilot: what we did, what we chose, what to improve

**A cheap model can sort markets into our plot groups almost as Opus does: Haiku 5.5 at low effort, 20 markets per call, agrees with Opus 5.5 on 191 of 200 markets, for about $36 at list price if we label everything. Sorting isn't the same as finding interesting questions, though: the one question meant to catch those barely separates anything.** Whether the $98 cloud credit can pay for it is still untested.

You are reading this to improve two things: the cost of the labeling and the quality of the questions. Your goal and rules are at the end.

## The goal behind the labels

The project (`AGENTS.md`) asks whether Polymarket and Manifold probabilities match how often things happen, especially on real questions rather than mass-produced gambling. So every market needs labels that let us plot each kind separately.

The labeler answers 22 narrow yes/no/unknown questions plus a free-text `junk_reason`. We turn the answers into plot groups ourselves. The questions, the group rules and the reasoning are in `notes/classifier_questions.md`.

## The process, step by step

1. **Clean the input** (`src/labeling_input.py`, output in the gitignored `data/labeling/`). It removes text written after a market was created, such as "Update..." and "resolved YES". The model never sees a price, an outcome, or any date except creation. Close dates are withheld because Manifold overwrites them on early resolution, and early resolution leans YES.
2. **Shrink Polymarket to templates.** Polymarket has 379,945 markets closed before our trade data ends (2026-02-02). They collapse to 127,378 question templates by removing numbers and dates, split also by scheduled length. We label one market per template. Manifold has 37,680 markets, labeled one by one. Total: 165,058 items.
3. **Pick the sample** (`src/labeling_pilot.py prepare`, seed 0): 200 markets in shuffled order. See "Choices" below.
4. **Build the prompt**, also in `prepare`: the intro, 23 question texts and the answer format, all read from `notes/classifier_questions.md` into `labeling/system_prompt.txt`.
5. **Call the models** (`run`), through Claude Code's `claude -p`. Raw output is in `labeling/results/*.jsonl`.
6. **Compare with Opus** (`score`): `scores.csv` by tag, `groups.csv` by plot group, `disagreements.csv` market by market.

To reproduce:

```
export CLAUDE_BIN=$(ls -d ~/.vscode-server/extensions/anthropic.claude-code-*-linux-x64 | sort -V | tail -1)/resources/native-binary/claude
.venv/bin/python -I src/labeling_pilot.py prepare   # overwrites the prompt and the sample
.venv/bin/python -I src/labeling_pilot.py run haiku_low_b20 claude-haiku-5-5 low 20
.venv/bin/python -I src/labeling_pilot.py score opus_high haiku_low haiku_medium haiku_low_b20
```

## Choices and why

**Opus 5.5 at high effort is the reference.** Peter's decision: it is "functionally truth". No human labels exist. Agreement therefore shows Haiku copies Opus, not that either is right.

**The sample avoids gambling on purpose, so it is not representative.** It has 150 Manifold and 50 Polymarket markets. The Manifold part is 6 from each of the 9 kinds the old word filter (`src/sieve.py`) caught, plus 96 it did not catch. Polymarket is 50 random templates. Agreement on this sample doesn't predict agreement on the full data, where the mix differs.

**`claude -p` with no tools and our own system prompt.** A default call sends about 22,000 tokens of Claude Code's own instructions and tools; this one adds about 150. We also set `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, because otherwise each call adds a paid helper request of about 1,270 tokens. The Claude Code installed in `~/.local/bin` (2.1.210) refuses Opus 5.5 and overstates Haiku 5.5's cost, so use the newer binary above.

**Short answer format.** The model lists only the yes and unknown tags; anything unlisted means no. Compared with spelling out all 23 values, this cut visible output from about 290 tokens per market to about 50. The risk is that a tag the model forgot looks like a "no".

**Batching several markets into one call.** It cut cost by about 60%. The prompt asks the model to judge each market separately, but neighbours may still influence each other, and the `substantive_world_question` result below suggests something does change.

**Scoring by plot group, not by tag.** The plot group decides what ends up on a plot, and tag disagreements often don't change it. The pass mark, agreed with Peter: at most 10% of Haiku's "world" group is something else according to Opus, because that much garbage shifts a plot only slightly. Garbage may still pile up in some probability bins, which we can check only once plots exist.

## Results

Groups were assigned by the first-match rules in `notes/classifier_questions.md`. "World" is whatever is left after the other groups.

| Run (200 markets) | Same group as Opus | USD per market |
|---|---|---|
| Haiku low, 1 per call | 192 | 0.00057 |
| Haiku medium, 1 per call | 191 | 0.00067* |
| Haiku low, 20 per call | 191 | 0.00022 |

*\*Recomputed by hand. The script reports 0.00053, which is too low because this run ran alongside Haiku low and reused its cache entries for the same market text.*

Opus costs $0.0124 per market, which would be about $2,050 for everything. Prices are list prices computed by Claude Code; the formula reproduces them exactly (see Details). **These runs were not charged in dollars. They used Peter's subscription allowance.**

**The world group passes the mark.** Opus puts 92 markets there. Of the 91 that Haiku low with batching puts there, 4 (4.4%) are something else according to Opus, and it loses 5 of Opus's 92. Single-market Haiku low: 3 of 91 and 4 lost. With so few cases, the three Haiku runs are indistinguishable.

**The weak points in the questions:**

- **`substantive_world_question` barely separates anything.** Opus says yes on 186 of 200, including sports matches and asset prices, and no only on coin flips, games about the market itself, a few word-saying bets and one vague question. Batching drops Haiku to 137 yes (49 disagreements, against 18 for single calls). This was meant to be the "is this interesting?" question. The groups don't use it, so group agreement hides the problem.
- **"World" means "not caught", not "interesting".** A random 25 from Opus's world group has real questions (a Senator's conviction, a Russian attack on NATO) next to "Will Destiny complete factorio by Christmas?" and "Will George Soros die this year". Destiny, one streamer, accounts for 6 of the 92. Whether they belong in the headline plot is undecided.
- **`subjective_resolution` causes most group disagreements** (13–16 markets per Haiku run). All three Haiku runs call "China will not launch a full-scale invasion of Taiwan [in 2023]" subjective; Opus doesn't.
- **Some tags are untested.** Opus gives zero yes to `short_crypto_price`, `existing_fact`, `fermi_estimate`, `puzzle_or_math` and `direct_opinion`. The sample may simply lack them, or the wording may be too narrow. So the "not a forecast" and "opinion" groups have no evidence at all.
- **`speech_or_posts` sits in the "traded elsewhere" group.** It sends Zelenskyy apologizing to Trump there, though nobody trades that elsewhere. That is a problem with our grouping rule, not with the labeler.
- **`junk_reason` is noisy.** Haiku low fills it on 22 markets, Opus on 4. Haiku often repeats what a tag already says ("Random coin flip").

## Where the money goes

Haiku low at 20 per call, as shares of cost (these 10 calls cost $0.044 at list price):

| Part | Share |
|---|---|
| Thinking | 55% |
| Market text written to the cache | 33% |
| Visible answers | 11% |
| Prompt read from cache | under 1% |

**Shortening the prompt saves almost nothing.** The 22 questions could get longer at no real cost.

Full run at $0.00022 per market: **about $36 for all 165,058, or $28** for Manifold plus the 90,892 templates with volume of at least $1,000. A cruder 50-per-call test gave $0.00018 on the old prompt, but its quality was not scored. Polymarket text runs about 25% longer than Manifold's in the sample, and Polymarket makes up most of the full run, so the real cost may run a little higher.

## The cloud credit: not verified

The plan is to pay with the $98 cloud credit, which expires November 4, 11:59 PM PT. Anthropic's help page confirms these things and no more:

- It applies automatically to cloud sessions.
- Routines don't count.
- While credit remains, cloud usage doesn't count against plan limits.

It doesn't state a rate, and it doesn't say whether subagents or `claude -p` inside a cloud session draw on the credit. We also don't know whether `claude -p` is logged in there at all. If it isn't, Haiku subagents are the fallback. Each would bring its own instructions and tools and a 5-minute cache, and Haiku subagents haven't been measured.

**The test needs a real cloud session run by Peter.** Run the 200-market batch there, then larger pieces, and compare the credit balance with the list-price estimate. The test also needs the committed files on GitHub, and the full run needs the full input, which is in the gitignored `data/`.

## Your job

Improve (a) cost and (b) question quality, then report what changed and by how much, with your uncertainty.

**Rules:**

- **Never add prices, outcomes, or close and resolution dates to the model's input**, and don't let the labels depend on them. That would bias the calibration result.
- **Don't start any full labeling run.** Peter must see the results and approve a run first.
- **Limit spending.** One Opus run on 200 markets costs about $2.50 of Peter's subscription allowance. Change several questions, then rerun once. Haiku runs cost about $0.05–0.13.
- **Don't tune on these same 200 markets alone.** Make a fresh sample with another seed and keep the old one for checking.
- **`prepare` and `run` overwrite files.** Save results under new run names, and run `prepare` for a new sample only after copying the old one.
- **Follow `AGENTS.md`:** minimal code, no hidden errors, commit your work.

**Ideas we haven't tested:**

- Turning thinking off or down, the biggest cost. Check how much group agreement falls.
- A 5-minute cache instead of 1-hour (`FORCE_PROMPT_CACHING_5M=1`): writes cost 1.25x input instead of 2x.
- Bigger batches, or batches of similar length.
- Labeling only a sample of mass-produced Polymarket templates.
- Rewriting `substantive_world_question` so it really separates, or replacing it with several narrower questions.
- A sample enriched in the untested tags, such as by keyword.
- Checking whether template collapsing merges different questions. This is unconfirmed either way.

## 10 disagreements for Peter

The groups in the first column are Opus's. These are the cases that show what the disagreements are about. Peter hasn't reviewed them yet.

| Question | Opus | Haiku |
|---|---|---|
| Will Tyler Cowen agree a real mathematical model of AI risk exists? | world | subjective |
| China will not fully invade Taiwan in 2023 | world | subjective |
| Will Zelenskyy apologize to Trump by end of March 2025? | words + subjective | subjective |
| Will Google Search include a chatbot by June 2023? | subjective | world |
| Will Open Philanthropy open individual AI safety grant applications? | subjective | world |
| Will NYC's air quality be unhealthy on June 15? | weather | world |
| Will an NBC announcer say "smart stadium" at the Super Bowl? | words | world |
| Will Destiny post more videos in February than January? | words | world |
| Will Julia pass R, COBOL, Fortran and Matlab on TIOBE in 2024? | world | scheduled number |
| Will an AI-generated YouTube video reach 50M views before 2027? | world | subjective |

Not every Haiku run disagrees on each of these; see `labeling/results/groups.csv`.

## Details

- **Formula, per million tokens.** Haiku 5.5: $0.10 input, $0.50 output including thinking, $0.01 cache read, $0.20 one-hour cache write. It reproduces Claude Code's reported cost exactly. Opus 5.5's rates weren't checked separately; its figures are what Claude Code reported.
- **Token totals.** Haiku low, 20 per call, 200 markets: 58,330 output of which 48,486 thinking; 30,546 cache read; 73,574 cache write. Haiku low, single calls: 127,961 output, 117,603 thinking.
- **Prompt.** 11,084 characters, about 3,400 tokens, measured from the cache read.
- **Web sources on the credit.** Help page: <https://support.claude.com/en/articles/17152539-cloud-sessions-bonus-credit-promotion>. Caching and cache-lifetime rules: <https://code.claude.com/docs/en/prompt-caching.md>.
- **The 22,000-token default call** was measured on Claude Code 2.1.210. The 150 tokens added to our own prompt come from a call with a one-line prompt.
- **Script review.** Sol reviewed `src/labeling_pilot.py`. It found no errors in the saved results, and its fixes (strict answer checks, a compared-markets count, cost per market sent, an input version) left all scores unchanged. The four saved runs predate the version field, so theirs is empty; all four used the current prompt and sample.
- **Noise not measured.** We ran no model twice on the same prompt, so we don't know how much of the disagreement is random.
