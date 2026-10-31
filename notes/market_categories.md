# Market categories: what the rule-based "sieve" finds

**What this is.** `src/sieve.py` puts every market into a category by its **function**, using only the question text, event title, tags/topics, series metadata, and (Polymarket only) descriptions that link to another Polymarket market. It never uses price or outcome. What the rules can't catch cleanly gets `rule = null` and goes to a cheap LLM later. Output: `data/categories/{polymarket,manifold}.parquet` with columns `id, group, rule, function, topic`.

**Main result.** Polymarket is 91% markets that copy a price or odds from elsewhere: crypto/stock prices and sports games. After the rules, only **~50k Polymarket markets (2.4%) in ~11.4k groups** are left, mostly genuine world questions. Manifold is the reverse: **66% of markets (24.9k in 22.8k groups)** are left for the LLM, mostly politics, AI and tech.

**This version fixes the bugs found by two reviews (Sol, Astra).** The category design is unchanged; Peter decides that (see the last section).

---

## The labels

**Function (main label).** Rule = a regex rule catches it. LLM = no clean rule, so the LLM decides.

- **world**: a genuine question about the world with no liquid outside price. Elections, wars, laws, AI releases, court cases, awards. *LLM.* Exception: "Will X say/post 'word'" markets are caught by the `mentions` rule and labeled world; they can be sliced out by `rule`.
- **mirror**: the outcome is a price that trades elsewhere, or has liquid bookmaker or futures odds. *Rule* for asset prices, sports results and central-bank rate decisions.
- **stat**: a threshold or bracket on a published number: a temperature reading, tweet/view counts, box office, Rotten Tomatoes score, CPI/jobs, earnings beat, App Store/Netflix/LLM-leaderboard rank. *Rule.*
- **personal**: about the creator or someone they know privately ("Will I pass my driving test?", "Will my roommate talk in his sleep?"). *Rule* for first person; *LLM* for third person.
- **meta**: about forecasting platforms themselves. Examples: a market's own price, traders or resolution; Manifold leagues, account profit, followers, features, the company; another market's price. *Rule + LLM.*
- **random**: coin flips, dice, lotteries, Super Bowl coin toss, NBA draft lottery. *Rule.*
- **unclear**: no real question (polls, riddles, jokes). *LLM only.* The definition is still open, see the last section.

**Topic (secondary, for slicing).** sports, crypto, ai, economy, politics, science, tech, culture. Taken from tags, first match in that order; null if no tag matches (0.7% of Polymarket, 22% of Manifold). **Topic was not formally audited**; in about 200 rows I read, roughly 1 in 10 looked off.

**Polymarket meta exists, but only as derivatives.** 106 markets (48 groups) resolve on another Polymarket market's price ("Odds of Khamenei out by March 31 over 40%?", "Fed Derivative: 'No Change' favored on Monday?"). The rule finds them through descriptions that link to that market and talk about its price or favorite. The Manifold personal/meta text rules still run only on Manifold: on Polymarket they produce only false hits ("Hawai'i", "MANA eSports").

---

## Funnel

Rules run in this order: Polymarket meta (derivatives) or Manifold meta → personal (Manifold) → mentions → random → asset_price → sports → central_bank → weather → stat. A market gets the first rule that matches.

**Polymarket input:** the first 2,061,100 markets of the still-running fetch (761,165 events, 27,431 groups), i.e. markets created up to about the end of July 2026. **Manifold input:** 37,680 markets (32,864 groups).

| Function | Polymarket markets / groups | Manifold markets / groups |
|---|---:|---:|
| mirror | 1,870,843 / 13,253 | 6,208 / 4,810 |
| stat | 119,891 / 1,985 | 1,297 / 925 |
| world (mentions) | 19,710 / 801 | 102 / 101 |
| meta | 106 / 48 | 3,153 / 2,729 |
| personal | – | 1,481 / 1,433 |
| random | 443 / 23 | 535 / 40 |
| **left for LLM** | **50,107 / 11,414** | **24,904 / 22,839** |

