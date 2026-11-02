# Luna audit of markets labeled “no default” by both classifiers

**This audit does not justify treating the agreement group as safe.** GPT-6 Luna at low reasoning flagged 6 of 100 markets for substantial outcome-dependent timing, marked 1 unsure, and marked 93 no. These are Luna’s classifications, not a verified error rate. Reading the requested random examples reveals clear missed mechanisms, including an explicit early-NO rule. Several positive flags also have questionable explanations.

**The concrete counterexample we needed:** “Will Joe Biden receive more than 50.00% of the popular vote in the 2024 general presidential election?” Its rules explicitly allow NO when he drops out or dies, but otherwise wait for the official vote count. This is a real early-elimination mechanism, rather than a speculative correlation between race duration and winner. Both original classifiers put it on the no-default side, and Luna missed the timing issue too.

**Ten random markets.** Selected before seeing Luna’s results, independently of the audit flags. YES/NO below refers to Luna’s timing-asymmetry judgment, not the market outcome. Titles are verbatim. Notes are my reading of the supplied descriptions; they do not alter Luna’s saved answers.

**1. [Will GPT-5 like to delve?](https://manifold.markets/Bair/will-gpt5-like-to-delve) — Luna: NO**

Ten tests after GPT-5 becomes available; five uses of “delve” means YES. Both results use the same test procedure.

**2. [Will any of Biden, Trump, or @Mira be elected president in 2024?](https://manifold.markets/Orangey/will-any-of-biden-trump-or-mira-be) — Luna: NO**

Resolves according to whom liberal news outlets generally believe won the election.

**3. [Will Premier Doug Ford win the 44th Ontario General Election?](https://manifold.markets/dittopoop/will-premier-doug-ford-win-the-44th) — Luna: NO**

The rules also say NO if Ford steps down as leader. That provides an early-NO path which Luna’s explanation overlooks; the exact settlement time is not specified.

**4. [Will the White Smoke come after 3 or more Black Smokes during the Papal Conclave?](https://manifold.markets/strutheo/will-the-white-smoke-come-after-3-o) — Luna: NO**

No description. The question counts black-smoke announcements before white smoke; Luna does not identify a days/weeks asymmetry.

**5. [Will more than 25% of US Adults believe the 2024 Election was illegitimate in February 2025?](https://manifold.markets/Gen/will-more-than-25-of-us-adults-beli) — Luna: NO**

The creator may resolve without polls on February 1 if nobody contests legitimacy, otherwise wait for polls and possibly additional polling. Luna’s common-timing explanation overlooks these different evidence paths; their actual delay is unspecified.

**6. [Mistral Large 2 outperforms Llama 3.1 405b Instruct on Chatbot Arena on August 12th?](https://manifold.markets/transmissions11/mistral-large-2-outperforms-llama-3) — Luna: NO**

Compares the models on Chatbot Arena on August 12: a measurement at a named date.

**7. [Will Starship visit the moon? (2023)](https://manifold.markets/Gigacasting/will-starship-visit-the-moon-2023) — Luna: NO**

The title asks about a moon visit during 2023; description says “Fly-by, aka dearMoon.” A visit can establish YES before year-end, while its absence needs the deadline or a definitive cancellation. Luna’s common-measurement explanation is unsupported.

**8. [Will Joe Biden receive more than 50.00% of the popular vote in the 2024 general presidential election?](https://manifold.markets/father/will-joe-biden-receive-more-than-50) — Luna: NO**

The description explicitly says: “I’ll resolve it early if e.g. he drops out of the running or dies before then but otherwise I’ll wait for the official count to come in.” This directly contradicts Luna’s NO flag.

**9. [In the Gorton and Denton by election, will the Greens get more votes than Labour?](https://manifold.markets/PontiMin/in-the-gorton-and-denton-by-electio) — Luna: NO**

Compares Green and Labour vote counts in the same named by-election.

**10. [Will there be >=100,000 confirmed cases of monkeypox worldwide by the end of 2022?](https://manifold.markets/JoeBrenton/will-there-be-100000-confirmed-case) — Luna: YES**

A cumulative 100,000-case threshold can be reached before year-end; failure requires waiting. This is also an apparent missed default-outcome case, despite Luna calling default_outcome=no.

**All six markets Luna flagged.** These are all positive flags, without selecting only the convincing ones. The monkeypox question also appears in the random ten.

**1. [Over the next five days, I am going to use ChatGPT to recreate iconic album covers. Will they be recognizable?](https://manifold.markets/VerySeriousPoster/over-the-next-five-days-i-am-going)**

Luna: YES can be established once at least three of the five image markets have resolved correctly. NO can be established once three have failed, potentially before all five two-week markets finish.

My assessment: Questionable flag. Three successes and three failures are symmetric stopping rules. Five markets opened on consecutive days and each lasts two weeks; the claimed weeks-long difference between their completion dates is unsupported. This is not a demonstrated YES-versus-NO timing mechanism.

**2. [Will Joe Biden complete a second term as President?](https://manifold.markets/Andrew40384/will-joe-biden-complete-a-second-te)**

Luna: YES requires Biden to complete the second term, so it cannot be settled until that term ends. NO can be settled as soon as he fails reelection or leaves office, potentially years earlier.

My assessment: The timing mechanism is clear. However, Luna’s default-outcome explanation assumes reelection: at creation, reelection itself still had to happen. Keep the timing finding separate from that label.

**3. [Will there be >=100,000 confirmed cases of monkeypox worldwide by the end of 2022?](https://manifold.markets/JoeBrenton/will-there-be-100000-confirmed-case)**

Luna: YES can be established when reported confirmed cases first reach 100,000. NO requires the end-of-2022 cutoff to pass below the threshold.

My assessment: A cumulative 100,000-case threshold can be reached before year-end; failure requires waiting. This is also an apparent missed default-outcome case, despite Luna calling default_outcome=no.

**4. [🔥 Will More Than 1,355,802 Acres Burn During The 2024 California Wildfire Season?](https://manifold.markets/Lunar/-will-more-than-1355802-acres-burn)**

Luna: YES can be established once 1,355,802 acres have burned during 2024. NO requires the 2024 season/year total to be complete and the data available.

My assessment: Early threshold crossing is a plausible information-timing mechanism. The description also warns that data may not be available until 1–2 weeks after year-end, so early formal resolution is not established by the text.

**5. [Will Polymarket give biden more than 30% probability on Biden winning the election, in the next week?](https://manifold.markets/Bayesian/will-polymarket-give-biden-more-tha)**

Luna: YES requires a 30% average over a 24-hour window within the next week, so it can be confirmed after such a window. NO is only established when the week ends without a qualifying window.

My assessment: A qualifying 24-hour average may finish days before the week ends. This also looks like a default-NO mechanism that Luna failed to recognize as such.

**6. [Will the runner-up in the 2024 US Presidential Election accept their defeat by Dec 31, 2024?](https://manifold.markets/Mosiah/will-the-runnerup-in-the-2024-us-pr)**

Luna: YES is assessed by December 31, 2024. NO can arise from a qualifying post-election court case during 2025, or from the other specified rejection conditions.

My assessment: Ambiguous rules. If a court case at any time in 2025 can force NO, December 31, 2024 is not necessarily a valid final YES date. Luna’s specific timing claim is too confident.

**What this means for the next decision.** The result is not negative, and this Luna-low pass is not reliable enough to estimate how common the problem is. I would not use it to waive further review of the agreement group. It does not yet show that every market needs relabeling either. The useful next audit would explicitly include withdrawal/disqualification and cumulative thresholds, and require explanations grounded in the resolution rules. No second model pass was run.

**Details.** We sampled 100 without replacement from 3,599 eligible world markets: Jev status_quo_default probability below 0.2, a valid Haiku NO rather than unsure, and no prior reviewer placing the market on the default-outcome side of the current plots. There were 3,603 raw Jev/Haiku NO agreements in world; four reviewer overrides were excluded. This sample does not represent the disagreement or unsure groups.

Haiku comes from the completed manifold_haiku.jsonl run (37,676 valid market answers), not the separate reverse-order run. The existing parser reports nine invalid lines; invalid answers are never treated as NO. Sampling used Python random.Random(20261102).sample on sorted eligible IDs; the ten display IDs were sampled from those 100 with seed 20261103, before classification.

Luna was run as a GPT-6 Luna subagent with low reasoning and no inherited chat history. It received the saved prompt and full cleaned classifier inputs, without the manifest or previous labels. It was asked to distinguish clear days/weeks-or-longer mechanisms from ordinary common-event resolution, minutes/hours, and speculative timing correlations. It also classified default outcomes to distinguish prior labeling errors from genuine non-default asymmetry. The inputs omit later updates and do not verify historical resolution timestamps.

The raw result IDs and order match all 100 inputs. Luna’s results remain unchanged. My comments above cover the displayed examples; they are not a replacement classification of all 100.

[Prompt](../labeling/review/timing_luna/prompt.txt) · [100 market texts](../labeling/review/timing_luna/input.jsonl) · [Raw Luna answers](../labeling/review/timing_luna/results.jsonl) · [Sample and eligibility manifest](../labeling/review/timing_luna/manifest.json) · [Metrics](../labeling/review/timing_luna/metrics.csv)
