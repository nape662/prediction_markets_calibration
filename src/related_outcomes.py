"""Small text/metadata sensitivity analysis; no new classification or API calls.

Run .venv/bin/python src/related_outcomes.py after src/activity_correction.py.
Outputs and methodology are in plots/related_outcomes/ and notes/related_outcomes.md.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_calibration import EDGES, load

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "plots/related_outcomes"
HORIZONS = ["1d", "1w", "1m"]
TAGS = ["subjective_resolution", "creator_influence", "trader_influence", "insider_knowable", "platform_metric"]
REMOVALS = {
    "politics": "Politics", "ai": "AI", "culture": "Culture",
    "large_topics": "Politics + AI + culture", "top_templates": "20 largest title templates",
    "election_2024": "2024 US election storyline", "gaza_2024": "2024 Gaza ceasefire family",
    "gpt5_release": "First GPT-5 release family", "openai_crisis": "Nov 2023 OpenAI storyline",
    "storylines": "Four named families/storylines", "combined": "Large topics + templates + storylines",
}


def prepare():
    d = load()
    d = d[(d.group == "world") & (d.anchor == "after_creation") & d.horizon.isin(HORIZONS)].copy()
    counts = pd.read_csv(ROOT / "plots/activity_analysis/corrected_counts.csv")
    d = d.merge(counts, on=["id", "anchor", "horizon"], validate="1:1")
    assert (d.bettors == d.bettors_old).all()
    m = pd.read_parquet(ROOT / "data/labeling/manifold.parquet").drop(columns=["description", "creator", "platform"])
    c = pd.read_parquet(ROOT / "data/categories/manifold.parquet").rename(columns={"group": "template"})
    m = m.merge(c[["id", "template", "topic"]], on="id", validate="1:1").set_index("id")
    assert d.id.isin(m.index).all()
    primary = d[(d.horizon == "1w") & (d.bettors_new >= 15)]
    counts = m.loc[primary.id, "template"].value_counts().rename_axis("template").reset_index(name="markets")
    counts = counts.sort_values(["markets", "template"], ascending=[False, True])
    counts.to_csv(OUT / "templates_ranked.csv", index=False)
    m["top_templates"] = m.template.isin(counts.head(20).template)
    for topic in ["politics", "ai", "culture"]:
        m[topic] = m.topic.eq(topic)
    m["large_topics"] = m[["politics", "ai", "culture"]].any(axis=1)
    q, created = m.question.str.lower(), pd.to_datetime(m.created, utc=True)
    m["election_2024"] = (m.tags.str.contains(r"\b2024-us-presidential-election\b", na=False)
                          & created.between("2023-01-01", "2024-11-05 23:59:59.999999"))
    m["gaza_2024"] = (q.str.contains("ceasefire") & q.str.contains("hamas|gaza|palestine")
                       & created.between("2023-12-01", "2024-12-31 23:59:59.999999")
                       & ~q.str.contains("starmer|chomsky|ukraine|china|hezbollah|fatal|resume|call for|shut down"))
    m["gpt5_release"] = (q.str.contains(r"\bgpt[- ]?5\b") & q.str.contains("releas|launch|announc|deploy|arrive|come out")
                         & (created < "2025-01-01") & ~q.str.contains(r"gpt[- ]?5[.]|gpt[- ]?[6-9]"))
    m["openai_crisis"] = (q.str.contains("altman|openai|brockman|ilya|sutskever")
                           & created.between("2023-11-17", "2023-11-23 23:59:59.999999"))
    m["storylines"] = m[["election_2024", "gaza_2024", "gpt5_release", "openai_crisis"]].any(axis=1)
    m["combined"] = m[["large_topics", "top_templates", "storylines"]].any(axis=1)
    labels = {x["id"]: x for x in map(json.loads, open(ROOT / "labeling/results/full/manifold_final.jsonl"))}
    for tag in TAGS:
        m[tag] = ["yes" if tag in labels[i]["yes"] else "unsure" if tag in labels[i]["unsure"] else "no" for i in m.index]
    m.loc[primary.id, ["question", "created", "tags", "topic", "template", *REMOVALS, *TAGS]].to_csv(OUT / "membership.csv")
    return d.merge(m, on="id", validate="m:1")


def summary(g):
    residual = g.prob - g.y
    blocks = g.assign(residual=residual).groupby("creator").agg(total=("residual", "sum"), n=("id", "size"))
    rng = np.random.default_rng(730)
    weights = rng.multinomial(len(blocks), np.full(len(blocks), 1 / len(blocks)), 1000)
    lo, hi = np.percentile(weights @ blocks.total / (weights @ blocks.n), [2.5, 97.5])
    return dict(markets=len(g), creators=len(blocks), mean_forecast=g.prob.mean(), yes_share=g.y.mean(),
                gap=residual.mean(), gap_low=lo, gap_high=hi, brier=((g.prob - g.y) ** 2).mean())


def tables(d):
    metrics, bins = [], []
    for version, bettors in [("original", "bettors_old"), ("corrected", "bettors_new")]:
        eligible = d[d[bettors] >= 15]
        common = eligible.groupby("id").horizon.nunique().eq(len(HORIZONS))
        for fixed in [False, True]:
            data = eligible[eligible.id.isin(common[common].index)] if fixed else eligible
            for (h, quo), base in data.groupby(["horizon", "quo"]):
                selections = {"all": base, **{f"without_{key}": base[~base[key]] for key in REMOVALS}}
                if not fixed:
                    selections.update({f"{tag}_{value}": base[base[tag] == value] for tag in TAGS for value in ["no", "yes", "unsure"]})
                for name, g in selections.items():
                    if g.empty:
                        continue
                    key = dict(version=version, fixed_horizons=fixed, horizon=h, quo=quo, selection=name)
                    metrics.append(dict(key, base_markets=len(base), removed=len(base) - len(g), **summary(g)))
                    if not fixed and h == "1w":
                        for b, x in g.groupby("bin"):
                            bins.append(dict(key, low=EDGES[b], high=EDGES[b + 1], markets=len(x),
                                             mean_forecast=x.prob.mean(), yes_share=x.y.mean()))
    return pd.DataFrame(metrics), pd.DataFrame(bins)


def decorate(fig, version, method):
    fig.suptitle("Manifold world questions: does YES overprediction survive these exclusions?", x=.02, ha="left", fontsize=14)
    if version == "corrected":
        note = "CORRECTION: the 15-bettor cutoff excludes zero-amount orders/fills. Prices are unchanged."
    else:
        note = "ORIGINAL: the 15-bettor cutoff includes zero-amount orders/fills."
    fig.text(.02, .92, note, color="#b60000", weight="bold", fontsize=12)
    fig.text(.02, .015, method, fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, .89))


def plot_calibration(bins, metrics, version):
    fig, axes = plt.subplots(2, 3, figsize=(14, 9), sharex=True, sharey=True)
    primary = metrics[(metrics.version == version) & ~metrics.fixed_horizons & (metrics.horizon == "1w")]
    for row, quo in enumerate([True, False]):
        for col, removal in enumerate(["large_topics", "top_templates", "storylines"]):
            ax = axes[row, col]
            ax.plot([0, 1], [0, 1], color="#aaa", lw=1)
            for selection, label, color in [("all", "All", "#999999"), (f"without_{removal}", "Remaining", "#1767a6")]:
                b = bins[(bins.version == version) & (bins.quo == quo) & (bins.selection == selection)]
                stat = primary[(primary.quo == quo) & (primary.selection == selection)].iloc[0]
                ax.plot(b.mean_forecast, b.yes_share, color=color, lw=1, alpha=.8)
                ax.scatter(b.mean_forecast, b.yes_share, s=10 + 3 * np.sqrt(b.markets), facecolors=np.where(b.markets >= 30, color, "white"), edgecolors=color)
                ax.plot([], [], color=color, label=f"{label}: n={stat.markets:,}; gap={100 * stat.gap:.1f} pp")
            removed = primary[(primary.quo == quo) & (primary.selection == f"without_{removal}")].iloc[0]
            ax.set_title(f"Remove {REMOVALS[removal]}\n{removed.removed:,} removed ({removed.removed / removed.base_markets:.0%})", fontsize=11)
            ax.set(xlim=(0, 1), ylim=(0, 1), xticks=[0, .25, .5, .75, 1], yticks=[0, .25, .5, .75, 1])
            ax.grid(alpha=.2)
            ax.legend(fontsize=8, loc="upper left")
        axes[row, 0].set_ylabel(("Status quo / by-deadline" if quo else "Other world questions") + "\nFraction resolved YES")
    for ax in axes[-1]:
        ax.set_xlabel("Mean forecast probability")
    decorate(fig, version, "One market once, last available snapshot 1 week after creation; still unresolved and at least 15 bettors then. Only eventually resolved YES/NO markets.\n"
             "Dots use existing fixed probability bins (0–2–5–10–20…90–95–98–100%); hollow dots have fewer than 30 markets. Gap = mean forecast minus YES share.\n"
             "Topics and templates chosen by corrected 1-week sample size before examining outcomes; named families chosen from text/dates. See membership.csv and notes/related_outcomes.md.")
    fig.savefig(OUT / f"calibration_{version}.png", dpi=130)
    plt.close(fig)


def plot_types(metrics, version):
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.5), sharex=True, sharey=True)
    x = metrics[(metrics.version == version) & ~metrics.fixed_horizons & (metrics.horizon == "1w")]
    for ax, quo in zip(axes, [True, False]):
        ax.axvline(0, color="#888", lw=1)
        for j, tag in enumerate(TAGS):
            for value, offset, color in [("no", -.12, "#1767a6"), ("yes", .12, "#b85a15")]:
                s = x[(x.quo == quo) & (x.selection == f"{tag}_{value}")].iloc[0]
                ax.errorbar(100 * s.gap, j + offset, xerr=[[100 * (s.gap - s.gap_low)], [100 * (s.gap_high - s.gap)]],
                            fmt="o", color=color, label=value if j == 0 else None)
                ax.annotate(f"n={s.markets:,}", (100 * s.gap_high + .4, j + offset), fontsize=8, va="center")
        ax.set_title("Status quo / by-deadline" if quo else "Other world questions")
        ax.set_yticks(range(len(TAGS)), [t.replace("_", " ") for t in TAGS])
        ax.set_xlabel("Mean forecast minus YES share (percentage points)")
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=.2)
        ax.legend(title="Existing label", fontsize=9)
    decorate(fig, version, "Same 1-week cohort as calibration figure. Each market has several overlapping existing classifier labels; these labels do not identify shared events.\n"
             "Unsure labels are excluded from each yes/no comparison and retained in metrics.csv. Existing final merged labels are used without new LLM calls.\n"
             "Bars resample creators 1,000 times (seed 730): 95% intervals for the mean gap. Different creators can share outcomes, so these intervals may be too narrow.")
    fig.savefig(OUT / f"question_types_{version}.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    data = prepare()
    metrics, bins = tables(data)
    metrics.to_csv(OUT / "metrics.csv", index=False)
    bins.to_csv(OUT / "bins.csv", index=False)
    for version in ["original", "corrected"]:
        plot_calibration(bins, metrics, version)
        plot_types(metrics, version)
    print(metrics[(metrics.version == "corrected") & ~metrics.fixed_horizons & (metrics.horizon == "1w") & metrics.selection.str.startswith(("all", "without_"))].to_string(index=False))
