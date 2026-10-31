# Raw data observations: Polymarket (Becker dump) and Manifold (API)

## Correction (Terra, 2026-10-31)

**The “left 10–90% for good” numbers below are wrong.** They measure the last in-range observation, which can be long before the price actually leaves that range; some markets finish inside it. The old Manifold claims of 68% more than a day before resolution, 48% more than a week before, and a six-day median should not be used.

On all 37,680 eligible Manifold markets, the following are **snapshot** probabilities, not claims about when a price left the range permanently. “Correct” means the final YES/NO outcome matched the more likely side. The two extreme groups overlap.

| Before resolution | Markets with a forecast | Below 10% or above 90%: share; correct | Below 2% or above 98%: share; correct |
|---|---:|---:|---:|
| 12 hours | 37,227 | 67.5%; 98.8% | 32.8%; 99.8% |
| 1 day | 36,533 | 63.8%; 98.7% | 27.9%; 99.7% |
| 1 week | 31,376 | 55.5%; 98.3% | 16.9%; 99.8% |
| 1 month | 24,818 | 44.0%; 98.0% | 8.8%; 99.7% |
| 1 year | 7,407 | 20.8%; 96.1% | 1.8%; 99.2% |

The earlier report's 31% for the 2% tails at one day used the incomplete fetch and a different snapshot rule; the full-data figure is 27.9%. For each snapshot we take `probAfter` from the last non-redemption bet with `probBefore != probAfter` and `createdTime` at or before the snapshot, breaking equal timestamps by file order. The snapshot must be after creation; a market with no earlier price-moving bet is excluded. Month and year mean 30 and 365 days. Limit orders and simultaneous bets need further timing checks. Extreme prices do not prove the answer was already known.

**The same error affects the Polymarket figures and the volume claim.** In the original 8,500-market topic-balanced sample, the corrected shares with an observed final exit more than a day and a week before `end_date` are **25.6% and 14.7%**, versus the old 43% and 25%. Among all sampled non-summary dollar volume, **34.4%** traded after that observed exit, versus the old 43%. We order fills by block and log index and use the first fill after the last price in the inclusive 10–90% range, only when the final fill is outside it. Markets without an observed in-range price have no identifiable exit and contribute to the denominator but not the numerator. The sample overweights substantive topics, and neither price extremes nor `end_date` prove when the outcome became known.

---

**What this is.** A first look at the raw rows, to find what matters for the calibration plots and the filters. No calibration curves here.

**What was looked at.**
- **Polymarket:** all 408,863 market rows. Trades only for a sample: 8,500 resolved markets, drawn per rough topic. The topic comes from a regex on the question text. That gave 14.5M trade rows.
- **Manifold:** all 107,761 lite market records, and the 17,486 markets whose bets are already fetched. Also the official 2024-07 market dump, used for one check.

Every claim is tagged **[verified]** (checked on the data) or **[suspected]** (not checked).

---

## The four things that matter most

### 1. "X hours before resolution" mostly measures markets that are already decided

On both platforms the price often reaches ~0 or ~1 long before the official end. After that the market just waits to be resolved.

- **Manifold [verified]:** 68% of markets had their price leave the 10–90% range for good more than 1 day before resolution. 48% did so more than 1 week before. The median gap is 6 days. One day before resolution, 31% of markets are already above 98% or below 2%.
- **Polymarket [verified]:** 43% of sampled markets left 10–90% for good more than 1 day before `end_date`, and 25% more than 1 week before. 43% of all dollar volume trades after that point, mostly at 0.99+ or 0.01−. 32% of trades print at ≥0.99 or ≤0.01.

**Why it matters.** At 12h or 1d, a "near-perfect diagonal" is mostly a few hundred markets sitting at 0 or 1. That is real, but it is not forecasting.

**Caveat.** "Left 10–90% for good" does not always mean the answer was known. A "by Dec 31" question that drifts down as time runs out is a real forecast at 3%. You cannot tell the two apart from price alone.

**What to do.** For every horizon, report the share of snapshots in the 0–2% and 98–100% bins. Show the curve with and without them. The 1w/1m horizons are probably the meaningful ones.

### 2. The scheduled close date is mostly not in the data

- **Manifold [verified]:** if a market is resolved before its close date, the API **overwrites `closeTime` with the resolution time**. Checked against the 2024-07 dump: 4,939 markets that were still open then later resolved more than 1 day early. For 97% of them the API now shows `closeTime == resolutionTime`. Their original close date is gone. In the current data 46% of eligible markets have `closeTime == resolutionTime`. These early markets resolve YES 54% of the time; the rest resolve YES only 25%.
- **Manifold [verified]:** creators also move close dates. 14% of markets that resolved on schedule have a different `closeTime` now than in the 2024 dump.
- **Polymarket [verified]:** `end_date` is usually a date, not a moment. 80–95% of political, "other", mentions and weather markets end at exactly 00:00 or 12:00 UTC. Trading often goes on after it: median +9h for weather, +16h for mentions, +18h for elections. Sports `end_date` is roughly the game start; trades continue ~3h past it.

