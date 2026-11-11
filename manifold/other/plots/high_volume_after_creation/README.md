# Heavily traded world markets, 1 month to 1 year after creation

**Markets with more trading lean downward less, but the lean doesn't disappear, and going from 10,000 to 20,000 mana changes almost nothing.** Average price minus YES rate, in percentage points:

| After creation | 3,000+ | 10,000+ | 20,000+ |
|---|---|---|---|
| 1 month | +5.4 | +3.1 | +3.0 |
| 6 months | +6.9 | +5.6 | +5.5 |

3 months and 1 year follow the same order (`summary.csv`). The intervals are mostly clear of zero; the exception is 20,000+ at 1 year, which touches it. Higher minimums are subsets of lower ones, so the three columns are not independent. The change across horizons is within noise at 10,000+ and 20,000+.

[calibration.png](calibration.png): blue, orange and green are world markets with at least 3,000, 10,000 and 20,000 mana traded by the snapshot. Grey is all world markets at the same horizon, with no volume minimum. Error bars are drawn on 20,000+ only, to keep the plot readable.

**This does not show that trading causes the smaller gap.** Heavily traded markets are a different, smaller set of questions.

## Same markets over time

Only 83 markets reach 20,000 mana within 1 month and are still open at 1 year. They resolved YES 17% of the time. Their average price falls from 28% at 1 month to 25%, 21% and 16% at 1 year, so it starts too high and reaches about the right level. This group is small and selected for being long-lived, so this is a lead to check, not a result. There are no intervals on these numbers.

## How this was made

- **Markets:** resolved YES/NO Manifold markets labeled `world`, both status-quo and other, with at least 15 lifetime bettors and 1,000 lifetime volume.
- **Snapshot:** the price after the last bet that moved it, at or before creation plus 30, 90, 180 or 365 days. The market must still be unresolved at that moment.
- **Filters:** at least 3,000, 10,000 or 20,000 mana and 15 bettors by that same moment, so the filter does not use the future.
- **Points:** markets grouped into 10-point-wide price bins. Each dot is the mean price and YES share of its bin. Bins with fewer than 10 markets are dropped.
- **Intervals:** 95%, from resampling creators 2,000 times.

## Caveats

- **Missing markets:** markets still open at data collection are absent. This is likely to matter most for the long horizons, and it could shift these results in either direction.
- **Independence:** resampling creators only partly handles related questions, because markets from different creators can share one outcome. The real intervals are probably wider.
- **Volume:** it sums absolute fill amounts, may count both sides of a match, and has not been checked against Manifold's own number. "20,000" may therefore mean less real trading than it sounds.
- **Changing sets:** each panel has a different set of markets. Only 343 of the 645 markets at 3 months are also among the 645 at 6 months; the equal counts are a coincidence.

Run `.venv/bin/python manifold/other/high_volume_after_creation.py`. Numbers are in `summary.csv`, `bins.csv` and `same_markets.csv`.
