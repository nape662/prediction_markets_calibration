"""Polymarket calibration split by the Haiku labels, like the Manifold plots in notes/second_pass_results.md.

python polymarket/calibration.py -> polymarket/plots/*.png, metrics.csv, bins.csv
Inputs: snapshots.jsonl and meta.csv (polymarket/prices.py), results.jsonl (16-question Haiku pass), outside_results.jsonl (polymarket/outside.py), cohorts.csv.
Main sample: the closed_by_feb cohort. Each market counts once per moment. Intervals resample events (event_title), because markets of one event share an outcome.
Filtered (main) plots keep a moment only if $1,000 had traded by then (volume.csv, Becker's trades, so open_in_feb mostly drops out) and,
in a one-winner (negRisk) event, the event's prices at that moment sum to at most 130%. Unfiltered plots go to polymarket/plots/unfiltered.
by_side_weighted.png: the by_side plot with each event weighted to 1 (weigh()).
"""
import json, re, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from stats import boot_rate, summary

OUT = HERE / "plots"
HORIZONS, MIN_BIN, MIN_VOL, MAX_SUM = ["1d", "1w", "1m"], 30, 1000, 1.3
# Market kinds by text rules on question + event title, tuned on 400 seen markets. On 200 fresh ones: chart 24/25, tsa 2/2, ai 1/1, no false alarms;
# the one chart miss (a song title with "Say") led to the quoted-phrase "say" guard, so that fix is untested on fresh markets.
CHART = (r"netflix (movie|show|series)|top (global |us )?netflix|most streamed|top spotify|song on (us |global )?spotify|spotify (charts|streams|artist|album|song)"
         r"|billboard|hot 100|rotten tomatoes|tomatometer|metacritic|metascore|box office|opening weekend|(highest|top)[- ]grossing|\bgross(es)?\b|\bviews\b"
         r"|\bsubscribers\b|\bviewers\b|most searched|year in search|#\d+ searched|album sales|first[- ]week sales|straight weeks|play store|app store on"
         r"|#\d+ (free |paid |grossing |finance )?app\b|top \d+ app|most popular app|\bmelon\b|top \d+ game on steam")
NOT_CHART = r"domestic product|\b(say|said)\s+[\"“]|earnings|\bstocks?\b|\bshares?\b|market cap|award|golden globe|oscar|grammy|\bremoved\b|acquire"
KINDS = [("tsa", r"\btsa\b", None), ("ai_leaderboard", r"(top|best|#\d+|number one) ai model|lmarena|chatbot arena|text arena|ai model (rank|leaderboard)", None),
         ("chart", CHART, NOT_CHART)]
ANCHORS = {"after_start": "after trading starts", "before_close": "before closing"}


def frame():
    meta = pd.read_csv(HERE / "meta.csv", dtype={"id": str, "token": str})
    meta["short"] = meta.close - meta.start < 7 * 86400
    events = pd.read_parquet(HERE.parent / "data/labeling/polymarket_markets.parquet", columns=["id", "event_id", "neg_risk"]).astype({"id": str})
    vol = pd.read_csv(HERE / "volume.csv", dtype={"id": str})
    cohort = pd.read_csv(HERE / "cohorts.csv", dtype={"id": str})
    labels = pd.DataFrame([json.loads(json.loads(l)["result"]) for l in open(HERE / "results.jsonl")])
    outside = {i: s for l in open(HERE / "outside_results.jsonl") for i, s in json.loads(l)["answers"].items()}
    event = {m["id"]: m["event_title"] or m["question"] for m in map(json.loads, open(HERE / "input.jsonl"))}
    rows = []
    for s in map(json.loads, open(HERE / "snapshots.jsonl")):
        for k, v in s.items():
            if k != "id" and v[1] is not None:
                anchor, h = k.rsplit("_", 1)
                rows.append(dict(id=s["id"], moment=k, anchor=anchor, horizon=h, t=v[0], prob=v[1], lag_h=v[2]))
    a = pd.DataFrame(rows).merge(meta[["id", "y", "short"]], on="id", validate="m:1").merge(events, on="id", how="left", validate="m:1")
    a = a.merge(vol, on=["id", "moment"], how="left", validate="1:1").merge(cohort[["id", "cohort"]], on="id", validate="m:1")
    n = a[a.neg_risk == True][["id", "event_id", "moment", "t", "prob"]]  # one-winner events: sum sibling prices within a day of this moment
    pairs = n.merge(n, on=["event_id", "moment"], suffixes=("", "_sib"))
    event_sum = pairs[(pairs.t - pairs.t_sib).abs() <= 86400].groupby(["id", "moment"]).prob_sib.sum().rename("event_sum")
    a = a.merge(event_sum, on=["id", "moment"], how="left", validate="1:1")
    a = a.merge(labels[["id", "default_side", "substantive"]], on="id", validate="m:1")
    a["outside"] = a.id.map(outside)
    a["creator"] = a.id.map(event)  # the resampling unit, named creator for the shared helpers
    a["prob"] = a.prob.clip(.001, .999)
    a["bin"] = np.minimum((a.prob * 10).astype(int), 9)
    text = a.id.map({m["id"]: f'{m["question"]} | {m["event_title"] or ""}' for m in map(json.loads, open(HERE / "input.jsonl"))})
    a["kind"] = np.where(a.id.map(labels.set_index("id")["yes"]).map(lambda y: "speech_or_posts" in y), "speech_or_posts", "other")
    for kind, pat, not_pat in KINDS:  # speech_or_posts (Haiku), then the first rule that matches
        hit = text.map(lambda t: bool(re.search(pat, t, re.I)) and not (not_pat and re.search(not_pat, t, re.I)))
        a.loc[hit & (a.kind == "other"), "kind"] = kind
    a["source"] = np.where(a.outside.isna(), None, np.where(a.outside != "none", "has a source", np.where(a.substantive >= 80, "no source, substantive 80+", "no source, substantive <80")))
    return a


