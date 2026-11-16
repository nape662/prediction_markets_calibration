# Full methodology

The long versions of the methodology sections of the two LessWrong posts. The posts carry short versions.

## Post 1: Are Polymarket and Manifold well calibrated on non-garbage markets? (lw_calibration.md)

I apologise for having this part auto-generated, but I'm pretty burnt out from what was supposed to be a one-weekend project.

#### Question

Do the prices of Polymarket and Manifold match how often things actually happen, on questions about the world? Mass-produced markets like sports, asset prices, weather and coin flips are excluded. Studies that pool all markets are dominated by these: Dickerson et al. (PNAS 2026) and Reichenbach & Walther (SSRN 2026).

#### Data

- **Polymarket:** we used Polymarket's own APIs (Gamma for market data, CLOB for price history). Dollars traded before each moment come from the Becker on-chain trades dataset, which ends on 2026-02-02. Of about 2.06M Polymarket markets, our regex rules flag 1.12M as sports, 0.75M as asset prices and 0.09M as weather. We remove those and keep resolved Yes/No markets that closed before 2026-02-02 with at least $1,000 of lifetime volume: 36,853 markets, which then go through the LLM filter below.
- **Manifold:** we used Manifold's public API, fetched on 2026-10-30. We kept resolved binary markets with at least 15 bettors and at least 1,000 mana traded over the market's lifetime: 37,680 markets. Of these, 27,752 are labeled as questions about the world. Separately, we fetched resolved multiple-choice questions with the same thresholds (10,373 questions) and split each into one yes/no market per option: in one-winner questions the winning option is YES and the rest are NO; otherwise each option resolves on its own. "Other", options resolved N/A, and one-winner questions resolved to a split are dropped. Haiku 5.5 labeled these, one call per question, with the same junk rule; it also answered the "nothing happens" question per option. An option counts at a moment only if it already existed and was still unresolved.

#### Which markets count as junk

- **Manifold:** each market got 25 tag questions, answered from the text only. The model never saw prices, outcomes or close dates. Jev, a cheap classification model, labeled every market. Opus 5.5 and GPT 6.1 Terra labeled 1,115 markets by hand, chosen where the labels contradicted each other or at random. A tag counts as yes when Jev puts it at 0.8 or higher. The order is fixed, and the first match wins:
  1. coin flips and other fixed-chance games;
  2. existing facts and estimates;
  3. things that are traded or forecast elsewhere anyway (sports, prices, weather, scheduled statistics, who-says-what);
  4. "not a substantive question about the world" (Jev 0.2 or lower).

  Everything else is "world": the 27,752 markets above. On 100 random world markets, Opus scored 9 as hardly substantive, 5 of them about one streamer.
- **Polymarket:** Haiku 5.5 answered the same kinds of tag questions. We drop a market if Haiku tags it as a crypto or other asset price, sports, a central-bank rate, weather, a scheduled release (CPI, jobs reports), who-says-what or post counts, or an existing fact, or if it scores 20 or less out of 100 on "substantive". At 1 week this drops 3,071 of 11,881 markets (26%), mostly who-says-what and tweet counts (1,925). Rankings like box office and app-store charts stay in.
- **How much the LLM filter matters, 1 week after opening.** On Polymarket, without it the shift is −0.29; with it, −0.32. On Manifold binary markets, with the regex alone instead of the LLM filter, it is −0.47 instead of −0.51 (10,777 markets). The sports, price and weather markets the regex removes from Manifold are calibrated (+0.01, 919 markets). The ones it removes from Polymarket were never priced.

#### Forecasts

- **Moments:** 1 day, 1 week and 1 month (30 days) after Polymarket trading starts or after the Manifold market is created. A market counts at a moment only if it was still open then, and each market counts once per panel.
- **Why not "N days before resolution":** the resolution date depends on the outcome. "By date" questions resolve early when YES happens, so "1 week before resolution" is a different calendar moment for YES markets and NO markets. That makes the numbers look better than they are; see the other post. Fixed times after opening don't depend on the outcome.
- **Polymarket price:** the last hourly point of the CLOB price history at or before the moment, at most 3 days old. A market counts only if at least $1,000 had been traded on-chain before the moment. Without this rule, empty order books show fake prices near 50%. We also drop markets in one-winner events whose prices, at that moment, sum to more than 130%.
- **Manifold price:** the probability after the last bet that moved the price, at or before the moment. A market counts only if at least 15 distinct bettors had bet by then.
- **Counts at 1 week:** 22,228 Polymarket markets have a price; 11,881 of them pass the $1,000 rule, and 8,810 also pass the LLM filter. 1,697 Polymarket markets from before 2023 traded on an older system with no on-chain record, so they drop out. On Manifold, 9,762 of 27,748 labeled binary world markets have 15 bettors by then and are still open, plus 20,991 world markets from 1,959 multiple-choice questions (for these, the 15 bettors are counted on the whole question).

