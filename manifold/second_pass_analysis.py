"""Manifold calibration re-sorted by the second Haiku pass (manifold/labeling/second_pass/full_results.jsonl). Run in a tmux session.

python manifold/second_pass_analysis.py -> manifold/plots/second_pass/metrics.csv, bins.csv, before_deadline.csv
Same sample and snapshots as manifold/yes_bias.py: price at a fixed time after creation, 15+ bettors by then, still open then. Groups under 30 markets are skipped.
Shift is the log-odds added to every price that makes the group's mean price equal its YES rate. "Done" keeps markets whose stated deadline passed 60+ days before the fetch, which removes most of the skew from markets still open.
"""
import json
import numpy as np
import pandas as pd
import statsmodels.api as sm
from yes_bias import COLLECTED, DATA, HOURS, ROOT, data, hash_half
from stats import boot_rate, logit, summary, wshift

OUT = ROOT / "manifold/plots/second_pass"
MIN_GROUP, DRAWS, CUT = 30, 2000, pd.Timestamp("2024-01-01")
QUESTIONS = ["default_side", "outside_reference", "early_side", "early_path", "general_interest", "prompted_by_news"]


def labeled():
    """Every snapshot of a labeled market. The returned counts say what was dropped."""
    a = data(min_bettors=0)
    labels = pd.DataFrame([json.loads(json.loads(l)["result"]) for l in open(ROOT / "manifold/labeling/second_pass/full_results.jsonl")])
    assert labels.id.is_unique
    unlabeled = a.loc[~a.id.isin(labels.id), "id"].nunique()
    a = a.merge(labels[["id", "stated_deadline", *QUESTIONS]], on="id")
    a["said"] = pd.to_datetime(a.stated_deadline, errors="coerce")
    created = pd.to_datetime(a.createdTime, unit="ms").dt.normalize()
    unusable = a.stated_deadline.notna() & (a.said.isna() | (a.said < created))  # an impossible date, or one before the market existed
    counts = dict(unlabeled=unlabeled, deadline_unusable=a.loc[unusable, "id"].nunique(), deadline_stated=a.loc[a.stated_deadline.notna(), "id"].nunique())
    a.loc[unusable, "said"] = pd.NaT
    a["done"] = a.said < COLLECTED - pd.Timedelta(days=60)
    return a, counts


def before_deadline(a):
    """Prices at fixed times before the stated deadline, which doesn't depend on the outcome. 15 people must have moved the price by then, and the market must still be open."""
    u = a[(a.group == "world") & a.done].drop_duplicates("id")
    moves = pd.read_parquet(DATA / "moves.parquet", columns=["id", "t", "user", "pa"])
    g = dict(tuple(moves[moves.id.isin(u.id)].sort_values("t").groupby("id")))
    rows = []
    for r in u.itertuples():
        x, end = g.get(r.id), (r.said + pd.Timedelta(days=1)).timestamp() * 1e3  # the deadline day counts in full
        if x is None:
            continue
        seen = pd.Series(pd.factorize(x.user)[0]).cummax().to_numpy() + 1
        for name, days in [("1y", 365), ("6m", 182), ("3m", 91), ("1m", 30), ("2w", 14), ("1w", 7), ("3d", 3), ("1d", 1)]:
            t = end - days * 86400e3
            i = np.searchsorted(x.t.values, t, side="right") - 1
            if r.createdTime < t < min(r.resolutionTime, r.closeTime) and i >= 0 and seen[i] >= 15:
                rows.append(dict(before=name, prob=x.pa.values[i], y=r.y, creator=r.creator, default_side=r.default_side, early_side=r.early_side))
    b = pd.DataFrame(rows)
    return pd.DataFrame([dict(side=f"{col}={side}", before=k, **summary(x)) for col in ["default_side", "early_side"] for side, s in b.groupby(col) for k, x in s.groupby("before") if len(x) >= MIN_GROUP])


def scores(p, y):
    p = np.clip(p, .001, .999)
    return (p - y) ** 2, -(y * np.log(p) + (1 - y) * np.log(1 - p))


