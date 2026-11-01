"""What share of markets sits at each price, at each horizon before resolution, for all markets, world and status_quo_default.

python src/plot_price_distribution.py -> plots/price_distribution.png, plots/price_distribution.csv
Needs data/manifold/snapshots.parquet (src/snapshots.py) and labeling/results/full/manifold_final.jsonl.
"""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
QUIET = 0.2  # Jev reaches 0.8 on only 7 of 69 markets Opus calls status_quo_default; 0.2 finds 51 (notes/labeling_review.md)
SQ = "status_quo_default"

jev = {c["ids"][0]: c["probs"][SQ] for c in map(json.loads, open(ROOT / "labeling/results/full/manifold_jev.jsonl"))}
final = [json.loads(l) for l in open(ROOT / "labeling/results/full/manifold_final.jsonl")]
sets = {"All markets": {a["id"] for a in final},
        "World": {a["id"] for a in final if a["group"] == "world"},
        SQ: {a["id"] for a in final if (jev[a["id"]] >= QUIET if a["source"] == "jev" else SQ in a["yes"])}}
d = pd.read_parquet(ROOT / "data/manifold/snapshots.parquet")
d["percent"] = (d.prob * 100).round().astype(int)
horizons = ["12h", "1d", "1w", "1m", "1y"]

fig, axes = plt.subplots(3, 5, figsize=(17, 8), sharex=True, sharey=True)
rows = []
for r, (name, ids) in enumerate(sets.items()):
    for c, h in enumerate(horizons):
        g = d[(d.horizon == h) & d.id.isin(ids)]
        share = g.percent.value_counts(normalize=True).reindex(range(101), fill_value=0) * 100
        rows += [dict(set=name, horizon=h, percent=p, share=v, markets=len(g)) for p, v in share.items()]
        ax = axes[r, c]
        ax.bar(share.index, share.values, width=1, color="#2a6fbb")
        ax.set_ylim(0, 22)
        ax.set_xlim(-1, 101)
        ax.set_xticks([0, 10, 25, 50, 75, 90, 100])
        ax.set_yticks([0, 5, 10, 15, 20], ["0%", "5%", "10%", "15%", "20%"])
        ax.grid(axis="y", color="#e4e4e4", linewidth=0.6)
        ax.set_axisbelow(True)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_title(f"{h} before resolution, {len(g):,} markets" if r == 0 else f"{h}, {len(g):,} markets", fontsize=10)
    axes[r, 0].set_ylabel(f"{name}\n% of markets at that price", fontsize=10)
for ax in axes[-1]:
    ax.set_xlabel("Market price, rounded to a whole percent")
fig.suptitle("Where Manifold prices sit before resolution", fontsize=14, x=0.01, ha="left")
fig.text(0.01, 0.005, "Each market counts once per panel, at its last price-moving bet at or before resolution minus the horizon. Resolved YES/NO markets with at least 15 bettors.\n"
         f"World and groups: merged Jev, Opus and Terra labels. {SQ}: Jev probability ≥ {QUIET}, or a reviewer's yes.", fontsize=8.5, color="#555555")
fig.tight_layout(rect=(0, 0.05, 1, 0.97))
(ROOT / "plots").mkdir(exist_ok=True)
fig.savefig(ROOT / "plots/price_distribution.png", dpi=130)
pd.DataFrame(rows).to_csv(ROOT / "plots/price_distribution.csv", index=False, float_format="%.3f")