**Why it matters.** Anchoring on the resolution time of an early-resolved market picks the moment just before a surprise YES. This bias is visible on Manifold [verified]. One day before resolution, the Brier score is 0.104 for early-resolved markets and 0.059 for the rest. (Brier = mean squared error of the probability; lower is better.)

**What to do.**
- **Manifold:** the true scheduled close exists only in the official dump, and only for markets open on 2024-07-06. Otherwise it has to come from the question text ("by end of 2025"). Use the dump to estimate how big the bias is.
- **Polymarket:** treat `end_date` as accurate to about a day. Prefer horizons of 1w or more, or a fixed calendar date.

### 3. Low-probability bins are mostly losing candidates of multi-outcome events

- **Polymarket [verified]:** 56% of sampled markets trade on the NegRisk exchange. That is Polymarket's contract for "one of N options wins" events: elections, "who will win the Masters", temperature brackets, tweet-count brackets. You can tell from the `_contract` column of the trades.
- One month before `end_date`, 53% of snapshots are priced ≤2%. Only 1 of those 916 resolved YES. 83% of them are NegRisk options. Typical examples: "Will Enoch Chihana win the 2025 Malawi presidential election?", "Will Russell Henley win The 2025 Masters?".
- Because of these losing options, the first outcome wins only 20% of the time in "other" and 22% in elections.

**Why it matters.** Without grouping, the low bins and the market count are dominated by fields of 10–30 long shots per event. Those long shots are cheap to get right.

**What to do.** Becker has no event id. A usable proxy [verified]: markets of one event share the same `created_at` second and the same `end_date`. 61% of markets share that key with at least two others. Examples:
- one UFC fight: KO, submission, O/U rounds;
- a ladder: "Meta reach $620 / 640 / 660 / 730 / 820 in December";
- one esports match.

Use this key for cluster bootstrap and per-event weights. Also show a "NegRisk options only" vs "standalone binaries" split.

### 4. Prices go stale

- **Manifold [verified]:** at the snapshot, how old is the last bet that moved the price?
  - 1d before resolution: median 1 day; 25% are older than a week.
  - 1m before: median 6 days; 48% older than a week.
  - 1y before: median 11 days; 30% older than a month.
- **Polymarket [verified]:** median age of the last trade, 1 month before `end_date`: 25h overall, 47h for "other", but 0–5h for crypto, stocks and weather.

**What to do.** Store the staleness with every snapshot and show the curve with and without a recency filter. The plan to count unique bettors up to the snapshot also matters [verified]. One year before resolution, only 55% of Manifold markets have their 15 bettors yet.

---

## Polymarket

**What the markets are [verified, rough regex topics].** There are 383,707 closed markets.

| Kind of market | Share of closed markets |
|---|---|
| Crypto "Up or Down" (hourly or 15-min) | 31% |
| Sports with team-named outcomes, plus sports Yes/No | 44% |
| Everything else (politics, tech, culture, crypto price ladders, weather, mentions) | 25% |

The top templates are BTC/ETH/XRP/SOL "Up or Down – <date> <hour>", about 12,600 each. Next come crypto "above $X on <date>" ladders (~1,550 per coin), "highest temperature in London between X–Y°F" (1,520) and "Elon Musk post X–Y tweets" (1,286).

The regex bucket "other" still contains sports, stock ladders ("Palantir finish week above $181?") and memecoin launches. Real world-event questions are perhaps 5% of the total: Epstein files, Fed chair, Ukraine, AI model rankings. **A content filter is the main job, and the market question alone is often too thin to classify.** "Will Bolivia win?" and "FriendlyCampers to win 0 maps?" need the event title, which Becker lacks.

**Markets are short [verified].** Of closed markets with volume, 6.9% are open more than 30 days and only 0.16% (about 500) more than a year. **A Polymarket 1y horizon is close to empty.** The 1m horizon has roughly 1,700 markets in a sample of 6,000. On Manifold, 15% of fetched markets reach the 1y horizon.

**Volume is a bad quality filter [suspected, partly verified].** 43% of dollar volume comes after the price is decided, so high volume partly means "lots of trading at 0.99". 18% of closed markets have zero volume, mostly hourly XRP/SOL Up-or-Down. `liquidity` and `active` are useless: `active` is True for every row.

