"""Manifold numbers for lw_bias.md: binary world markets pooled with multiple-choice world options, each option one YES/NO forecast. Run in a tmux session.

python src/pooled_bias.py -> manifold/plots/pooled/metrics.csv, bins.csv (same layout as manifold/plots/second_pass/; src/bias_plots.py draws them)
Binary: the manifold/second_pass_analysis.py sample (15+ bettors by the moment, still open). Options: the manifold_mc/calibration.py main sample
(same gate, option unresolved), with Haiku's per-option default side and stated deadline. "Deadline passed": the stated deadline is 60+ days
before the fetch (binary 2026-10-30, multiple-choice 2026-11-14).
"""
import importlib.util, sys
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "manifold")]
from stats import boot_rate, logit, summary
import second_pass_analysis as sp
spec = importlib.util.spec_from_file_location("mc", ROOT / "manifold_mc/calibration.py")  # same module name as polymarket/calibration.py
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)

OUT = ROOT / "manifold/plots/pooled"
COLS = ["id", "horizon", "prob", "y", "creator", "default_side", "said", "done", "year", "resolutionTime", "one_winner"]
MC_COLLECTED = pd.Timestamp("2026-11-14")


def load():
    a, _ = sp.labeled()
    b = a[(a.group == "world") & (a.bettors >= 15) & (a.anchor == "after_creation") & a.horizon.isin(sp.HOURS) & (a.t < a.closeTime)].assign(one_winner=False)
    c = mc.main_sample(mc.frame())
    c = c[c.group == "world"].copy()
    created = pd.to_datetime(c.createdTime, unit="ms")
    c["said"] = pd.to_datetime(c.stated_deadline, errors="coerce")
    c.loc[c.said < created.dt.normalize(), "said"] = pd.NaT  # a date before the market existed, as for binary markets
    c["done"] = c.said < MC_COLLECTED - pd.Timedelta(days=60)
    c["year"] = created.dt.year
    print(f"binary {b[b.horizon == '1w'].shape[0]:,}, options {c[c.horizon == '1w'].shape[0]:,} at 1w", flush=True)
    return pd.concat([b[COLS], c[COLS]], ignore_index=True)


def main():
    OUT.mkdir(exist_ok=True)
    w = load()
    metrics, bins = [], []
    def add(check, g, h):
        if len(g) >= sp.MIN_GROUP:
            metrics.append(dict(check=check, by="creator", horizon=h, **summary(g)))
    for h in sp.HOURS:
        x = w[w.horizon == h]
        for side, g in x.groupby("default_side"):  # plots: every market
            for b, y in g.groupby(pd.cut(g.prob, np.arange(0, 1.01, .1), include_lowest=True, labels=False)):
                if len(y) >= 10:
                    low, high = boot_rate(y) if 0 < y.y.mean() < 1 else (np.nan, np.nan)
                    bins.append(dict(series=f"default {side}", horizon=h, bin=b, n=len(y), price=y.prob.mean(), yes=y.y.mean(), yes_low=low, yes_high=high))
        x = x[~x.one_winner]  # shifts: without one-winner markets, whose prices sum to ~1 with one winner, pinning their shift near 0
        add("world", x, h)
        for side, g in x.groupby("default_side"):
            add(f"default {side}", g, h)
            add(f"default {side}: deadline passed", g[g.done], h)
            fit = sm.GLM(g.y.to_numpy(), sm.add_constant(logit(g.prob.to_numpy())), family=sm.families.Binomial()).fit(cov_type="cluster", cov_kwds=dict(groups=pd.factorize(g.creator)[0]))
            metrics.append(dict(check=f"line, default {side}", by="creator", horizon=h, n=len(g), alpha=fit.params[0], beta=fit.params[1], beta_low=fit.conf_int()[1, 0], beta_high=fit.conf_int()[1, 1]))
            if h == "1w":
                for year, y in g.groupby("year"):
                    add(f"default {side}, created {year}", y, h)
                    add(f"default {side}, created {year}: deadline passed", y[y.done], h)
        sp.recalibrate(metrics, x, h)
        sp.recalibrate(metrics, x[x.done], h, ", deadline passed")
        print("done", h, flush=True)
    pd.DataFrame(metrics).to_csv(OUT / "metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(bins).to_csv(OUT / "bins.csv", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
