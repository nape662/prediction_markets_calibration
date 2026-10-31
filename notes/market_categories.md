**Automatic word filters classify 91% of downloaded Polymarket questions as bets on asset prices, sports results or interest rates.** About **50,000 questions remain to be classified**. Manifold needs much more reading: **66% of its selected questions, about 25,000, still need labels**.

For our study, a chart covering all Polymarket questions would mostly describe price bets and sports. We need to identify questions about elections, wars, technology and other events before checking whether their probabilities match how often things happen. The unclassified questions are a place to look, not a finished selection.

We currently use seven categories:

**Prices, sports results and interest rates.** “Will Bitcoin cost more than $100,000?” Also match results and central-bank rate decisions. **Equivalent forecasts elsewhere have not been checked for every question.**

**Other questions about the world.** “Will Russia capture all of Pokrovsk by November 30?” Also elections, laws, AI releases and awards. Questions about saying a particular word are included too, but remain separately identifiable.

**Private life.** “Will I pass my driving test?” This includes the question creator and people they know privately.

**Forecasting websites and their users.** “Will I gain followers on Manifold?” Also account profits, website features and questions about another market's probability.

**Chance outcomes.** “Will this coin land heads?” Dice and lottery results belong here too.

**Questions without a clear answer.** Direct opinion polls, such as “What is your favourite colour?”, are candidates. The definition still needs Peter's decision.

**How questions get a category.** Automatic word filters use question text, tags and other market information, including some Polymarket descriptions linking to other markets. The first matching filter assigns the category. They do not use recorded probabilities or outcomes.

Next, inexpensive language models (LLMs) will classify the rest. These include ordinary world questions, missed price bets and sports questions, and questions about private life or forecasting websites. No questions have yet been assigned to “without a clear answer”.

**How much to trust the filters.** In the fresh Polymarket checks, each tested filter made zero to two mistakes per 20 questions. Manifold's private-life filter was weakest: four mistakes per 20 in its first check, and three per 20 randomly chosen markets in its second. It confused Manifold activity with private life, or read a capital “I” as a pronoun.

Some errors were fixed afterwards, without another audit. These small, manual checks therefore **do not measure the final filters' accuracy**; zero mistakes does not establish reliability.

**Three cautions before the next step:**

- **Classify each question separately.** One Super Bowl page can contain match results, a coin toss and halftime songs. Bundles of related questions can mix categories; copying one category across a bundle would introduce mistakes.
- **Clean descriptions before an LLM reads them.** Some contain “resolved YES” or later timelines revealing the answer. Keep the original conditions for deciding the answer; remove outcome updates and probabilities. This cleaning is not implemented yet.
- **These are selected datasets.** Polymarket is a still-growing, partial download of closed markets. Manifold includes only questions resolved YES or NO, with at least 15 bettors and at least 1,000 mana in trading volume. The platforms' category shares therefore do not describe comparable samples of all their markets.

**Three decisions for Peter:**

- **Keep published numbers separate?** I recommend keeping the label and running the study both with and without those questions. A measurement tells us how an answer is decided, not how easy it was to predict.
- **Should asset prices, sports and rate decisions stay together?** I recommend showing them separately in the analysis. An asset price today is not automatically a probability of a future price target, and equivalent bookmaker or futures odds have not been checked for every question.
- **What counts as having no clear answer?** I recommend missing or contradictory conditions for deciding the answer, with direct opinion polls explicitly identified. Humour alone should not exclude a question; predicting a future poll result is still a forecast.

## Details

Counts were checked against the saved [Polymarket](../data/categories/polymarket.parquet) and [Manifold](../data/categories/manifold.parquet) files, without rerunning the [script](../src/sieve.py).

**Polymarket: 2,061,100 markets.** Prices, sports results and interest rates: **1,870,843**; published numbers: **119,891**; other world questions: **19,710**, all from the filter for saying or posting words; forecasting websites and users: **106**; private life: **0**; chance outcomes: **443**; without a clear answer: **0**. Awaiting LLM classification: **50,107**.

**Manifold: 37,680 markets.** Prices, sports results and interest rates: **6,208**; published numbers: **1,297**; other world questions: **102**, all from the filter for saying or posting words; forecasting websites and users: **3,153**; private life: **1,481**; chance outcomes: **535**; without a clear answer: **0**. Awaiting LLM classification: **24,904**.

**Reading the saved files.** The `function` column contains the category: `mirror` means prices/sports/rates; `stat` means published numbers; `world` means other world questions; `personal` means private life; `meta` means forecasting websites/users; `random` means chance outcomes. `unclear` is the proposed label for questions without a clear answer; it is not assigned yet. A missing value means awaiting classification. The `rule` column records which automatic word filter matched; `mentions` identifies questions about saying or posting words.

The `group` column identifies related bundles for sampling, not shared category labels or independent observations. The `topic` column estimates the subject from tags; it has not been formally audited.

**Audit method.** Each tested filter had two checks: 20 random bundles, taking one market from each, and 20 uniformly selected markets. Polymarket checks used the earlier 1.26-million-market portion. Weather and Manifold rate-decision filters were not checked again. Manifold private-life errors were 4/20 with each method initially, then 0/20 from bundles and 3/20 from uniformly selected markets. These judgments come from the previous report; the original audit materials are outside the repository and were not independently rechecked here.