**Trade-level quirks [verified].**
- **41% of trade rows are duplicates.** These are the taker's summary of a match; the `taker` column is the exchange contract itself. Drop them before counting trades. The prices in them are consistent.
- Each trade gives a price for one token. Convert to the YES price by taking 1 − p for the second token. Mint matches (YES at 0.93 bought against NO at 0.07) show this sums to 1.
- **About half of the last trades before a snapshot are under $1.** Most are long-shot dust. Still, the last trade is more than 10 percentage points from the median of the last 10 trades in only ~4% of snapshots. A short median or VWAP would make this robust (VWAP = volume-weighted average price).
- Block timestamps look real, not interpolated. The steps are 2, 4, 6 or 8 seconds in three block ranges checked. This contradicts one of the Gemini notes.

**Odd metadata [verified].**
- 1,714 markets resolved 50/50 (cancelled games and similar); exclude them.
- 162 rows are `["0","0"]` and 14 are `["1","1"]`.
- 10% of markets have no `created_at`.
- 6,400 have `end_date` before `created_at`, usually by a few hours (sports, mentions).
- Last trade on the losing side: 0.9% of markets.
- About 26k early markets (2020–22) trade on the old automated market maker (FPMM), so their trades are in `legacy_trades`.

**Where missing metadata hurts.**
- No event id: use the `created_at`+`end_date` proxy.
- No tags or category: regex or an LLM on thin question text.
- No resolution or closed time: use the last trade as a proxy.
- No order book: last trade instead of the midpoint.

## Manifold

**Eligible set.** 37,680 markets with resolution YES/NO, ≥15 bettors and ≥1000 mana volume. All are cpmm-1 (the automated market maker) and all are in MANA.

**Fetch coverage [verified].** So far the fetched bets are mostly 2024 markets: 9.6k from 2024, 3.5k from 2025, 2.0k from 2026, 2.2k from 2023. The 2023 cohort has 50k markets of all sizes, so it is under-covered for now. Partial results are not representative by year.

**What the markets are [verified].** Content is much more substantive and much less templated than on Polymarket.
- 30,404 of 32,486 normalized question templates appear only once.
- Top-10 creators make 16% of markets. Examples:
  - BTE, 1,300 markets: "Will Xi visit the White House by end of 2024?"; 28% resolve YES.
  - Traveel: "Daily Coinflip", 470 markets.
  - johnleoks: Destiny streamer markets.
- Repetitive series do exist: S&P / FTSE / BTC "close higher than yesterday" (~400 in total) and "Will Jimmy Carter be alive at end of day" (83).
- Topic tags from `groupSlugs`: about 11% carry non-predictive, personal, meta or fun tags ("Are there more chairs than tables?", "Will I read 24+ books?"), 9% sports, 11% crypto or stocks. About 70% are none of these.

**Resolution timing [verified].**
- 20% of markets resolve more than 1 day after close, 3.7% more than 30 days after.
- Betting stops at close. So "1d before resolution" can be the price from a month before resolution. Anchor on `min(closeTime, resolutionTime)`, but see finding 2: for early markets that value is the resolution itself.

**Creators bet and resolve [verified].**
- In 60% of markets the creator bets, including right before resolving. In 84% the creator is the resolver.
- The last price is on the wrong side of the outcome in 3.9% of markets. Some are genuine surprises ("Will Pierre Poilievre win his seat?", 99% the day before, NO). Some are self-referential ("Will the largest bettor be a YES holder?") or judgment calls.

**Bet records [verified].**
- 17% of bet rows have amount 0. They are placed or cancelled limit orders that do not move the price, so skip them when measuring staleness.
- 29% of bets are placed through the API, mostly bots.
- 36% of markets have small breaks in the `probBefore`/`probAfter` chain. These are bots betting within the same ~100 ms. Taking the last `probAfter` by time is fine.
- `uniqueBettorCount` matches the distinct bettors in the files.

**Excluded resolutions.** CANCEL (6,855) and MKT (2,237, resolved to a probability) are outside the eligible set [suspected]. Cancellation may itself select on awkward outcomes.

---

## Details

- **Polymarket sample.** Trades were extracted for 8,500 closed markets with volume > 0. The draw was 2,500 "other", 1,200 elections, 800 stocks/macro and 500 for each other bucket, so the sample over-represents substantive markets. 7,970 of them had CLOB trades. The extraction is one DuckDB pass over all 46 GB and takes about 70 s, so full scans are cheap.
- **Price conventions.** Price = USDC/tokens. Rows with the exchange as taker were removed for every statistic except the 41% count.
- **How "left 10–90% for good" was measured.** Time of the last trade or bet with a price strictly inside (0.1, 0.9), compared with `end_date` (Polymarket) or `resolutionTime` (Manifold).
- **Manifold snapshots.** The snapshot is the last price-moving bet at or before resolution − h. Staleness is the snapshot time minus that bet's time.
- **Scripts.** All in `/tmp/claude-1001/-home-nape662-projects-prediction-markets-calibration/a4aac4c7-3a1f-414f-ad26-26bcbb53b54e/scratchpad`; nothing was written to `src/` or `data/`.