#### "No default side"

Haiku 5.5 (medium effort, one market per call, text only) answered:

> If nothing new happens and the current state of affairs simply continues until the deadline, how does this market resolve? Answer YES, NO, or NONE. Answer NONE when the outcome is decided by a scheduled event, measurement or decision that will happen anyway, such as an election, a vote count or an award.

"No default side" means NONE. When we reran the question on 100 Manifold markets, Haiku gave the same answer on 96. All labels and prompts are in the [repository](https://github.com/nape662/prediction_markets_calibration).

#### Statistics

- **Bins:** 10-point price bins. Each dot shows the bin's mean price and the share of its markets that resolved YES. Bins with fewer than 30 markets are hidden.
- **Shift:** a single number added to every price's log-odds so that the group's mean price equals its YES rate. 0 means calibrated. Below 0 means YES is overpriced: at −0.32, a market priced 50% resolves YES about 42% of the time; at −0.51, about 37.5%. Shifts leave out one-winner markets (a Polymarket event or Manifold question where exactly one market wins): their prices add up to about 100% and exactly one of n resolves YES, so their shift is near 0 whatever their calibration. Their miscalibration still shows on the plots and in the other columns, which use all markets.
- **95% intervals:** we resample clusters with replacement, 500 times, and take percentiles. A cluster is a Polymarket event, because its markets share one outcome, or a Manifold creator. Separate events in one storyline ("ceasefire by June?", "… by July?") still count as independent, so the intervals are probably somewhat too narrow.
- **Brier score:** mean of (price − outcome)². The baseline always predicts the group's own YES share. It knows that share only after the fact, which flatters it slightly.
- **Log loss:** natural log, with prices clipped to 0.1%–99.9%.
- **AUROC:** the chance that a random market that resolved YES had a higher price than a random market that resolved NO. It measures ranking only and ignores calibration.
- **Balanced accuracy:** predict YES when the price is above 50%. It is the mean of the share of YES markets called correctly and the share of NO markets called correctly.

#### Results, 1 week after opening

| | Markets | Mean price → YES rate | Shift without one-winner markets (95%) | Brier (baseline) | AUROC | Balanced accuracy |
|---|---|---|---|---|---|---|
| Polymarket, all | 8,810 | 24.5% → 22.3% | −0.32 (−0.42 to −0.24) | 0.090 (0.173) | 0.91 | 0.79 |
| Polymarket, no default side | 3,810 | 23.9% → 23.0% | −0.18 (−0.41 to +0.04) | 0.078 (0.177) | 0.94 | 0.82 |
| Manifold, all world | 30,753 | 33.8% → 27.9% | −0.51 (−0.59 to −0.44) | 0.128 (0.201) | 0.87 | 0.78 |
| Manifold, no default side | 11,624 | 31.3% → 28.0% | −0.37 (−0.50 to −0.22) | 0.115 (0.202) | 0.90 | 0.79 |

The 1-day and 1-month numbers tell the same story; they are in `plots/metrics.csv`. On Polymarket, giving each event a total weight of 1 gives shifts of −0.36 (−0.45 to −0.27) for all markets (3,660 events) and −0.06 (−0.34 to +0.20) for no default side (368 events). On Manifold, giving each multiple-choice question a total weight of 1 (spread over its markets) gives −0.51 (−0.57 to −0.45) for all markets (10,670 events) and −0.26 (−0.37 to −0.14) for no default side (1,924 events). An earlier run, before the LLM filter on Polymarket, grouped repeating events into series by title, with numbers and dates removed. Series with more than 5 events held 10% of the event weight at 1 week, and capping each series at 5 events cut that to 5%. The cap made no visible difference, so the final plots don't use it.

**Read with care:**
- The two platforms' samples contain different questions, so these numbers don't say which platform forecasts better.
- Manifold numbers probably understate the overpricing. Markets that were still unresolved at the fetch are missing, and the recent markets that have resolved lean YES. If we keep only markets whose stated deadline passed at least 30 days before the fetch, the overall shift on Manifold moves from −0.51 to −0.62 (the gap grows from 7.7 to 9.3 points; 15,374 markets). Polymarket has the same problem on a smaller scale: the same filter moves its overall shift from −0.32 to −0.40 (4,242 markets). The follow-up post on the bias uses this filter throughout.
- Manifold's lifetime requirement of 1,000 mana traded uses information from after the moment.

#### Reproduce

Code, labels and prompts: https://github.com/nape662/prediction_markets_calibration. `python src/both_platforms.py` draws both plots above and writes `plots/metrics.csv`. It reads the outputs of `polymarket/prices.py` and `manifold/second_pass_analysis.py` (see their docstrings). The raw data is not in the repository because of its size. It comes from the public APIs and the Becker dataset (github.com/Jon-Becker/prediction-market-analysis).

## Post 2: Manifold and Polymarket are biased against "nothing ever happens" (lw_bias.md)

**Data and filters** are the same as in [the calibration post](TODO-link). In short:
- **Polymarket:** resolved Yes/No markets that closed before 2026-02-02, after regex rules and Haiku labels removed junk (sports, asset prices, weather, scheduled statistics, who-says-what, existing facts, unsubstantive questions). A market counts at a moment only if $1,000 had been traded on-chain before then. 8,810 markets at 1 week.
- **Manifold:** resolved binary and multiple-choice questions, fetched on 2026-10-30 (binary) and 2026-11-14 (multiple-choice), that a classifier labeled as questions about the world (Jev for binary, Haiku 5.5 for multiple-choice, same rule). As on Polymarket, a multiple-choice question is an event split into one yes/no market per option; the "Other" option, markets resolved N/A, and one-winner events resolved to a split are left out. A market counts at a moment only if 15 distinct people had bet on its event by then, and its option existed and was unresolved then. 30,753 markets at 1 week (9,762 binary markets and 20,991 markets from 1,959 multiple-choice events).

**Label.** The question above, answered by Haiku 5.5 at medium effort, one market per call. It saw only the text: no prices, outcomes, or close or resolution dates.
- **Rerun on 100 markets,** Haiku gave the same answer on 96.
- **Against 302 markets Opus 5.5 high labeled by hand** as "YES means no change", Haiku said YES on 284.
- **A plain text rule with no model** ("by/before <date>" vs "still/remain") finds the same flip on Manifold binary markets: by-date −0.74 (3,978 markets), still-or-remain +0.40 (320 markets).
- **Memory:** Haiku may remember how older events ended. We didn't test the label on events after its knowledge cutoff.

**Shift and intervals.** The shift is fitted on prices clipped to 1–99%. The 95% intervals come from a bootstrap: we resample Polymarket events or Manifold creators with replacement, 500 times. Separate events in one storyline still count as independent, so the intervals are probably somewhat too narrow.

**It's a shift, not a squeeze toward 50%.** Prices aren't too extreme, just too high on YES: for Manifold "resolves NO" at 1 week, YES odds are about 2× too high at every price, from 15% to 75%. (Fitting logit(YES rate) = α + β·logit(price) gives β = 1.06, interval 1.01 to 1.12; β = 1 would be a pure shift, β below 1 prices that are too extreme.)

**Each event counted once.** Many Polymarket markets are slices of one event. Giving each event's K markets a weight of 1/K each moves "resolves NO" to −0.46 (−0.57 to −0.35) on 3,035 events. On Manifold, where each binary market is its own event, the same weighting moves "resolves NO" to −0.80 (−0.88 to −0.72) on 6,335 events.

**Across time, numbers (Manifold, 1 week after creation, "resolves NO").** With the deadline filter: −0.98 (2022, 735 markets), −0.88 (2023, 3,082), −0.71 (2024, 4,909), −0.71 (2025, 1,993), −0.45 (2026, 815). Without it, the shift shrinks to −0.30 in 2026. In 2026, three monthly multiple-choice series ("What will happen in <month>?", "<Month> AI model releases", "Which YouTube channels will release a video in <month>?") hold 47% of the markets and are much less biased (shift −0.34 together). Counting each event once gives −0.76 in 2026, against −0.69 in 2024 and −0.68 in 2025. "Resolves YES" has 53–462 markets per year with the deadline filter, and its interval touches 0 in some years.

**A correction fitted on old markets works on new ones (Manifold, 1 week after creation).**
- **Fit:** one log-odds shift per default side, using only what was known at the start of 2024. The training markets are those whose stated deadline passed at least 30 days before 2024.
- **Test:** applied to markets created from 2024 on, among those whose deadline passed at least 30 days before the fetch.
- **Result:** the gap between mean price and YES rate falls from 8.5 points to 0.9. Brier falls from 0.144 to 0.134 (change −0.010, interval −0.015 to −0.006), on 10,634 markets.
- **Without the deadline filter,** the gap falls from 7.0 to 3.6 points.
- **One shift for all markets** gets most of the gain, since most markets are on the "resolves NO" side.

This shows the error is stable, not that it is profitable to trade on. Fees, spreads and capital locked until the deadline are not counted.

**Things we tested on Manifold that don't explain the bias:** early finishes, niche questions, questions prompted by news, the 50% starting price, stale prices, the price impact of trades, and wrong resolutions. More trading volume goes with a smaller bias and more time left with a larger one, but neither removes it.

**Reproduce:** `python src/pooled_bias.py` for Manifold (it reads the outputs of `manifold/second_pass_analysis.py` and `manifold_mc/`); `python polymarket/calibration.py` for Polymarket; `python src/bias_plots.py` draws the plots. Per-group numbers are in `manifold/plots/pooled/metrics.csv` and `polymarket/plots/metrics.csv`. Code, labels and prompts: https://github.com/nape662/prediction_markets_calibration.
