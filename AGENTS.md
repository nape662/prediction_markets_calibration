# AGENTS.md

## Project

Цель проекта — небольшое воспроизводимое исследование: соответствуют ли вероятности Polymarket и Manifold фактическим частотам исходов, особенно на содержательных вопросах вне массовых коротких криптоставок. Желательный масштаб первого результата — выходные или немного больше, а не исчерпывающая исследовательская программа. Just good enough that after people see that plot which roughly looks as y=x, and they dig into "what it actually measures" it is something real and something they care about, without major mistakes in methodology. Perhaps, in the ideal case, we manage to filter out the really "markets for which no easy objective source of truth does not exist and which would really help people get extra knowledge quickly" and see how calibrated they are 12h/week/month/year before resolution (and compare those markets and simpler markets, with less filtering). 

## Working with me
- На русском обращайся ко мне только на «ты», никогда на «вы».
- Ask, don't assume. If something is unclear, ask before writing a single line. Never make silent assumptions about intent, architecture, or requirements.
- Read me generously, do not nitpick, when they re explain what they understood to you. Again, I am smart and generally competent.
- Flag uncertainty explicitly. If you are not confident about an approach or technical detail, say so before proceeding. Confidence without certainty causes more damage than admitting a gap.
- **My words are suggestions, not commands.** I'm gesturing at what I want. You have agency and experience: question, argue, propose better approaches, dig deeper into the topic than I asked. Push back when I'm wrong.
- **Be very critical of my ideas in this project.** I know basically nothing about prediction markets or statistics. I hang out in Manifold's AI section, but mostly I don't know what's really going on there.
- **Subagents are capable.** Give them rich context, the goal, and the constraints; don't micromanage how. They'll figure it out.
- When you run `cat`, send the output to a file and show only the lines that matter.

When Peter asks you to add something to instructions, add only that. Don't add extras he didn't mention. Agents you hand the task to can work out the details themselves; if it's unclear, ask Peter.

## Code
- **Minimal edits.** If 1 line does it, don't change 100. If 10 lines does it, don't write 100. Smallest diff that solves the actual problem.
- **Short, effective but maintainable and easily readable code.** No unnecessary abstractions or unasked for flexibility, few comments. Clean up after yourself: no leftover debug code, temp files, or dead code.
- **Tests: strongly prefer E2E.** Avoid unit tests unless there's a clear reason. Generally test and re-check your work less.

Never hide errors in experiment-critical code. Crash immediately instead. Don't silently substitute anything that would distort the results:
- If the dataset didn't load, don't swap in a synthetic one.
- If there's a division by zero, don't plug in a made-up number.

The only exception is a very long run (think 3 weeks), where recovering can be worth it.

When I say to "optimise" the code or simplify it, we are really hunting for 80/20 changes of some prior really stupid choices: adding caches, deduplicating functions, etc. I'm not interested in obsessive hyperparam tuning and stuff, usually. 

Commit your work, keep git state clean!

Run experiments in their own separate tmux sessions, so they finish even if Peter closes Claude.

Claude and ChatGPT, you two are working side-by-side.
Claude, when you write a substantial chunk of code, ask latest Sol model at High reasoning to review the diff critically for bugs. 
Chat, when you write a substantial chunk of code, you ask latest Opus model at High reasoning to /simplify your work. Trust that Opus correctly simplifies it, do not re-check its results, do not sandbox it extra, let it edit the project files directly, and yes I approve of passing project files to Claude. And please don't launch it with "no-persistent-session" let it be a normal persistent session of Claude. 

## Writing style

Use **simple, direct prose**, yet very concrete sentences such that the person always understands the important details. No mannered writing, unexplained jargon, or cryptic shorthand. Every noun must still make sense to them a week from now, with this conversation forgotten.

Write for someone with **high intelligence, slight ADHD, and low processing speed**. They can understand complex ideas; make them easy to follow.

- **Start with the point:** what is happening, what are we trying to do, or what comes next?
- **Limit information per message.** Explain what matters now; avoid dumping every detail.
- **Make it scannable.** Use short paragraphs and selective bolding. Use 3–6 bullets only when helpful with bias towards $\leq 3$. NEVER more than 4-6 bullet points. If your draft has more bullet points, compress/merge them.
- **Keep replies under 120 words**, ideally shorter, unless more detail is requested.

The reader should feel ready to act or ask further clarifying questions, not overwhelmed.

