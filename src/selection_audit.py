"""One-week sensitivity to delayed fills, price age, and creation cohorts."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_calibration import EDGES, load

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "plots/selection_audit"


def main():
    OUT.mkdir(exist_ok=True)
    d = load().query("group == 'world' and anchor == 'after_creation' and horizon == '1w'")
    counts = pd.read_csv(ROOT / "plots/activity_analysis/corrected_counts.csv")
    d = d.merge(counts, on=["id", "anchor", "horizon"], validate="one_to_one")
    assert (d.bettors == d.bettors_old).all()
    d = d[d.bettors_old >= 15].copy()
    ids = set(d.id)
    markets = {m["id"]: m for m in map(json.loads, open(ROOT / "data/manifold/api/markets.jsonl")) if m["id"] in ids}
    assert len(markets) == len(ids)
    audit = []
    for row in d.itertuples():
        m = markets[row.id]
        t = m["createdTime"] + 7 * 86400_000
        bets = json.load(open(ROOT / "data/manifold/api/bets" / f"{row.id}.json"))
        assert all(a["createdTime"] <= b["createdTime"] for a, b in zip(bets, bets[1:]))
        moves = [b for b in bets if not b.get("isRedemption") and b["probBefore"] != b["probAfter"] and b["createdTime"] <= t]
        assert moves and moves[-1]["probAfter"] == row.prob
        future = [any(f["timestamp"] > t and f["amount"] != 0 for f in b.get("fills", [])) for b in moves]
        audit.append(dict(id=row.id, created=m["createdTime"], last_future=future[-1], any_future=any(future)))
    d = d.merge(pd.DataFrame(audit), on="id", validate="one_to_one")
    d["year"] = pd.to_datetime(d.created, unit="ms", utc=True).dt.year
    d["type"] = np.where(d.quo, "Status quo NO", "Other world")
    d[["id", "type", "year", "bettors_old", "bettors_new", "age_days", "volume", "last_future", "any_future"]].to_csv(OUT / "membership.csv", index=False)
    checks = {
        "All eligible": pd.Series(True, index=d.index),
        "No later fills in selected order": ~d.last_future,
        "No later fills in any earlier price-moving order": ~d.any_future,
        "Last price move within 24h": d.age_days <= 1,
        "Snapshot fill volume >= 1000": d.volume >= 1000,
        "Created before 2025": d.year < 2025,
        "Created before 2024": d.year < 2024,
    }
    metrics, bins = [], []
    for version, count in [("original", "bettors_old"), ("corrected", "bettors_new")]:
        eligible = d[count] >= 15
        fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True, sharey=True)
        for i, typ in enumerate(["Status quo NO", "Other world"]):
            for name, mask in checks.items():
                g = d[eligible & (d.type == typ) & mask]
                assert len(g)
                metrics.append(dict(version=version, type=typ, check=name, markets=len(g), mean_probability=g.prob.mean(), yes_share=g.y.mean(), gap=(g.prob-g.y).mean()))
                b = g.groupby("bin").agg(markets=("y", "size"), mean_probability=("prob", "mean"), yes_share=("y", "mean"))
                for k, v in b.iterrows():
                    bins.append(dict(version=version, type=typ, check=name, low=EDGES[k], high=EDGES[k+1], **v.to_dict()))
                col = 0 if "fills" in name else 1 if name.startswith(("Last", "Snapshot")) else 2
                for j in (range(3) if name == "All eligible" else [col]):
                    p = b[b.markets >= 30]
                    axes[i, j].plot(p.mean_probability, p.yes_share, "o-", ms=3, label=f"{name} (n={len(g):,})")
            for j, label in enumerate(["Delayed-fill exclusions", "Freshness / volume", "Older creation cohorts"]):
                ax = axes[i, j]
                ax.plot([0, 1], [0, 1], color="gray", lw=1)
                ax.set(xlim=(0, 1), ylim=(0, 1), title=f"{typ}: {label}")
                ax.grid(alpha=.2)
                ax.legend(fontsize=7)
                if i == 1:
                    ax.set_xlabel("Mean forecast probability")
                if j == 0:
                    ax.set_ylabel("Fraction resolved YES")
        fig.suptitle(f"{version.upper()} BETTOR COUNTS: one week after creation", color="red", fontweight="bold")
        fig.text(.01, .01, "Corrected counts exclude zero-amount orders. Same prices/outcomes. Bins with fewer than 30 markets omitted; no uncertainty bars.", fontsize=9, color="red")
        fig.tight_layout(rect=(0, .04, 1, .95))
        fig.savefig(OUT / f"calibration_{version}.png", dpi=130)
        plt.close(fig)
    pd.DataFrame(metrics).to_csv(OUT / "metrics.csv", index=False)
    pd.DataFrame(bins).to_csv(OUT / "bins.csv", index=False)
    print(pd.DataFrame(metrics).query("version == 'corrected'").to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
