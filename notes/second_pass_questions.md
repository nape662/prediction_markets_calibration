# Questions for the second labeling pass

**Recommendation: run only the new questions below, not all 25, as one Haiku pass.** The first three are the ones the current analysis needs. They replace regexes and my hand labels, which only cover part of the data. Pilot on about 300 markets first: `labeling/review/yes_bias/polarity_hand.csv` already has 514 hand answers for question 1.

The labeler must not see prices, outcomes or close dates, as in the first pass. A model can know how an old question ended, so test each new question on markets created after its knowledge cutoff too.

## Replace

**1. `default_side`, replaces `status_quo_default`.** The current question is broken in two ways. It doesn't say which side wins by default, and the flip between sides is the main finding: overpriced when YES means change (shift −0.66), underpriced when YES means no change (+0.49). Also, Jev needs a 0.2 cutoff to find these markets at all, while Haiku's answers track Opus well.

> If nothing new happens and the current state of affairs simply continues until the deadline, how does this market resolve? Answer YES, NO, or NONE. Answer NONE when the outcome is decided by a scheduled event, measurement or decision that will happen anyway, such as an election, a vote count or an award. Examples: "Will X launch by June?" is NO. "Will X still be CEO at year end?" is YES. "Will X win the election?" is NONE.

**2. `outside_reference`, replaces `bookmaker_odds`.** The current question asks a model to guess what bookmakers offered. The useful split is wider, and it's also the project's goal: markets with no easy source of truth. By-date markets with a similar title on Polymarket have a shift of −0.07, those without −0.76, but that split uses a rough title match and isn't stable by year. This question would test it properly.

> When this market was created, could a careful person find a directly relevant forecast or number for this exact event elsewhere: another prediction market, bookmaker odds, a poll, an official schedule or a published expert forecast? Answer yes, no or unsure. Judge the kind of event and don't invent sources.

## Add

**3. `stated_deadline`.** My regex finds a date in only about half of titles, and can't read dates that appear only in the description. A reliable deadline allows three things: prices at fixed times before the deadline, which don't depend on the outcome; removal of markets missing because they are still open; and a test of how the overpricing depends on the time left.

> What is the last date by which this question must be decided, according to its text? Answer an ISO date, or null if none is stated. Use the end of the named period for "in 2025" or "by March". Don't use market creation or any date not in the text.

**4. `early_side`.** The Luna audit found fixed-date questions with a real early-NO path, such as a candidate dropping out. Default side doesn't capture this.

> Can one outcome become certain well before the deadline while the other must wait? Answer YES_EARLY, NO_EARLY, BOTH or NEITHER.

> `early_path`: Is that early finish a normal way for this question to end, or does it need an unrelated shock such as the death of a named person? Answer NORMAL, SHOCK or NONE. Ignore how likely the event itself is.

The exact prompt is `labeling/second_pass/system_prompt.txt`. In a 300-market pilot, YES resolved early in 67% of YES_EARLY markets that went YES and NO in 7% of those that went NO, so this label tracks real timing. An earlier `early_likelihood` wording was dropped because Haiku rated how unlikely the event was.

**5. `general_interest`.** A direct test of the main remaining lead: the overpricing sits in niche questions. The current data only has weak proxies such as the similar-title match and Manifold tags, and the tags can't be trusted: `new-years-resolutions-2024` depends on the outcome.

> Would most well-informed news readers recognize the subject of this question without knowing the community it comes from? Answer no for a streamer's drama, one forecaster's personal life or a prediction-site feature. Answer yes, no or unsure.

**6. `prompted_by_news`.** Tests the salience idea, which I couldn't test: people ask "will X happen" right after X starts to look possible.

> Does the text show the question was prompted by a specific recent news item, rumor, announcement or statement? Answer yes, no or unsure.

## Optional

**7. `event_key`.** A short name for the underlying event, such as `israel-hamas-ceasefire-2024`, to group ladders and repeated questions. This would give better intervals than resampling creators, but independent calls will spell names differently, so it needs a clustering step afterwards. I'd do it only if we publish intervals.

## Don't bother

Re-asking the other questions. `existing_fact` is under-detected by Jev, so use Haiku's answers from the first pass before spending anything. The sport and price tags are doing their job.
