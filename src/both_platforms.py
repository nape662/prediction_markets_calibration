"""Polymarket and Manifold on the same axes, for lw_calibration.md. Run in a tmux session (the Manifold loader takes a few minutes).

python src/both_platforms.py -> plots/all_markets.png, plots/no_default_side.png, plots/metrics.csv
Samples are the main ones of polymarket/calibration.py (closed_by_feb, $1,000 traded before the moment, one-winner events summing to at most 130%)
and manifold/second_pass_analysis.py (world markets, 15+ bettors by the moment, still open then), pooled with Manifold multiple-choice options
(manifold_mc/calibration.py: each option a YES/NO forecast, world markets, same gate). Price at a fixed time after trading starts / creation.
"""
import importlib.util, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "manifold"), str(ROOT / "polymarket")]
from stats import boot_rate, summary
import calibration as pm
import second_pass_analysis as mf
spec = importlib.util.spec_from_file_location("mc", ROOT / "manifold_mc/calibration.py")  # same module name as polymarket/calibration.py
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)

OUT, HORIZONS, MIN_BIN = ROOT / "plots", ["1d", "1w", "1m"], 30
PLATFORMS = [("Polymarket", "#1d4ed8", "markets"), ("Manifold", "#c2410c", "markets")]


def load():
    p = pm.frame()
    p = p[~p.junk & (p.cohort == "closed_by_feb") & (p.anchor == "after_start") & (p.vol >= pm.MIN_VOL) & p.neg_risk.notna() & ~(p.event_sum > pm.MAX_SUM)]
    m, _ = mf.labeled()
    m = m[(m.group == "world") & (m.bettors >= 15) & (m.anchor == "after_creation") & m.horizon.isin(HORIZONS) & (m.t < m.closeTime)]
    cols = ["id", "horizon", "prob", "y", "creator", "default_side"]
    c = mc.main_sample(mc.frame())
    c = c[c.group == "world"]
    m = pd.concat([m[cols].assign(w=1.0), c[cols + ["w"]]])
    return {"Polymarket": p[cols], "Manifold": m[cols]}, {"Polymarket": pm.weigh(p)[cols + ["w"]], "Manifold": m}


def metrics(g):
    p, y = g.prob.clip(.001, .999), g.y
    base = y.mean()
    return dict(**summary(g), brier=((p - y) ** 2).mean(), brier_base_rate=((base - y) ** 2).mean(),
                log_loss=-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean(), auroc=roc_auc_score(y, p), balanced_accuracy=balanced_accuracy_score(y, p > .5))


def bins(g):
    rows = []
    for b, x in g.groupby(np.minimum((g.prob * 10).astype(int), 9)):
        if len(x) >= MIN_BIN:
            lo, hi = boot_rate(x)
            rows.append(dict(bin=b, n=len(x), price=x.prob.mean(), yes=x.y.mean(), lo=lo, hi=hi))
    return pd.DataFrame(rows).set_index("bin").reindex(range(10))  # a dropped bin breaks the line


def figure(data, keep, name, title):
    fig, axes = plt.subplots(1, 3, figsize=(15, 6.2), sharey=True)
    for ax, h in zip(axes, HORIZONS):
        ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
        ax.grid(color="#eeeeee", lw=.6)
        ax.spines[["top", "right"]].set_visible(False)
        for (platform, color, unit), offset in zip(PLATFORMS, [(-5, 6), (6, -10)]):
            g = data[platform]
            g = g[(g.horizon == h) & keep(g)]
            b = bins(g)
            ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.lo) * 100, (b.hi - b.yes) * 100], color=color, marker="o", ms=5, lw=1.8, elinewidth=.8,
                        label=f"{platform}: {len(g):,} {unit}\nmean price {g.prob.mean():.1%}, resolved YES {g.y.mean():.1%}")
            for r in b.dropna(subset="n").itertuples():
                ax.annotate(f"{int(r.n):,}", (r.price * 100, r.yes * 100), xytext=offset, textcoords="offset points", ha="right" if offset[0] < 0 else "left", fontsize=7, color="#444444")
        ax.set(xlim=(0, 100), ylim=(0, 100), xlabel="Market price (%), mean within the bin", title=f"{h} after the market opens")
        ax.legend(frameon=False, fontsize=8, loc="lower right")
    axes[0].set_ylabel("Resolved YES (%)")
    fig.suptitle(title, x=.01, ha="left", fontsize=14)
    fig.text(.01, .01, "Resolved YES/NO markets. Junk removed by text rules and LLM labels: sports, asset prices, weather, scheduled statistics, who-says-what, existing facts, unsubstantive questions\n(Manifold also: coin flips, games about the market). Each market counts once per panel; a Manifold multiple-choice question is split into one YES/NO market per option.\n"
             "Polymarket: last hourly API price at or before the moment, markets closed before Feb 2, 2026, only moments with $1,000+ traded on-chain before them. "
             "Manifold: probability after the last bet, 15+ distinct bettors by the moment.\n"
             "Dots: markets grouped into 10-point price bins (0-10%, 10-20%, ...), bins under 30 markets dropped, number = markets in the bin. "
             "Bars: 95%, resampling Polymarket events or Manifold creators.", fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, .1, 1, .96))
    fig.savefig(OUT / name, dpi=140)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    data, weighted = load()
    groups = [("All markets", lambda g: g.prob > -1), ("No default side", lambda g: g.default_side == "NONE")]
    rows = [dict(platform=p, group=name, horizon=h, **metrics(d[(d.horizon == h) & keep(d)]))
            for p, d in data.items() for name, keep in groups for h in HORIZONS]
    rows += [dict(platform=f"{p}, each {unit} weighs 1", group=name, horizon=h, events=d.w.sum(), **summary(d))  # within a moment, an event's K markets, or a multiple-choice market's K options, weigh 1/K
             for (p, unit), w in zip([("Polymarket", "event"), ("Manifold", "market")], weighted.values()) for name, keep in groups for h in HORIZONS for d in [w[(w.horizon == h) & keep(w)]]]
    pd.DataFrame(rows).round(4).to_csv(OUT / "metrics.csv", index=False)
    figure(data, groups[0][1], "all_markets.png", "All filtered markets: both platforms sit near the diagonal, Manifold below it")
    figure(data, groups[1][1], "no_default_side.png", "Only markets where nothing happening doesn't decide the answer")


if __name__ == "__main__":
    main()