**What changed vs the previous version** (same 1.26M-market prefix, so the numbers are comparable):
- Sports metadata alone no longer counts: the question has to be about a competition result. About 500 Polymarket markets moved from `sports` to the LLM: Taylor Swift on broadcast, anthem length, trades, suspensions, halftime shows.
- 371 mention-tagged Polymarket contracts moved from sports/stat/weather to `mentions` (364 of them from sports).
- On Manifold, bare "profit/profitable", "trustworthy" and "portfolio" no longer count as meta, so corporate profitability questions go to the LLM.
- Platform activity written in first person ("Will I promote to Diamond?", "my follower count", "Will I resolve a market controversially?") is now meta.
- Company names no longer count as asset evidence without stock context. A parenthesised "(HIGH)/(LOW)" no longer counts as a ticker, and years no longer count as price numbers. So Vision Pro prices, Google search share, Claude Code commits and "Tron: Ares" box office left `asset_price`.
- Markets with no event now get group `m:<market id>` instead of a null group (14 Polymarket markets).

---

## Precision of the revised rules

Fresh samples after the fixes, per rule: 20 random groups (one random market each, G) and 20 uniformly random markets (M). Counts are my judgement of *function*. Errors marked "fixed" were corrected after the sample and not re-audited. Polymarket samples come from the first 1.26M markets, the part where I had text loaded. Weather and Manifold central_bank were unchanged and are not re-sampled (earlier: 0/40 and 0/25).

| Rule | Wrong G / M (of 20) | Example error |
|---|---|---|
| PM meta, random, central_bank | 0 / 0 each | (FX "USD/TRY above 25" sits in central_bank; still mirror) |
| PM mentions | 1 / 0 | "Fear & Greed Index says 'Extreme Fear'?" (fixed) |
| PM asset_price | 2 / 0 | "Trump flips Kamala on Silver Bulletin?", "Solana flips ETH in daily fees?" (both fixed) |
| PM sports | 1 / 0 | "Where will Kenneth Walker III play in 2026-27?" |
| PM stat | 0 / 0 | (boundary: "Number of North Korea missile tests in May?") |
| MF meta | 0 / 0 | (boundary: "Will I throw a party for Manifold users?") |
| MF personal, 1st sample | 4 / 4 | "Will I have less than 3 followers?" (meta, fixed); "AIME I" read as first person (fixed) |
| MF personal, 2nd sample | 0 / 3 | "I stay in masters this league?" (meta, fixed); "Google … at I/O 2026" (fixed) |
| MF mentions | 1 / 1 | the same Fear & Greed question (fixed) |
| MF random | 3 / 0 | "Will the responder one-box in this Newcomb's Problem?" (a game, fixed) |
| MF asset_price | 1 / 0 | "Will @Champion1024 get a girlfriend before NVIDIA's market cap hits $5.5T?" |
| MF sports | 1 / 1 | "Will Australia host the 2030 World Cup?" |
| MF stat | 2 / 1 | "Will any Billboard Hot 100 song be composed by AI?" |

**Reading it.** Polymarket rules are now clean: about 0–1 wrong per 20. Manifold personal is the weakest rule. Its errors are mostly meta-vs-personal confusions (both are not world), and a few cases where a capital "I" is not a pronoun. 0 errors in 20 draws still allows an error rate up to about 14% (one-sided 95%), so treat these as rough.

---

## Boundary cases and how to decide them

- **Long-horizon crypto or stock price ("Where will ETH be in a year?") → mirror** at any horizon, if the asset already trades. Not mirror: tokens or IPOs not yet trading, private-company valuations (Stripe, SpaceX), fundamentals (ETF approval, airdrops, fees). See open question (b).
- **Sports.** Competition results are mirror: games, props, halftime results, season winners, MVP-type awards, esports. Off-field news goes to the LLM: transfers, trades, suspensions, coaching changes, retirements, broadcasts, anthem, halftime show, fantasy football.
- **Elections, Oscars, Eurovision → world**, even though bookmakers price the big ones.
- **Rate decisions → mirror.** Fed chair nominations, Powell's tie and the odds of a Fed market are not mirror: they go to the LLM or to Polymarket meta.
- **Earnings:** "beat EPS estimate" → stat. "Stock up or down after earnings" → mirror.
- **Personal vs meta.** Your own life → personal. Your own platform standing (league, account profit, Manifold followers, creating or resolving markets) → meta. "Will I hit a 100 day streak?" with no stated activity → left to the LLM.
- **Mentions** precede sports/stat/weather/random: "Will the announcers say 'Heisman' 5+ times?" is a mention, not a game result.
- **Streamer markets** (Destiny, ~2,000 Manifold markets) → world, topic culture.