def recalibrate(metrics, x, h, tag=""):
    """Fit shifts on what was known at the start of 2024, test on markets created from then on: is the fix stable enough to apply to later markets?"""
    train, test = x[x.resolutionTime < CUT.timestamp() * 1e3], x[x.year >= CUT.year]
    if tag:
        train = train[train.said < CUT - pd.Timedelta(days=60)]
    shifted = lambda p, s: 1 / (1 + np.exp(-(logit(p) + s)))
    fit = lambda g: wshift(logit(g.prob.to_numpy()), g.y.to_numpy(), np.ones(len(g)))
    sides = {s: fit(g) for s, g in train.groupby("default_side")}
    p = {"raw": test.prob.to_numpy(), "one shift": shifted(test.prob.to_numpy(), fit(train)), "one shift per default side": shifted(test.prob.to_numpy(), test.default_side.map(sides).to_numpy())}
    y, c = test.y.to_numpy(), pd.factorize(test.creator)[0]
    rng = np.random.default_rng(0)
    w = np.array([np.bincount(rng.integers(0, c.max() + 1, c.max() + 1), minlength=c.max() + 1)[c] for _ in range(DRAWS)])
    for name, q in p.items():
        brier, log = scores(q, y)
        change = brier - scores(p["raw"], y)[0]
        draws = w @ change / w.sum(axis=1)
        metrics.append(dict(check=f"recalibrated from 2024{tag}: {name}", by="creator", horizon=h, n=len(test), price=q.mean(), yes=y.mean(), gap=q.mean() - y.mean(), brier=brier.mean(), log_loss=log.mean(), brier_change=change.mean(), low=np.percentile(draws, 2.5), high=np.percentile(draws, 97.5)))
    draws = w @ (scores(p["one shift per default side"], y)[0] - scores(p["one shift"], y)[0]) / w.sum(axis=1)
    metrics.append(dict(check=f"recalibrated from 2024{tag}: Brier, one shift per default side minus one shift", by="creator", horizon=h, n=len(test), brier_change=draws.mean(), low=np.percentile(draws, 2.5), high=np.percentile(draws, 97.5)))
    for s, v in sides.items():
        metrics.append(dict(check=f"recalibrated from 2024{tag}: shift fitted on markets resolved before 2024, default {s}", by="", horizon=h, n=int((train.default_side == s).sum()), shift=v))
    return test.assign(prob=p["one shift per default side"])


