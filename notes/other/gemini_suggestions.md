# Gemini suggestions (2026-10-31)

Saved verbatim for later. Not discussed or adopted yet.

The biggest threat to your weekend study is not noisy individual markets—it is structural multiplicity: on both platforms, what looks like 50,000 binary markets is actually a few thousand independent questions plus massive clusters of correlated contracts (Polymarket negRisk multi-outcome bundles and recurring series). If you filter and bucket at the individual market_id level, your calibration plot will mostly measure how Polymarket prices 15-candidate political fields and 10-bucket weekly Elon Musk tweet brackets.

## 1. The Filtering & De-duplication Methodology

Do not run an LLM classifier on raw markets, and do not try to philosophically adjudicate whether "How many tweets will Elon Musk post?" is a "real" world-judgment question. Instead, shift the unit of filtering from individual markets to normalized templates/events, and solve the recurring-series problem via cluster weighting rather than hard binary exclusion.

### Step 1: Collapse Markets into Canonical Templates (Deterministic)

Before running any content filters, group markets into clusters so you can see the actual shape of the dataset:
- Polymarket (event_id + Title Normalization): Polymarket's Gamma API groups related binary contracts under a parent event_id (and series_id for recurring markets). Furthermore, strip dates, numbers, dollar amounts, and ordinals from question strings into a canonical template:
  "Will Elon Musk post 100-119 tweets from May 2 to May 9?" --> "Will Elon Musk post <NUM>-<NUM> tweets from <DATE> to <DATE>?"
- Manifold (creatorId + Normalized Title): Filter to outcomeType == "BINARY" and resolution IN ("YES", "NO") (explicitly drop "MKT" partial resolutions and "CANCEL"). Group by (creatorId, normalized_title_template).

This single step typically compresses ~100,000+ raw binary markets into a few thousand multi-market templates plus a tail of true one-off questions.

### Step 2: Two-Layer Content Filter (Deterministic Regex + Rubric LLM)

- Deterministic Pruning (Zero Cost):
  - Polymarket: Exclude markets where event tags or series metadata contain Sports, Games, or Up or Down, or where the canonical template matches `<TICKER> above/below/hit <USD> on <DATE>`. (Using a price-target template regex preserves epistemic crypto questions like "Will the SEC approve a Solana ETF?" while killing 10,000 daily price bets.)
  - Manifold: Exclude markets whose groupSlugs contain sports leagues (nfl, nba, soccer, f1, esports), stock/crypto tickers (crypto, bitcoin, stocks), or Manifold meta-games (whale-watching, stock-exchange, lottery, coin-flip).
- LLM Classification on Templates (Explicit 3-Question Rubric): Run an agent on the unique templates (prioritizing all templates with 3 or more markets, plus a pass over singletons). Instead of asking "Is this a useful market?", require a structured JSON classification on three concrete axes:
  ```json
  {
    "mirrors_liquid_external_odds": false,
    "epistemic_category": "WORLD_EVENT | RECURRING_EMPIRICAL | PERSONAL | PRICE_OR_SPORTS | RNG_OR_META",
    "is_self_referential_or_gimmick": false
  }
  ```
  - Rule for mirrors_liquid_external_odds: True only if a regulated exchange, sportsbook, CME FedWatch tool, or mathematical RNG continuously publishes implied probabilities for the exact outcome.
  - Manual Audit (20 minutes): Inspect the top 50 templates by market count and 50 random singletons. Because templates follow power laws, auditing the top 50 templates audits the majority of your multi-market rows.

### Step 3: Stop Multi-Bucket Events & Recurring Series from Dominating

This is where most Polymarket calibration studies silently break:
- The negRisk / Multi-Bucket Trap (Within-Event Correlation): On Polymarket, categorical questions ("Who will be the next Fed Chair?", "How many tweets will Elon post this week?") are implemented as bundles of K mutually exclusive binary markets sharing an event_id. In every resolved bundle of K contracts, exactly 1 resolves YES and K - 1 resolve NO. If K = 10, each weekly tweet market injects 9 correlated NO resolutions into your 2%–20% probability bins.
- The Fix (Hierarchical Weighting): Assign every market i belonging to event e (with K_e binary sub-markets) and recurring template T (with M_T distinct events over time) a weight [formula missing in the pasted text], where C is a series cap (e.g., C = 5).
  - Dividing by K_e ensures a 20-candidate election has the same total weight (1.0) as a single binary question.
  - Capping at C = 5 means "Elon Musk weekly tweets" or a Manifold user's daily "Will I go to the gym?" series can contribute at most 5 effective event-equivalents to the global calibration curve—letting you keep recurring empirical and personal markets without letting them hijack the bins.
  - Sanity check: Plot unweighted, event-weighted (1/K_e), and template-capped (w_i) curves side by side, or isolate pure standalone binaries (K_e = 1) as your clean baseline.

## 2. Methodological Choices: Demonstrated vs. Speculative Pitfalls

Not all caveats deserve equal engineering effort on a weekend. The table below separates problems that empirically warp Polymarket and Manifold curves from second-order noise.

