# Heavily traded world markets, 1 month to 1 year after creation

**Heavily traded world markets still lean below the diagonal, by about 2.5 to 5.5 percentage points.** Prices average higher than the YES rate at every horizon: 34% vs 31% at 1 month, 33% vs 29% at 3 months, 30% vs 24% at 6 months, 25% vs 23% at 1 year. The 95% intervals on these gaps only just exclude zero at 1 and 3 months, and touch zero at 1 year. The change between horizons is within noise.

[calibration.png](calibration.png): green is world markets with at least 20,000 mana traded by the snapshot. Grey is all world markets at the same horizon, with no volume minimum.

**This does not show that trading causes the smaller gap.** The heavily traded markets are a different, smaller set of questions.

## Same markets over time

Only 83 markets reach 20,000 mana within 1 month and are still open at 1 year. They resolved YES 17% of the time. Their average price falls from 28% at 1 month to 25%, 21% and 16% at 1 year, so it starts too high and reaches about the right level. This group is small and selected for being long-lived, so this is a lead to check, not a result. There are no intervals on these numbers.

## How this was made

- **Markets:** resolved YES/NO Manifold markets labeled `world`, both status-quo and other, with at least 15 lifetime bettors and 1,000 lifetime volume.
- **Snapshot:** the price after the last bet that moved it, at or before creation plus 30, 90, 180 or 365 days. The market must still be unresolved at that moment.
- **Filters:** at least 20,000 mana and 15 bettors by that same moment, so the filter does not use the future.
- **Points:** markets grouped into 10-point-wide price bins. Each dot is the mean price and YES share of its bin. Bins with fewer than 10 markets are dropped.
- **Intervals:** 95%, from resampling creators 2,000 times.

## Caveats

- **Missing markets:** markets still open at data collection are absent. This is likely to matter most for the long horizons, and it could shift these results in either direction.
- **Independence:** resampling creators only partly handles related questions, because markets from different creators can share one outcome. The real intervals are probably wider.
- **Volume:** it sums absolute fill amounts, may count both sides of a match, and has not been checked against Manifold's own number. "20,000" may therefore mean less real trading than it sounds.
- **Changing sets:** each panel has a different set of markets. Only 343 of the 645 markets at 3 months are also among the 645 at 6 months; the equal counts are a coincidence.

Run `.venv/bin/python src/high_volume_after_creation.py`. Numbers are in `summary.csv`, `bins.csv` and `same_markets.csv`.
