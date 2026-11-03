"""Plots for notes/yes_bias_debug.md, from the tables of src/yes_bias.py analyze. python src/yes_bias_plots.py -> plots/yes_bias/*.png"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "plots/yes_bias"
m = pd.read_csv(OUT / "metrics.csv").set_index(["check", "horizon"], drop=False)
bins = pd.read_csv(OUT / "bins.csv")
ACCENT, BLUE, GRAY, GREEN = "#c2410c", "#1d4ed8", "#6b7280", "#047857"
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
HOW = "Source: Manifold API. Resolved YES/NO world markets, price at a fixed time after creation, 15+ bettors by then, each market once per panel, still unresolved then."


def curve(ax, series, h, color, label, min_n=10):
    b = bins[(bins.series == series) & (bins.horizon == h) & (bins.n >= min_n)]
    ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker="o", ms=4, lw=1.6, elinewidth=.8, label=label)


def diag(ax):
    ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
    ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="Price (%)")
    ax.grid(color="#eeeeee", lw=.6)


fig, axes = plt.subplots(1, 3, figsize=(13, 6), sharey=True)
for ax, h in zip(axes, ["1d", "1w", "1m"]):
    diag(ax)
    curve(ax, "nothing happening means NO", h, ACCENT, "Nothing happening means NO: YES needs a change")
    curve(ax, "YES means no change", h, BLUE, "YES means no change")
    curve(ax, "both labels no default, no title date", h, GREEN, "Decided on an event, no title date")
    ax.set_title(f"{h} after creation")
axes[0].set_ylabel("Resolved YES (%)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, frameon=False, fontsize=11, loc="upper left", bbox_to_anchor=(.01, .93), ncols=3)
fig.suptitle("Change is overpriced and continuation underpriced; questions decided on one event sit near the line", x=.01, ha="left", fontsize=14)
fig.text(.01, .01, HOW + "\n10-point bins, under 10 markets dropped. Bars: 95%, resampling creators.\nOrange: Haiku says one side wins by default, no negation words. Blue: hand labels from titles. Green: Jev and Haiku both say no default, no date in the title.", fontsize=9, color="#555555")
fig.tight_layout(rect=(0, .1, 1, .88))
fig.savefig(OUT / "resorted.png", dpi=140)
plt.close(fig)

rows = [("Current plot, all world markets", "world", "1w", GRAY),
        ("1,000+ mana by the snapshot", "artifact: 1000+ mana by the snapshot, so the fetch gate needs no future", "1w", GRAY),
        ("Drop closed but unresolved markets", "artifact: drop closed but unresolved", "1w", GRAY),
        ("Price before the last trade", "artifact: price before the last move", "1w", GRAY),
        ("Mean price over the last 24 hours", "artifact: mean price over the last 24h", "1w", GRAY),
        ("Traded in the last 24 hours", "artifact: traded in the last 24h, last price", "1w", GRAY),
        ("2,000+ mana by the snapshot", "artifact: 2000+ mana by the snapshot", "1w", GRAY),
        ("Created before 2025", "artifact: created before 2025", "1w", GRAY),
        ("Old label: other world", "old label: other world", "1w", GRAY),
        ("Nothing happening means NO", "nothing happening means NO", "1w", ACCENT),
        ("Decided on an event, no title date", "both labels no default, no title date", "1w", GREEN),
        ("YES means no change", "YES means no change, hand labels", "1w", BLUE)]
fig, ax = plt.subplots(figsize=(10, 6.4))
for i, (label, check, h, color) in enumerate(rows[::-1]):
    r = m.loc[(check, h)]
    ax.plot([r.low, r.high], [i, i], color=color, lw=2)
    ax.plot(r["shift"], i, "o", color=color, ms=7)
    ax.text(1.05, i, f"{r.gap * 100:+.1f} pts, n={int(r.n):,}", va="center", fontsize=10, color="#444444")
ax.axvline(0, color="#999999", lw=1)
ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
ax.set_xlim(-1, 1)
ax.set_xlabel("Log-odds shift that would calibrate the group (below 0: YES overpriced)")
fig.suptitle("Counting checks barely move the gap; what the question is does", x=.01, ha="left", fontsize=14)
fig.text(.01, .01, HOW + "\n1 week after creation. Bars: 95%, resampling creators; right column: mean price minus YES rate.", fontsize=8.5, color="#555555")
fig.tight_layout(rect=(0, .07, .86, 1))
fig.savefig(OUT / "what_moves_it.png", dpi=140)
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(14, 5.6), sharey=True)
for ax, series, name in zip(axes, ["nothing happening means NO", "title date", "title date passed"], ["WITHOUT correction: every resolved market", "Only markets with a date in the title", "WITH correction: that date passed 60+ days before fetch"]):
    diag(ax)
    curve(ax, series, "1w", ACCENT, name)
    ax.set_title(name, fontsize=11)
axes[0].set_ylabel("Resolved YES (%)")
fig.suptitle("CORRECTION: the right panel keeps only markets whose written deadline has passed", color="#c00000", fontweight="bold", fontsize=14, x=.01, ha="left")
fig.text(.01, .01, "Markets still open are missing from the data, which overstates YES among recent questions. Requiring a date also changes which questions are in the sample, so the middle panel separates the two effects.\nMarkets where nothing happening means NO, 1 week after creation. " + HOW, fontsize=8.5, color="#555555")
fig.tight_layout(rect=(0, .08, 1, .94))
fig.savefig(OUT / "censoring.png", dpi=140)
plt.close(fig)

rows = [("Manifold, no similar Polymarket title", "manifold: by date, no similar Polymarket title open then", ACCENT),
        ("Manifold, similar Polymarket title", "manifold: by date, similar Polymarket title open then", ACCENT),
        ("Polymarket, no similar Manifold title", "polymarket: by date, no similar Manifold title open then", BLUE),
        ("Polymarket, similar Manifold title", "polymarket: by date, similar Manifold title open then", BLUE),
        ("Same events, not copied: Manifold price", "pairs, by_date, not copied: Manifold price", ACCENT),
        ("Same events, not copied: Polymarket price", "pairs, by_date, not copied: Polymarket price", BLUE)]
fig, ax = plt.subplots(figsize=(14, 5.2))
for i, (label, check, color) in enumerate(rows[::-1]):
    r = m.loc[(check, "1w")]
    ax.plot([r.low, r.high], [i, i], color=color, lw=2)
    ax.plot(r["shift"], i, "o", color=color, ms=7)
    ax.text(1.2, i, f"{r.price * 100:.0f}% vs {r.yes * 100:.0f}% YES, n={int(r.n):,}", va="center", fontsize=10, color="#444444")
ax.axvline(0, color="#999999", lw=1)
ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
ax.set_xlim(-1.1, 1.1)
ax.set_xlabel("Log-odds shift that would calibrate the group (below 0: YES overpriced)")
fig.suptitle("Overpricing by date is on both platforms; it looks smaller where the other platform has a similar market", x=.01, ha="left", fontsize=14)
fig.text(.01, .01, "Source: Manifold API, Becker Polymarket data. Markets with a deadline in the title by one text rule, created 2023-25, 1 week after creation, 15+ bettors or takers and 1,000+ mana or $1,000+ by then.\nPolymarket: Becker on-chain trades, last block's mean price.  Similar title: TF-IDF cosine 0.42+, already open at the snapshot, no gate on its later outcome, not verified.\nSame events: verified by hand from titles and rules, priced at the same moment, Manifold copies of Polymarket removed. Bars: 95%, resampling creators or Polymarket event groups.", fontsize=8.5, color="#555555")
fig.tight_layout(rect=(0, .13, .82, .95))
fig.savefig(OUT / "platforms.png", dpi=140)
plt.close(fig)

d = pd.read_csv(OUT / "before_deadline.csv")
d = d[(d.side == "nothing happening means NO") & (d.dates == "clear")]
fig, ax = plt.subplots(figsize=(9, 5.4))
ax.plot(d.before, d.price * 100, "o-", color=ACCENT)
ax.plot(d.before, d.yes * 100, "o-", color=GRAY)
ax.text(len(d) - .9, d.price.iloc[-1] * 100, "Mean price", color=ACCENT, va="center")
ax.text(len(d) - .9, d.yes.iloc[-1] * 100, "Resolved YES", color=GRAY, va="center")
ax.set_xlim(-.3, len(d) + .4)
ax.set_ylim(0, None)
ax.set(xlabel="Time before the deadline written in the title", ylabel="%")
ax.grid(axis="y", color="#eeeeee")
ax.set_title("These markets stay overpriced close to the deadline", loc="left", fontsize=14)
fig.text(.01, .01, "Source: Manifold API. Markets where nothing happening means NO, with an unambiguous date in the title that passed 60+ days before fetch, still open at that moment, 15+ people having moved the price by then.\nEach point is a different set of markets: those whose event already happened are gone, so both lines fall.\nThis moment doesn't depend on the outcome, unlike time before resolution.", fontsize=8.5, color="#555555", wrap=True)
fig.tight_layout(rect=(0, .13, 1, 1))
fig.savefig(OUT / "before_deadline.png", dpi=140)