| Issue | Status | Direction / Magnitude of Distortion | Weekend 80/20 Fix |
|---|---|---|---|
| 1. UMA Oracle delay on Polymarket resolution timestamps | Demonstrated (Critical) | Massive at 12h / 1d: Post-outcome prices (99.9% / 0.1%) get sampled as "pre-resolution" forecasts. | Anchor horizons on min(closedTime, endDate), never on on-chain settlement / resolvedTime. |
| 2. Conditioning on actual_resolution - Δt for "By Date X" markets | Demonstrated (Critical) | 5–15 pp bias: Early surprise YES resolutions get sampled right before the surprise; NO resolutions only expire at the deadline. | Use scheduled_close - Δt as primary; split actual_resolution - Δt into early-resolved vs on-schedule. |
| 3. Polygon block-timestamp interpolation in Becker's dataset | Demonstrated (Moderate) | ~3h timestamp noise on interpolated Polygon block times (documented in 2026 studies on Becker's archive). | Safe for 1w/1m/1y; at 12h, cross-check against CLOB /prices-history API on 20 fast-moving markets. |
| 4. OrderFilled complementary (NO) tokens & summary rows | Demonstrated (Critical) | Mirrors prices across 50% (p vs 1-p) or double-counts volume if decoded naively. | Drop rows where taker is the exchange contract; map asset_id to clobTokenIds and invert NO fills (1 - p_NO). |
| 5. Stale trade carry-forward (LOCF) on Manifold & thin Polymarket | Demonstrated (Moderate) | Pulls 12h / 1d curves toward 50% because dead markets carry 3-month-old opening prices to resolution. | Require at least 1 trade within a recency window (e.g., 7 days before snapshot) for 12h and 1d horizons. |
| 6. Horizon composition shift (different markets in 1y vs 1d) | Demonstrated (Moderate) | Confounds time-to-resolution with market difficulty (long political markets vs short event markets). | Add one plot restricting to a balanced cohort (markets open for at least 30 days tracked across 1m, 1w, 1d, 12h). |
| 7. Execution price vs. bid-ask midpoint | Speculative / Minor | Bid and ask executions average out inside bins across hundreds of markets, except on $1 dust trades. | Ignore order books; use trailing 3-trade VWAP (or minimum $5 trade size on Polymarket) to kill dust ticks. |
| 8. Complex error bars | Secondary | Binomial error bars lie anyway because of within-event correlation. | Print n_markets (n_events) per bin on the plot; if adding bars later, cluster-bootstrap by event_id. |

## 3. Concrete Fixes for the Pipeline (Steps 2–4)

### Fix A: The Polymarket Timestamp & UMA Oracle Trap

When an event occurs in the real world (e.g., an announcement happens on Tuesday at 14:00 UTC), Polymarket traders immediately bid the contract to 0.999 or 0.001. However, the market only resolves on-chain after a proposer submits the bond to the UMA Optimistic Oracle and the challenge period (2 hours minimum, or days if disputed) expires.
- If your "12 hours before resolution" or "1 day before resolution" snapshot subtracts from the on-chain resolution timestamp, you are sampling markets 10 to 36 hours after the real-world outcome already occurred.
- Fix: Use min(closedTime, endDate) from the Gamma API metadata as your resolution anchor. As an additional safeguard on early-resolving markets, define a market's effective terminal time T_term as the timestamp after which the execution price permanently stays outside [0.01, 0.99] until resolution, and check whether anchoring on T_term changes your 12h and 1d curves.

### Fix B: Decoding Jon Becker's OrderFilled Records Cleanly

In Polymarket's CTFExchange (0x4bFb...982E) and NegRiskCtfExchange (0xC5d5...f80a) contracts on Polygon, a single matchOrders transaction matching a taker against k makers emits k individual maker OrderFilled events plus one summary OrderFilled event where the taker field is the exchange contract address itself.
- If you are reading raw decoded OrderFilled rows rather than pre-normalized YES prices, verify two invariants in your script:
  ```python
  # 1. Drop the exchange summary row emitted by matchOrders
  EXCHANGE_CONTRACTS = {
      "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e",
      "0xc5d563a36ae78145c45a50134d48a1215220f80a",
  }
  df = df[~df["taker"].str.lower().isin(EXCHANGE_CONTRACTS)]

  # 2. Normalize NO-token executions to implied YES probability
  # If asset_id == clobTokenIds[1] (the NO token), implied_yes_price = 1.0 - raw_price
  ```
- Also check the upper date boundary of your local Becker snapshot: Polymarket migrated exchange contracts in late April 2026, so older indexers stop capturing fills after that cutover unless updated.

### Fix C: Manifold's Front-Loaded Activity Problem

Your plan specifies downloading Manifold markets with at least 15 lifetime participants and filtering by participation prior to the snapshot. That catches dead markets at creation, but Manifold has a severe front-loading dynamic: because new markets hit the home feed immediately upon creation, a 6-month market often gets 25 traders in its first 48 hours and then zero trades for the next 5 months.
- If you sample that market at resolution - 1d, its "1 day before resolution" probability is actually a 5-month-old stale forecast.
- Fix: Alongside "at least 15 unique traders prior to snapshot," record staleness = snapshot_time - last_trade_time. Require last_trade_time to fall in the second half of the interval [open_time, snapshot_time] (or within 2 × Δt of the snapshot) so that a "1-day-out" forecast actually reflects beliefs near the 1-day mark.

### Fix D: Fractional-Lifetime Horizon alongside Fixed Clock Horizons

Because fixed backward horizons (12h, 1d, 1w, 1m, 1y before resolution) suffer from both early-resolution selection bias (on "Will X happen before Y?" questions) and massive sample-size attrition at 1m and 1y, add one normalized horizon: the midpoint of scheduled market duration (open_time + 0.5 * (scheduled_close - open_time)), restricted to markets where actual_resolution_time is after that midpoint.
- Every valid market appears exactly once in this plot regardless of whether it was a 1-week political crisis or a 1-year macro forecast, giving you a clean, selection-free baseline to compare Polymarket vs. Manifold head-to-head.
