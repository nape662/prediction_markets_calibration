"""Plots for lw_bias.md, from tables already written by polymarket/calibration.py and manifold/second_pass_analysis.py. No captions: the post explains them.

python src/bias_plots.py -> plots/by_side_manifold.png, plots/by_side_polymarket.png, plots/by_year.png
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "plots"
SIDES = [("NO", "#c2410c", "Nothing happening means NO"), ("YES", "#1d4ed8", "Nothing happening means YES"), ("NONE", "#047857", "No default side")]
HORIZONS = {"1d": "1 day", "1w": "1 week", "1m": "1 month"}
plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})


def by_side(bins, name, title, opened):
    """bins: one row per side, horizon and 10-point bin, with columns side, horizon, n, price, yes, yes_low, yes_high."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.4), sharey=True)
    for ax, (h, words) in zip(axes, HORIZONS.items()):
        ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
        ax.grid(color="#eeeeee", lw=.6)
        for (side, color, label), offset in zip(SIDES, [(-4, 6), (5, -10), (6, 1)]):
            b = bins[(bins.side == side) & (bins.horizon == h) & (bins.n >= 30)].set_index("bin").reindex(range(10))  # a dropped bin breaks the line
            ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker="o", ms=5, lw=1.8, elinewidth=.8, label=label)
            for r in b.dropna(subset="n").itertuples():
                ax.annotate(f"{int(r.n):,}", (r.price * 100, r.yes * 100), xytext=offset, textcoords="offset points", ha="right" if offset[0] < 0 else "left", fontsize=7, color="#444444")
        ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="Market price (%)", title=f"{words} after {opened}")
    axes[0].set_ylabel("Resolved YES (%)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper left", bbox_to_anchor=(.01, .91), ncols=3)
    fig.suptitle(title, x=.01, ha="left", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .86))
    fig.savefig(OUT / name, dpi=140)
    plt.close(fig)


def by_year(m):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), sharey=True)
    for ax, tag, name in zip(axes, ["", ": deadline passed"], ["All resolved markets", "Only markets whose deadline passed 60+ days before the fetch"]):
        for (side, color, label), dx in zip(SIDES, [-.15, 0, .15]):
            r = m[m.check.str.fullmatch(rf"default {side}, created \d+{tag}") & (m.n >= 30)]
            year = r.check.str.extract(r"created (\d+)")[0].astype(int)
            ax.errorbar(year + dx, r["shift"], yerr=[r["shift"] - r.low, r.high - r["shift"]], color=color, marker="o", ms=6, lw=0, elinewidth=1.2, label=label)
            for y, s, n in zip(year, r["shift"], r.n):
                ax.annotate(f"{int(n):,}", (y + dx, s), xytext=(4, 0), textcoords="offset points", va="center", fontsize=7, color="#444444")
        ax.axhline(0, color="#999999", lw=1)
        ax.set(xticks=range(2022, 2027), xlim=(2021.6, 2026.5), xlabel="Year the market was created")
        ax.grid(axis="y", color="#eeeeee", lw=.6)
        ax.set_title(name, fontsize=11)
    axes[0].set_ylabel("Log-odds shift (below 0: YES overpriced)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, loc="upper left", bbox_to_anchor=(.01, .91), ncols=3)
    fig.suptitle("Manifold: where nothing happening means NO, YES is overpriced in every creation year", x=.01, ha="left", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .86))
    fig.savefig(OUT / "by_year.png", dpi=140)
    plt.close(fig)


OUT.mkdir(exist_ok=True)
mb = pd.read_csv(ROOT / "manifold/plots/second_pass/bins.csv")
mb = mb[mb.series.isin([f"default {s}" for s, _, _ in SIDES])].assign(side=lambda d: d.series.str.removeprefix("default "))
by_side(mb, "by_side_manifold.png", "Manifold: YES is overpriced where nothing happening means NO, and underpriced where it means YES", "creation")
pb = pd.read_csv(ROOT / "polymarket/plots/bins.csv")
pb = pb[(pb.cohort == "closed_by_feb") & (pb.split == "default_side") & (pb.anchor == "after_start")]
pb = pb.assign(side=pb.group.map({label: side for side, _, label in SIDES}))
by_side(pb, "by_side_polymarket.png", "Polymarket: the same direction, about half as large", "trading starts")
by_year(pd.read_csv(ROOT / "manifold/plots/second_pass/metrics.csv"))