---

## Grouping, and two warnings for the LLM step

- **Label per market, not per group.** A Polymarket series or even one event can mix functions. Examples: the `nba` series has games plus trades and suspensions; one Super Bowl event has quarter results, a coin toss and Rihanna's songs. Groups are only for sampling and compression. The code already labels each market on its own.
- **Sanitize descriptions before the LLM sees them.** Some descriptions contain the outcome ("(resolved YES)", later rate-change timelines). Keep the original resolution criteria; strip resolution updates, probabilities and outcome notes. (Not implemented yet.)
- **Polymarket:** group = series, else event, else market id. 2.06M markets → 761k events → 27.4k groups. For error bars, cluster by event, not series.
- **Manifold:** group = creator + question with digits, months and weekdays replaced. 37,680 → 32,864. In 40 + 30 (Astra) sampled merged groups, no group mixed unrelated questions.
- **Polymarket data is partial.** The fetch reads in id order, roughly creation order. Markets created after about July 2026 are not in this run.

---

## What the remaining "world" core looks like

**Polymarket (50k markets, 11.4k groups, 6.7k of them single markets).** By group topic: politics 49%, no tag 13%, culture 10%, crypto 9% (non-price), economy 7%. Examples:

- "Will Russia capture all of Pokrovsk by November 30?"
- "Ethereum ETF approved by end of March?"
- "Oscars: Will 'Emilia Pérez' win Best Sound?"
- off-field sports: "Giannis traded during NBA Draft?"

**Manifold (24.9k markets, 22.8k groups, almost all one-off).** By group topic: politics 38%, AI 13%, culture 10%, no tag 18%. Examples:

- "Will Starship launch to orbit at least 8 times before the end of 2025?"
- "Will Lula appoint Flávio Dino to the Supreme Court by end of 2023?"

The remainder is **not purely world**. In Astra's samples, 10/40 Polymarket market draws and 7/40 Manifold draws belong to families the rules could have caught: index results, untagged football, Metacritic scores, follower counts. Expect the LLM to move a noticeable share to stat, mirror, meta or personal [verified on samples; the overall share is a guess].

---

## Open design questions for Peter (nothing changed yet)

**(a) Keep `stat`, or merge it into `world` with subtypes?**
- **Me:** keep it as a plotting class. These are bracket ladders on public trackers, a different forecasting task.
- **Astra:** merge. `stat` describes how the outcome is measured, not whether it is easy: "bird-flu cases by June" or "who leads the AI leaderboard" are real forecasts. If kept, define it literally as "a published numeric measurement" and apply that to the remainder too.

**(b) Keep `mirror`, or rename it to an observable `market_price`?**
- **Me:** keep mirror for asset prices, sports and rate decisions: there is a liquid outside price for (nearly) the same outcome.
- **Astra:** `mirror` overclaims. Today's price is not a future exceedance probability; options don't cover every contract; and bookmaker liquidity for, e.g., a dog-surfing championship or Colombia's central bank isn't established. She proposes `market_price` (financial asset price targets, any horizon) and treating sports and rate decisions as world with a topic or subtype slice. If mirror stays, call it an unverified benchmark candidate.

**(c) What does `unclear` mean?**
- **Me:** not a real question: polls, riddles, jokes.
- **Astra:** criteria that are insufficient or contradictory. A funny title with clear criteria ("Will Claude become a Pokémon Master?") is world. A forecast of a future poll is not the same as a direct opinion poll.

---

## Details

- Run: `python src/sieve.py`. It took 7.3 min and 2.7 GB RAM on the 2.06M-market prefix; time and memory grow with the fetch. It reads only the bytes listed in `state.json` and retries if that file is mid-rewrite.
- Inputs: Manifold `full.jsonl` (already filtered to YES/NO, ≥15 bettors, ≥1000 mana volume). Polymarket: all closed markets in the partial file, including 50/50 and zero-volume ones. These selections happen before the sieve; report them separately from function.
- Audit seeds: 2026 (Polymarket, Manifold meta), 2027 and 2028 (other Manifold rules). The scripts are in the session scratchpad, not in the repo.