def analyze():
    OUT.mkdir(exist_ok=True)
    a, counts = labeled()
    print(counts, flush=True)
    metrics = [dict(check=f"count: {k}", by="", n=int(v)) for k, v in counts.items()]
    def add(check, g, by="creator", horizon="1w"):
        if len(g) >= MIN_GROUP:
            metrics.append(dict(check=check, by=by, horizon=horizon, **summary(g, by)))
    def line(check, g, horizon="1w"):
        """Two-parameter recalibration: logit(YES) = alpha + beta * logit(price). beta above 1 means prices are squeezed toward 50%."""
        fit = sm.GLM(g.y.to_numpy(), sm.add_constant(logit(g.prob.to_numpy())), family=sm.families.Binomial()).fit(cov_type="cluster", cov_kwds=dict(groups=pd.factorize(g.creator)[0]))
        metrics.append(dict(check=check, by="creator", horizon=horizon, n=len(g), alpha=fit.params[0], alpha_low=fit.conf_int()[0, 0], alpha_high=fit.conf_int()[0, 1], beta=fit.params[1], beta_low=fit.conf_int()[1, 0], beta_high=fit.conf_int()[1, 1]))

    s = a[(a.bettors >= 15) & (a.anchor == "after_creation") & a.horizon.isin(HOURS) & (a.t < a.closeTime)]
    w = s[s.group == "world"]
    recalibrated = {}
    for h in HOURS:
        x = w[w.horizon == h]
        add("world", x, horizon=h)
        add("world: deadline passed", x[x.done], horizon=h)
        total = (x.prob - x.y).sum()
        for side, g in x.groupby("default_side"):
            add(f"default {side}", g, horizon=h)
            add(f"default {side}: no deadline stated", g[g.said.isna()], horizon=h)
            add(f"default {side}: deadline stated", g[g.said.notna()], horizon=h)
            add(f"default {side}: deadline passed", g[g.done], horizon=h)
            line(f"line, default {side}", g, h)
            metrics.append(dict(check=f"share of the total gap: default {side}", by="", horizon=h, n=len(g), gap=(g.prob - g.y).sum() / total))
        recalibrated[h] = recalibrate(metrics, x, h), recalibrate(metrics, x[x.done], h, ", deadline passed")
        print("done", h, flush=True)

    x = w[w.horizon == "1w"]
    for (d, e), g in x.groupby(["default_side", "early_side"]):
        add(f"default {d}, early {e}", g)
        add(f"default {d}, early {e}: deadline passed", g[g.done])
    for (e, p), g in x.groupby(["early_side", "early_path"]):
        add(f"early {e}, path {p}", g)
    for q in QUESTIONS:
        for v, g in x.groupby(q):
            add(f"{q} {v}", g)
    ne = x[x.default_side == "NO"]
    for q in ["outside_reference", "general_interest", "prompted_by_news", "early_side", "early_path"]:
        for v, g in ne.groupby(q):
            add(f"default NO, {q} {v}", g)
            add(f"default NO, {q} {v}: deadline passed", g[g.done])
    for side, g in x.groupby("default_side"):
        for year, y in g.groupby("year"):
            add(f"default {side}, created {year}", y)
            add(f"default {side}, created {year}: deadline passed", y[y.done])
        for half in [0, 1]:
            add(f"holdout creators {half}: default {side}", g[g.creator.map(hash_half) == half])
        dated = g[g.said.notna()]
        add(f"default {side}, resampling deadline months", dated.assign(month=dated.said.dt.to_period("M").astype(str)), by="month")
    left = ne[ne.said.notna()].assign(left=lambda d: (d.said - pd.to_datetime(d.t, unit="ms")).dt.days)
    for low, high in [(0, 14), (14, 30), (30, 90), (90, 365), (365, 1e5)]:
        g = left[left.left.between(low + 1, high)]
        add(f"default NO, {low} to {high} days left", g)
        add(f"default NO, deadline passed, {low} to {high} days left", g[g.done])
        for year, y in g[g.done].groupby("year"):
            add(f"default NO, deadline passed, created {year}, {low} to {high} days left", y)
    for group, g in s[s.horizon == "1w"].groupby("group"):
        for side, y in g.groupby("default_side"):
            if group != "world":
                add(f"other group {group}: default {side}", y)
    print("splits done", flush=True)

    # Do the new labels agree with the older ways of sorting, and does the result depend on the disagreements?
    add("agree: regex and Haiku v1 say change, default NO", x[x.event & (x.default_side == "NO")])
    add("disagree: regex and Haiku v1 say change, not default NO", x[x.event & (x.default_side != "NO")])
    add("disagree: default NO, regex and Haiku v1 don't say change", x[~x.event & (x.default_side == "NO")])
    add("agree: hand YES default, default YES", x[x.yes_default & (x.default_side == "YES")])
    add("disagree: hand YES default, not default YES", x[x.yes_default & (x.default_side != "YES")])
    add("disagree: default YES, not hand YES default, hand labeled or not", x[~x.yes_default & (x.default_side == "YES")])
    both = x[x.clear & x.said.notna() & x.deadline.notna()]
    metrics.append(dict(check="stated deadline within a day of an unambiguous title date", by="", n=len(both), gap=((both.said - both.deadline).dt.days.abs() <= 1).mean()))
    metrics.append(dict(check="no stated deadline, though the title has an unambiguous date", by="", n=int((x.clear & x.said.isna()).sum())))
    metrics.append(dict(check="stated deadline, no date in the title", by="", n=int((x.said.notna() & x.deadline.isna()).sum())))

    edges, bins = np.arange(0, 1.01, .1), []
    series = {"world": lambda x: x.prob > -1, "world, deadline passed": lambda x: x.done}
    series |= {f"default {d}": (lambda x, d=d: x.default_side == d) for d in ["NO", "YES", "NONE"]}
    series |= {f"default {d}, deadline passed": (lambda x, d=d: (x.default_side == d) & x.done) for d in ["NO", "YES", "NONE"]}
    series |= {f"early {e}": (lambda x, e=e: x.early_side == e) for e in ["YES_EARLY", "NO_EARLY", "BOTH", "NEITHER"]}
    for h in HOURS:
        x = w[w.horizon == h]
        test = {"from 2024, raw": x[x.year >= 2024], "from 2024, one shift per default side": recalibrated[h][0], "from 2024, deadline passed, raw": x[(x.year >= 2024) & x.done], "from 2024, deadline passed, one shift per default side": recalibrated[h][1]}
        for name, g in [(n, x[f(x)]) for n, f in series.items()] + list(test.items()):
            for b, y in g.groupby(pd.cut(g.prob, edges, include_lowest=True, labels=False)):
                if len(y) >= 10:
                    low, high = boot_rate(y) if 0 < y.y.mean() < 1 else (np.nan, np.nan)  # resampling can't show what it never saw
                    bins.append(dict(series=name, horizon=h, bin=b, n=len(y), price=y.prob.mean(), yes=y.y.mean(), yes_low=low, yes_high=high))
    pd.DataFrame(metrics).to_csv(OUT / "metrics.csv", index=False, float_format="%.4f")
    pd.DataFrame(bins).to_csv(OUT / "bins.csv", index=False, float_format="%.4f")
    print("metrics and bins written", flush=True)
    before_deadline(a).to_csv(OUT / "before_deadline.csv", index=False, float_format="%.4f")
    print("finished", flush=True)


if __name__ == "__main__":
    analyze()