## Reports
- Truth over what you did is more important than beauty of headline results and numbers.
- Reports should be concise and do not need every single technical detail in them. 
- **Only headline numbers in a report's body.** Supporting numbers (parameter counts, GPU memory, timings, configs) go in one short "Details" section at the end. Full per-run numbers live in `metrics.csv`.
- **Tables: aim for 6 entries or fewer** (cells, not rows). Significantly more numbers than that → make a plot instead or annotate.
- **Reports carry your interpretation.** Read the CSV yourself and write what it means, in the same plain, short style as chat: what changed, by how much, and whether it is beyond seed noise. 
- **For every plot, there must exist an explanation of the process that produced the plot, so that the person would in theory be able to reproduce the main parts of it, either in plot description or elsewhere:** Example: "We train DINOv2 with only a learned head, or with head + LoRA, on X images (x-axis) and measure Y on the validation set. Rerun 5 times with different seeds, same image split. For every X, training stops once the loss on a separate stopping set hasn't improved for 10 epochs; the best checkpoint is evaluated on a validation set common to all X."
- **Corrections are never silent.** If a plot uses any correction (e.g. "12h before resolution" actually measured from a corrected anchor, so it is really 36h), say so under the plot in big red letters, and always make two plots: with and without the correction.
- **Reports are not academic papers.** They exist so that Peter can understand what happened. Don't copy the paper style; it is unreadable.

## Prediction-market calibration: good and bad methodological choices in prior work

Papers referenced
- Dickerson et al., PNAS 2026 (doi 10.1073/pnas.2615627123). ~1M records from four platforms: Kalshi 762,031; Manifold 149,109; Polymarket 98,259; Metaculus 4,723. The pooled result mostly describes Kalshi. Data pipeline: Themis (github.com/wasabipesto/themis).
- Reichenbach & Walther, SSRN 7552098, 2026 ("R&W"). 779,344 resolved binary Polymarket markets built from on-chain trades. Crypto (302,890) and sports (369,950) dominate; short crypto markets are not excluded.

Good choices worth copying

1. The market, not the trade, is the unit. R&W take one price per market per time interval, so a contract with a million trades does not get a million votes.

2. Plain empirical calibration plots. Group similar forecasts and compare mean forecast with realized frequency, showing group sizes. Quantile bins give equal counts; fixed-width bins are easier to read. Many identical prices make quantile bins awkward.

3. Comparisons on a fixed set of markets. R&W compare adjacent time points only on markets observed at both, and re-run on markets present in all ten intervals. Otherwise "improvement" can just be a change in which questions are in the sample. (The all-ten-intervals sample in turn selects more active markets, so it works as a robustness check, not as the main sample.)

4. A paired external benchmark. R&W compare Polymarket with bookmakers on the same matches at the same moment. The same idea carries over to Polymarket vs Manifold: same event, same time, same resolution rule. Mean scores on different question sets say nothing about which platform is better. Beating another forecaster in a paired comparison doesn't show either one is good.

5. Both Brier and log loss. Brier is mean squared error; log loss punishes confident misses more. Prices of exactly 0 or 1 need explicit handling for log loss. Calibration and informativeness are different things: a constant 50% on a fair coin is perfectly calibrated and useless.

6. Logistic recalibration as a summary: logit(pi) = alpha + beta * logit(p). Perfect calibration is alpha = 0, beta = 1. Calibration-in-the-large (CITL) estimates alpha with beta fixed at 1. beta > 1 means probabilities squeezed toward 0.5 (favorite-longshot-like); beta < 1 means too extreme. Two parameters can hide local errors, so this complements the plot rather than replacing it.

7. Separating bias types. R&W distinguish the cheaper outcome (longshot) from the outcome listed first in the interface (default, usually YES). Underpriced favorites and overpriced YES are different effects.

8. Sample-composition checks (PNAS): drop sports and finance, high-volume subset, duration strata, a small diversified set of distinct questions. The useful idea is to check whether the result survives without mass-produced repetitive markets.

Errors and pitfalls, with example fixes

1. Winner-only selection.
Error: for multiple-choice markets where exactly one option wins (Manifold, Metaculus), Themis/PNAS keep only the winning option's price history and set its outcome to 1 (confirmed in Themis extract/src/platforms/manifold.rs and metaculus.rs on the current main branch). This keeps "30% -> happened" and drops all the "30% -> didn't happen" options, pushing calibration upward by roughly f*(1-p) in a bin where a fraction f of records are such winners. That shape matches the Elections "underestimation" PNAS reports at low and mid probabilities (a hypothesis, not checked against their data).
Fix: use plain binary questions only, or include every option of a multi-choice market (with dependence handled and sensible weights), or pick the tracked option without looking at the outcome.

2. Many rows are not many independent events.
Error: ladders ("BTC above 80/85/90k?", "ceasefire by June/July/August?"), brackets (mutually exclusive ranges of one quantity), cross-platform copies and related election markets are all decided by one shared outcome; one surprise breaks dozens of forecasts at once. R&W cluster by market, which handles repeated snapshots of one market but not dependence between markets of one event. PNAS has no clustering at all in its domain-level claims.
Note: bracket prices summing to ~1 makes the overall mean match the overall hit rate. It does NOT make each probability bin calibrated.
Fix: cluster bootstrap over groups of related questions (event, storyline, date). Cheap check: drop the biggest storyline or election cycle and recompute.

