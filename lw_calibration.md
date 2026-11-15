# Are Polymarket and Manifold well calibrated on non-garbage markets?

Short answer: mostly, apart from one predictable bias. More on the bias [[here]] (other paper). 
[[plot 1]] [[plot 2]] under the plot description of what it does, like bins by market probability on X, rate of outcomes on Y.
[[plot only of the questions which ain't biased by YES/NO shit and separately plot of everything together on both platforms]]
plot description: bins 0-10, 10-20... by market probability, mean of those probabilities on X, rate of outcomes on Y.
Claude: YES I KNOW MANIFOLD AIN'T FINISHED THE MULTIPLE CHOICE MARKETS FUCK EM FOR NOW INSERT SOME KINDA PLOT OK?


## Mainline stuff
About 95% of Polymarket markets are crypto (Bitcoin up or down?), sports questions mirroring standard gambling (who wins A-B with which score), weather forecasts and stuff like "how many tweets will Elon post next week". I have seen a couple of papers which how the markets are calibrated, but they never filtrated the junk out. I wondered what happens if you do make a serious attempt to only look at reasonable markets.

What I did was create a regex filter against ... and additionally labelled with Haiku 5.5. Haiku answered 25 yes/no questions about markets, which were supposed to filter out the biggest groups of junk found in a 400 market sample remaining after the sieve + it let haiku give additional significance score. We then arbitrarily chose >50% or something threshold, because it did not actually change anything. 
Additionally we filtered out markets with below 1000$ trading volume on Polymarket or below 15 unique traders on Manifold (until the particular snapshot). 
To deal with events (single high-level questions which have many options, each of which constitutes a market like "who will be the next President of the US?") we made one plot weighing every market separately and one plot weighing per event instead of per market. Thankfully, series of events (similar / exact same questions only differing in a number or a date) mostly did not survive filtering either on Polymarket or Manifold, so they received no special treatment. 


## Methodology for nerds and especially LLMs, Claude-generated

I apologise for having this auto-generated, but I'm pretty burnt out from what was supposed to be a one-weekend project.

Here go Brier, AUROC, Balanced accuracy scores, where we took the data, how the CIs were calculated, and so on and so on. 