SPLITS = {
    "all": ("short", [(None, "#1d4ed8", "All markets"), (True, "#c2410c", "Closed within a week of starting")]),
    "default_side": ("default_side", [("NO", "#c2410c", "Nothing happening means NO"), ("YES", "#1d4ed8", "Nothing happening means YES"), ("NONE", "#047857", "No default side")]),
    "kind": ("kind", [("other", "#1d4ed8", "Everything else"), ("chart", "#c2410c", "Rankings, scores, box office, views"), ("speech_or_posts", "#6b7280", "Who says what, post counts"),
                      ("tsa", "#047857", "TSA passenger counts"), ("ai_leaderboard", "#7c3aed", "AI model leaderboards")]),  # metrics only, no plot
    "source": ("source", [("has a source", "#6b7280", "Outside source exists"), ("no source, substantive <80", "#1d4ed8", "No source, substantive <80"), ("no source, substantive 80+", "#c2410c", "No source, substantive 80+")]),
}


def groups(a, split):
    col, sides = SPLITS[split]
    for side, color, label in sides:
        yield side, color, label, (a if side is None else a[a[col] == side])


def weigh(a):
    """Within each moment, an event's markets share weight 1."""
    panel, event = [a.cohort, a.anchor, a.horizon], a.event_id.fillna(a.id)
    k = a.groupby(panel + [event]).id.transform("size")
    return a.assign(w=1 / k)


def tables(a, splits=SPLITS):
    bins, metrics = [], []
    for cohort, c in a.groupby("cohort"):
        for split in splits:
            for (anchor, h), g in c.groupby(["anchor", "horizon"]):
                for side, _, label, s in groups(g, split):
                    if len(s) < MIN_BIN:
                        continue
                    m = summary(s)
                    metrics.append(dict(cohort=cohort, split=split, group=label, anchor=anchor, horizon=h, events=s.creator.nunique(), brier=np.average((s.prob - s.y) ** 2, weights=s.get("w")), **m))
                    for b, x in s.groupby("bin"):
                        lo, hi = boot_rate(x) if len(x) >= MIN_BIN else (np.nan, np.nan)
                        bins.append(dict(cohort=cohort, split=split, group=label, anchor=anchor, horizon=h, bin=b, n=x.w.sum() if "w" in x else len(x), markets=len(x),
                                     price=np.average(x.prob, weights=x.get("w")), yes=np.average(x.y, weights=x.get("w")), yes_low=lo, yes_high=hi))
    return pd.DataFrame(bins), pd.DataFrame(metrics)