3. Underpowered "independence" checks.
Error: PNAS's robustness subset is 1,067 questions (~50 per category, deduplicated by GPT-4.1-mini). With ~100 questions per bin near 50%, the noise is about +/-10 pp, so "calibration remained intact" mostly reflects low power. It is a pooled check and says nothing about the domain-level deviations. LLM deduplication also doesn't guarantee statistical independence.
Fix: a larger deduplicated set, a saved list of selected questions, and a manual audit of a sample of the dedup decisions.

4. Forecast time that depends on the outcome.
Error: R&W split the span from first to last trade into ten parts; PNAS uses fractions of question duration. The last trade and the resolution can come after the answer is known (R&W's last bin has Brier 0.0043), and YES outcomes often close "by date" markets early. Late-stage "accuracy" then partly reflects knowing the answer. Possible artifact: R&W's small late favorite-longshot effect (-0.2 to -0.4 pp) is the size you'd expect from post-outcome trading at 0.99-0.999 while waiting for resolution (hypothesis, untested).
Fix: fixed calendar snapshots (prices of all markets open on date D), a fixed time after opening, or a fixed time before a pre-announced event date. These answer different questions. Use only information available at the snapshot; with calendar snapshots, long markets appear repeatedly and some questions are still unresolved.

5. Trade price is not the displayed probability.
Error: the last trade fills at the bid or ask, not the mid, which can create a small apparent YES/default bias. R&W's default overpricing (0.2-0.8 pp) is about the size of a half-spread (hypothesis; Mentions markets at -5 to -6 pp are too large for this). On-chain trades give execution history but not the historical order book or the displayed forecast. With no new trades, the last price goes stale.
Fix: midpoint or quote data where available, or compare buyer- and seller-initiated trades separately. API vs on-chain depends on what is being measured.

6. The pooled diagonal hides the errors that matter.
Error: sports and crypto can dominate; opposite domain errors cancel; a linear plot hides relative errors in the tails (5% forecast vs 2% realized is only 3 pp but 2.5x in odds). PNAS's "virtually no Brier difference after recalibration" is weak evidence, since a small reliability term doesn't guarantee good relative accuracy on rare events. Bürgi, Deng & Whelan find a strong favorite-longshot bias on Kalshi (contracts under 10c lose >60%), which PNAS doesn't cite.
Fix: separate plots per platform; per topic and tails where there are enough independent events; logit axes or coarse tail bins.

7. Interval mistakes in PNAS.
Error: their CIs use ten estimates on overlapping nine-fold subsets with SE = SD/sqrt(10). For a delete-one-group jackknife with K = 10 the multiplier should be (K-1)/sqrt(K), so as described the intervals are ~9x too narrow (simulation gives 9.3x). The text may describe the code incorrectly. Fig. 1B/C shows the outcome spread in a hypothetical sample of 100, not a confidence interval for the bin frequency.
Fix: cluster bootstrap, or a correct jackknife.

8. Bookmaker margin removal (R&W).
Error: proportional normalization of bookmaker odds is known to leave longshots overpriced, so R&W's "bookmakers price longshots higher than Polymarket" may be partly a method artifact. It is also unclear whether they used pre-closing or closing average odds.
Fix: Shin or power method, or Pinnacle closing odds, with timestamps aligned to the Polymarket snapshot.

9. Recalibration and exploitability.
A recalibration fitted on an early period and tested on a later one (without related events leaking across the split) shows whether the biases are stable. One model failing to improve doesn't prove market efficiency. Better log loss doesn't prove profit: trading also pays fees, spread, execution costs and the cost of locked capital.

Sources
- PNAS: https://doi.org/10.1073/pnas.2615627123 (methods pp. 7-8, robustness pp. 3-4, Fig. 3; SI is separate)
- R&W: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7552098 (Sections 3.2-3.4, Table 5, Appendix A2)
- Themis: https://github.com/wasabipesto/themis (extract/src/platforms/manifold.rs, metaculus.rs)
- Becker dataset (Polymarket/Kalshi trades and markets as Parquet, 36 GiB compressed): https://github.com/Jon-Becker/prediction-market-analysis
- Bürgi, Deng & Whelan (Kalshi favorite-longshot): https://www.karlwhelan.com/?p=2402
- Cardozo & Rivero-Wildemauwe (Polymarket favorite-longshot): https://arxiv.org/abs/2609.12878
- Yurchyna (composition shift and bias measurement, Kalshi): https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7364100
