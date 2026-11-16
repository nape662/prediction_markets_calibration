# Are Polymarket and Manifold well calibrated on non-garbage markets?

**Short answer: more or less, apart from one predictable bias.** Both platforms noticeably overprice "something happens": details in [the other post](TODO-link).

In general:
- **Polymarket is close to calibrated.** One week after a market opens, prices average 24.5% and 22.3% of markets resolve YES (8,810 markets).
- **Manifold overprices YES by about 6 points** (33.8% priced, 27.9% resolved YES; 30,753 markets). A lot of this gap comes from the bias above.
- **On questions where nothing happening doesn't decide the answer**, such as elections and awards, both platforms are close to the diagonal: Polymarket is off by under 1 point, Manifold by about 3.

![Both platforms, all filtered markets](plots/all_markets.png)

*We sort the markets into price bins (0–10%, 10–20%, …). For each bin, the x-axis shows the mean price of its markets and the y-axis shows the share that resolved YES. The number next to each dot is how many markets are in the bin. Bars are 95% bootstrap intervals.*

![Both platforms, no default side only](plots/no_default_side.png)

*The same plot, but only for markets where neither answer wins if nothing happens: "Will X win the election?" rather than "Will X happen by June?". Haiku 5.5 classified markets by the question statement and options.*


## What I did

About 95% of Polymarket markets are crypto and other asset prices ("Bitcoin up or down?"), sports questions that mirror ordinary betting (who wins A vs B, with what score) and weather forecasts. On top of that come things like "how many tweets will Elon post next week". I've seen a couple of papers that check how calibrated the markets are, but they never filtered the junk out. I wondered what happens if you seriously try to look only at reasonable markets.

First, a regex filter removed sports, asset-price and weather markets. Then an LLM answered 25 yes/no questions about the text of each remaining market. The questions target the biggest kinds of junk Opus 5.5 high found in samples of a few hundred markets that got through the regex: coin flips, games about the market itself, and the like. On Manifold, Jev (a cheap classification model) did this labeling, on Polymarket it was Haiku 5.5.[^1] We keep only markets whose answers flag none of these. We also drop markets that score below a hand-picked cutoff on a separate question with a numerical answer, how substantive the question is.[^2]

[^1]: In a 200-market pilot, Jev and Haiku (medium effort, one market per call, as used here) agreed with Opus 5.5 about equally often. I didn't want to spend more money on API calls, so Haiku, which ran on included credit, labeled Polymarket.

[^2]: For people suspicious of this last metric: you are right to be suspicious. But Jev's judgement on Manifold was surprisingly decent wherever Opus 5.5 and I looked (Opus rated 9 of 100 random kept markets as hardly substantive). And the Polymarket markets this whole LLM filter drops are calibrated about like the ones it keeps: shift −0.21 against −0.32, 1 week after opening (one-winner markets left out, see the methodology section).


We also dropped thinly traded moments. On Polymarket, a market counts at a given moment only if $1,000 had already been traded on it. On Manifold, at least 15 different people must have bet on it by then (for a multiple-choice question, on the question as a whole).

Another "junk market" caveat is weighting by events. An "event" is one question with many options split into many yes/no markets. For example, "Who will be the next US president?" becomes one market per candidate. Weighting per market makes the numbers less noisy, weighting per event makes few many-option markets not dominate the analysis. The same holds for Manifold's multiple-choice questions, split into one market per option. Thankfully, both ways of weighting give basically the same result. The plots count every market separately. The numbers with each event weighing one are in the methodology section below.

Finally, series. Some questions repeat with only a number or date changed, such as weekly tweet counts or "ceasefire by June / July / August". These could have needed a rule, such as "count at most N events per series". Turned out, we didn't need one: after our filters, the few remaining long series carried little weight, and capping each series at 5 events barely changed anything.


## Detailed methodology for nerds and especially LLMs, Claude-generated

I apologise for having this part auto-generated, but I'm pretty burnt out from what was supposed to be a one-weekend project. The full version, with every count and check, is in [METHODS.md](https://github.com/nape662/prediction_markets_calibration/blob/master/METHODS.md).

- **Data:** Polymarket's APIs (Gamma, CLOB), plus the Becker on-chain trades dataset for dollars traded; resolved Yes/No markets that closed before 2026-02-02. Manifold's public API, fetched 2026-10-30 (binary) and 2026-11-14 (multiple-choice); each multiple-choice question is split into one yes/no market per option.
- **Moments:** 1 day, 1 week and 1 month after Polymarket trading starts or the Manifold market is created. Not "N days before resolution": "by date" questions resolve early when YES happens, so that moment depends on the outcome.
- **Prices:** Polymarket, the last hourly CLOB price at or before the moment, at most 3 days old; markets in one-winner events whose prices sum to more than 130% are dropped. Manifold, the probability after the last bet.
- **No default side:** Haiku 5.5 answered "If nothing new happens and the current state of affairs simply continues until the deadline, how does this market resolve?" with YES, NO or NONE, from the text only. NONE means no default side (full prompt in [the other post](TODO-link)).
- **Shift:** one number added to every price's log-odds so that the mean price equals the YES rate. Below 0 means YES is overpriced: at −0.32, a market priced 50% resolves YES about 42% of the time. One-winner markets are left out of the shift, because their prices add up to about 100% by construction. 95% intervals resample Polymarket events or Manifold creators, 500 times.
- **Other columns:** the Brier baseline always predicts the group's own YES share; AUROC measures ranking only; balanced accuracy calls YES above 50%.

### Results, 1 week after opening

| | Markets | Mean price → YES rate | Shift without one-winner markets (95%) | Brier (baseline) | AUROC | Balanced accuracy |
|---|---|---|---|---|---|---|
| Polymarket, all | 8,810 | 24.5% → 22.3% | −0.32 (−0.42 to −0.24) | 0.090 (0.173) | 0.91 | 0.79 |
| Polymarket, no default side | 3,810 | 23.9% → 23.0% | −0.18 (−0.41 to +0.04) | 0.078 (0.177) | 0.94 | 0.82 |
| Manifold, all world | 30,753 | 33.8% → 27.9% | −0.51 (−0.59 to −0.44) | 0.128 (0.201) | 0.87 | 0.78 |
| Manifold, no default side | 11,624 | 31.3% → 28.0% | −0.37 (−0.50 to −0.22) | 0.115 (0.202) | 0.90 | 0.79 |

Counting each event once gives the same picture: −0.36 on Polymarket and −0.51 on Manifold. The 1-day and 1-month numbers are in `plots/metrics.csv`.

**Read with care:**
- The two platforms' samples contain different questions, so these numbers don't say which platform forecasts better.
- Both platforms' numbers probably understate the overpricing: markets still unresolved at the fetch are missing, and recently resolved ones lean YES. Keeping only markets whose stated deadline passed at least 30 days before the fetch moves the shift from −0.51 to −0.62 on Manifold and from −0.32 to −0.40 on Polymarket. The other post uses this filter throughout.
- Manifold's lifetime requirement of 1,000 mana traded uses information from after the moment.

**Reproduce:** `python src/both_platforms.py` (code, labels and prompts: https://github.com/nape662/prediction_markets_calibration).
