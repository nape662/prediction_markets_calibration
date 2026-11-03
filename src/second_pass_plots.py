"""Plots for notes/second_pass_results.md, from the tables of src/second_pass_analysis.py. python src/second_pass_plots.py -> plots/second_pass/*.png"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

OUT = Path(__file__).resolve().parents[1] / "plots/second_pass"
m = pd.read_csv(OUT / "metrics.csv").set_index(["check", "horizon"], drop=False)
bins = pd.read_csv(OUT / "bins.csv")
ACCENT, BLUE, GRAY, GREEN = "#c2410c", "#1d4ed8", "#6b7280", "#047857"
SIDES = [("NO", ACCENT, "Nothing happening means NO"), ("YES", BLUE, "Nothing happening means YES"), ("NONE", GREEN, "No default side")]
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
HOW = "Source: Manifold API; sides from a second Haiku pass that saw text only, no prices or outcomes. \nResolved YES/NO world markets, price at a fixed time after creation, 15+ bettors by then, still open then. 10-point price bins, under 10 markets dropped. Bars: 95%, resampling creators."


def curve(ax, series, h, color, label, marker="o"):
    b = bins[(bins.series == series) & (bins.horizon == h)]
    ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker=marker, ms=5, lw=1.8, elinewidth=.8, label=label)


def diag(ax):
    ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
    ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="Price (%)")
    ax.grid(color="#eeeeee", lw=.6)


def by_side(suffix, title, note, name, **kwargs):
    fig, axes = plt.subplots(1, 3, figsize=(13, 6), sharey=True)
    for ax, h in zip(axes, ["1d", "1w", "1m"]):
        diag(ax)
        for side, color, label in SIDES:
            curve(ax, f"default {side}{suffix}", h, color, label)
        ax.set_title(f"{h} after creation")
    axes[0].set_ylabel("Resolved YES (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper left", bbox_to_anchor=(.01, .93), ncols=3)
    fig.suptitle(title, x=.01, ha="left", fontsize=14, **kwargs)
    fig.text(.01, .01, HOW + note, fontsize=9, color="#555555")
    fig.tight_layout(rect=(0, .1, 1, .88))
    fig.savefig(OUT / name, dpi=140)
    plt.close(fig)


by_side("", "Sorted by what happens if nothing changes, the error flips sign, and most markets are on the overpriced side", "", "by_side.png")
by_side(", deadline passed", "CORRECTION: only markets whose stated deadline passed 60+ days before the fetch", "\nThis removes the skew from markets still open, and also every market with no stated deadline, which changes the mix.", "by_side_corrected.png", color="#c00000", fontweight="bold")

fig, axes = plt.subplots(1, 2, figsize=(11, 6.2), sharey=True)
for ax, tag, name, color in zip(axes, ["", ", deadline passed"], ["WITHOUT correction: every resolved market", "WITH correction: stated deadline passed 60+ days before fetch"], ["#333333", "#c00000"]):
    diag(ax)
    curve(ax, f"from 2024{tag}, raw", "1w", GRAY, "Market price", "s")
    curve(ax, f"from 2024{tag}, one shift per default side", "1w", ACCENT, "After the fix fitted on markets resolved before 2024")
    ax.set_title(name, fontsize=11, color=color)
axes[0].set_ylabel("Resolved YES (%)")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, frameon=False, loc="upper left", bbox_to_anchor=(.01, .93), ncols=2)
fig.suptitle("CORRECTED PRICES: a fix fitted on old markets, tested on markets from 2024 on", x=.01, ha="left", fontsize=14, color="#c00000", fontweight="bold")
fig.text(.01, .01, "One log-odds shift per default side is fitted on markets resolved before 2024, then applied to markets created from 2024 on, 1 week after creation.\nIn the right panel the fit and the test use only markets whose stated deadline had passed 60+ days before the start of 2024 and the fetch, respectively.\n" + HOW, fontsize=8, color="#555555")
fig.tight_layout(rect=(0, .16, 1, .88))
fig.savefig(OUT / "recalibrated.png", dpi=140)
plt.close(fig)

rows = [("Outside reference: no", "default NO, outside_reference no"), ("Outside reference: yes", "default NO, outside_reference yes"),
        ("General interest: no", "default NO, general_interest no"), ("General interest: yes", "default NO, general_interest yes"),
        ("Prompted by news: yes", "default NO, prompted_by_news yes"), ("Prompted by news: no", "default NO, prompted_by_news no"),
        ("Only YES can finish early", "default NO, early_side YES_EARLY"), ("Neither can finish early", "default NO, early_side NEITHER"), ("Both can finish early", "default NO, early_side BOTH"), ("Only NO can finish early", "default NO, early_side NO_EARLY"),
        ("Under 2 weeks to deadline", "default NO, 0 to 14 days left"), ("90 to 365 days to deadline", "default NO, 90 to 365 days left"), ("Over a year to deadline", "default NO, 365 to 100000.0 days left")]
fig, ax = plt.subplots(figsize=(10, 7.5))
for i, (label, check) in enumerate(rows[::-1]):
    for suffix, color, offset, marker in [("", GRAY, .16, "s"), (": deadline passed", ACCENT, -.16, "o")]:
        name = check if not suffix else check + suffix if "days left" not in check else check.replace("default NO, ", "default NO, deadline passed, ")
        r = m.loc[(name, "1w")]
        ax.plot([r.low, r.high], [i + offset] * 2, color=color, lw=2)
        ax.plot(r["shift"], i + offset, marker, color=color, ms=7)
ax.plot([], [], "s-", color=GRAY, label="WITHOUT correction: every resolved market")
ax.plot([], [], "o-", color=ACCENT, label="WITH correction: stated deadline passed 60+ days before fetch")
ax.axvline(0, color="#999999", lw=1)
ax.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]])
ax.set_xlim(-1.4, .4)
ax.grid(axis="x", color="#eeeeee", lw=.6)
ax.set_xlabel("Log-odds shift that would calibrate the group (below 0: YES overpriced)")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(.35, 1.09), ncols=1)
fig.suptitle("No split with enough markets removes the overpricing where nothing happening means NO", x=.01, ha="left", fontsize=13)
fig.text(.01, .01, "Source: Manifold API, Haiku labels from text only. Markets where nothing happening means NO, 1 week after creation, 15+ bettors by then, still open then. Bars: 95%, resampling creators.", fontsize=8.5, color="#555555", wrap=True)
fig.tight_layout(rect=(0, .05, 1, .95))
fig.savefig(OUT / "within_no.png", dpi=140)
