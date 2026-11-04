"""Calibration at fixed times before resolution, split by the second Haiku pass. Run in a tmux session.

python src/second_pass_before_resolution.py -> plots/second_pass/before_resolution.png, before_resolution_bins.csv, before_resolution_metrics.csv
The moment is resolution minus the horizon, so which moment a market gets depends on when its outcome arrived. Each dot is a plain mean of prices against a plain mean of outcomes.
"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from yes_bias import API, COLLECTED, HOURS, ROOT, boot_rate, summary
from plot_calibration import load

OUT, MIN_BIN, HORIZONS = ROOT / "plots/second_pass", 30, HOURS | {"1y": 8760}
SPLITS = {"default_side": [("NO", "#c2410c", "Nothing happening means NO"), ("YES", "#1d4ed8", "Nothing happening means YES"), ("NONE", "#047857", "No default side")],
          "early_side": [("YES_EARLY", "#c2410c", "Only YES can finish early"), ("NO_EARLY", "#1d4ed8", "Only NO can finish early"), ("NEITHER", "#047857", "Neither can finish early")]}
HOW = "Source: Manifold API; labels from a second Haiku pass that saw text only, no prices or outcomes. Resolved YES/NO world markets, price at resolution minus the horizon, 15+ bettors by then.\nA market already closed then counts at its last price. Each dot is one 10-point price bin: mean price against share resolved YES, each market once.\nBins under 30 markets dropped; the number beside each dot is its market count. Bars: 95%, resampling creators.\nYES markets often resolve early, so this moment depends on the outcome: a market's last day before an early YES isn't comparable to its last day before a deadline NO."


def frame():
    markets = {m["id"]: m for m in map(json.loads, open(API / "markets.jsonl"))}
    a = load()
    a = a[(a.anchor == "before_resolution") & (a.group == "world") & (a.bettors >= 15) & a.horizon.isin(HORIZONS)].copy()
    labels = pd.DataFrame([json.loads(json.loads(l)["result"]) for l in open(ROOT / "labeling/second_pass/full_results.jsonl")])
    a = a.merge(labels[["id", "stated_deadline", *SPLITS]], on="id")
    for col in ["createdTime", "closeTime", "resolutionTime"]:
        a[col] = a.id.map(lambda i: markets[i][col])
    t = a.resolutionTime - a.horizon.map(HORIZONS) * 3600e3
    a["open"] = t < a.closeTime
    said = pd.to_datetime(a.stated_deadline, errors="coerce")
    a["done"] = (said >= pd.to_datetime(a.createdTime, unit="ms").dt.normalize()) & (said < COLLECTED - pd.Timedelta(days=60))
    return a


def plot(bins, name, title, note, **kwargs):
    fig, axes = plt.subplots(2, 4, figsize=(17, 9.6), sharex=True, sharey=True)
    for row, (split, sides) in zip(axes, SPLITS.items()):
        for ax, h in zip(row, HORIZONS):
            ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
            ax.grid(color="#eeeeee", lw=.6)
            ax.set(xlim=(0, 100), ylim=(0, 100), title=f"{h} before resolution")
            ax.spines[["top", "right"]].set_visible(False)
            for (side, color, label), offset in zip(sides, [(-4, 6), (5, -10), (6, 1)]):
                b = bins[(bins.series == name) & (bins.split == split) & (bins.side == side) & (bins.horizon == h)].set_index("bin").reindex(range(10))  # a dropped bin breaks the line
                ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker="o", ms=5, lw=1.8, elinewidth=.8, label=label)
                for r in b.dropna(subset="n").itertuples():
                    ax.annotate(f"{int(r.n):,}", (r.price * 100, r.yes * 100), xytext=offset, textcoords="offset points", ha="right" if offset[0] < 0 else "left", fontsize=7, color="#444444")
        row[0].set_ylabel("Resolved YES (%)")
        row[0].legend(frameon=False, fontsize=9, loc="lower right")
    for ax in axes[1]:
        ax.set_xlabel("Price (%)")
    fig.suptitle(title, x=.01, ha="left", fontsize=14, **kwargs)
    fig.text(.01, .01, HOW + note, fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, .11, 1, .96))
    fig.savefig(OUT / f"{name}.png", dpi=140)
    plt.close(fig)


def main():
    a = frame()
    bins, metrics = [], []
    for name, g in [("before_resolution", a), ("before_resolution_open", a[a.open]), ("before_resolution_corrected", a[a.done])]:
        for split, sides in SPLITS.items():
            for side, _, _ in sides:
                for h in HORIZONS:
                    x = g[(g[split] == side) & (g.horizon == h)]
                    if len(x) >= 30:
                        metrics.append(dict(series=name, split=split, side=side, horizon=h, **summary(x), price_if_yes=x[x.y == 1].prob.mean(), price_if_no=x[x.y == 0].prob.mean()))
                    for b, y in x.groupby(pd.cut(x.prob, np.arange(0, 1.01, .1), include_lowest=True, labels=False)):
                        if len(y) >= MIN_BIN:
                            low, high = boot_rate(y) if 0 < y.y.mean() < 1 else (np.nan, np.nan)
                            bins.append(dict(series=name, split=split, side=side, horizon=h, bin=b, n=len(y), price=y.prob.mean(), yes=y.y.mean(), yes_low=low, yes_high=high))
    bins = pd.DataFrame(bins)
    bins.to_csv(OUT / "before_resolution_bins.csv", index=False, float_format="%.4f")
    pd.DataFrame(metrics).to_csv(OUT / "before_resolution_metrics.csv", index=False, float_format="%.4f")
    plot(bins, "before_resolution", "Before resolution, split by default side (top) and by which side can finish early (bottom)", "")


if __name__ == "__main__":
    main()