def plot_one(out, filtered, bins, split, anchors, name, title, note, unit="markets in the bin"):
    fig, axes = plt.subplots(len(anchors), 3, figsize=(15, 5.3 * len(anchors) + 1.2), squeeze=False, sharex=True, sharey=True)
    for row, anchor in zip(axes, anchors):
        for ax, h in zip(row, HORIZONS):
            ax.plot([0, 100], [0, 100], color="#bbbbbb", lw=1, zorder=0)
            ax.grid(color="#eeeeee", lw=.6)
            ax.spines[["top", "right"]].set_visible(False)
            ax.set(xlim=(0, 100), ylim=(0, 100), title=f"{h} {ANCHORS[anchor]}")
            for (side, color, label), offset in zip(SPLITS[split][1], [(-4, 6), (5, -10), (6, 1)]):
                b = bins[(bins.cohort == "closed_by_feb") & (bins.split == split) & (bins.group == label) & (bins.anchor == anchor) & (bins.horizon == h) & (bins.n >= MIN_BIN)]
                b = b.set_index("bin").reindex(range(10))  # a dropped bin breaks the line
                ax.errorbar(b.price * 100, b.yes * 100, yerr=[(b.yes - b.yes_low) * 100, (b.yes_high - b.yes) * 100], color=color, marker="o", ms=5, lw=1.8, elinewidth=.8, label=label)
                for r in b.dropna(subset="n").itertuples():
                    ax.annotate(f"{r.n:,.0f}", (r.price * 100, r.yes * 100), xytext=offset, textcoords="offset points", ha="right" if offset[0] < 0 else "left", fontsize=7, color="#444444")
        row[0].set_ylabel("Resolved YES (%)")
    for ax in axes[-1]:
        ax.set_xlabel("Price (%)")
    axes[0][0].legend(frameon=False, fontsize=9, loc="upper left")
    fig.suptitle(title, x=.01, ha="left", fontsize=14)
    gate = ("Kept only moments with $1,000+ traded before them (on-chain trades), and not in a one-winner event whose prices sum above 130% then.\n" if filtered
            else "UNFILTERED: includes moments before $1,000 had traded and one-winner events whose prices sum far above 100%.\n")
    fig.text(.01, .01, "Source: Polymarket Gamma and CLOB APIs; labels from Haiku, which saw text only. Resolved Yes/No markets that closed before Feb 2, 2026 with $1,000+ lifetime volume, sports, asset-price and weather markets removed.\n" + gate +
             f"Price: last hourly API price at or before the moment, at most 3 days old; moments outside trading skipped. 10-point bins, bins under 30 dropped, number = {unit}. Bars: 95%, resampling events.\n" + note,
             fontsize=8.5, color="#555555")
    fig.tight_layout(rect=(0, .12 if len(anchors) == 1 else .07, 1, .96))
    fig.savefig(out / f"{name}.png", dpi=140)
    plt.close(fig)


def main():
    a = frame()
    keep = (a.vol >= MIN_VOL) & a.neg_risk.notna() & ~(a.event_sum > MAX_SUM)  # open_in_feb has no event data, so it drops out
    print(a.groupby(["cohort", "anchor", "horizon"]).size().to_string(), f"\nno outside answer: {a.outside.isna().mean():.1%} of snapshots, median price age {a.lag_h.median():.1f}h", flush=True)
    print(f"moments under $1,000: {(a.vol < MIN_VOL).sum():,}, no volume (after Feb 2): {a.vol.isna().sum():,}, one-winner event sum over {MAX_SUM:.0%}: {(a.event_sum > MAX_SUM).sum():,}, kept {keep.sum():,} of {len(a):,}")
    for out, filtered, d in [(OUT, True, a[keep]), (OUT / "unfiltered", False, a)]:
        out.mkdir(parents=True, exist_ok=True)
        figures(out, filtered, d)


def figures(out, filtered, a):
    bins, metrics = tables(a)
    bins.to_csv(out / "bins.csv", index=False)
    metrics.round(4).to_csv(out / "metrics.csv", index=False)
    plot = lambda *x, **k: plot_one(out, filtered, *x, **k)
    plot(bins, "all", list(ANCHORS), "overall", "Polymarket calibration, all labeled markets",
         "Before closing: a market that resolves YES early closes early, so this moment depends on the outcome.")
    plot(bins, "default_side", list(ANCHORS), "by_side", "Polymarket, split by what happens if nothing new happens", "Haiku answered: if nothing new happens until the deadline, how does this resolve?")
    plot(bins, "source", ["after_start"], "by_source", "Polymarket, split by whether an outside source gives the answer",
         "Outside source: Haiku's forced-choice follow-up (polymarket/outside_prompt.txt): poll, odds, finance, data series, schedule or published forecast, not another prediction market. Substantive: 0-100 score from the main pass.")
    w = weigh(a)
    p = w[(w.cohort == "closed_by_feb") & (w.anchor == "after_start") & (w.horizon == "1w")]  # to eyeball the weights
    p.groupby("event_id").agg(title=("creator", "first"), markets=("id", "size"), weight=("w", "sum"), sides=("default_side", lambda s: s.value_counts().to_dict())) \
        .sort_values("markets", ascending=False).round(2).to_csv(out / "events_1w.csv")
    wbins, wmetrics = tables(w, ["default_side"])
    wbins.to_csv(out / "bins_weighted.csv", index=False)
    wmetrics.round(4).to_csv(out / "metrics_weighted.csv", index=False)
    plot(wbins, "default_side", list(ANCHORS), "by_side_weighted", "Polymarket by default side, each event counted once",
         "WEIGHTED: within each moment, an event's K markets get weight 1/K each.",
         unit="summed weight, about the number of events")


if __name__ == "__main__":
    main()
