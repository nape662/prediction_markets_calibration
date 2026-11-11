"""Compare after-creation calibration by activity; run in a tmux session."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # manifold/
from plot_calibration import load, EDGES

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'manifold/other/plots/activity_analysis'
OUT.mkdir(exist_ok=True)
d = load().query("anchor == 'after_creation' and group == 'world'").copy()
d['type'] = np.where(d.quo, 'Status quo NO', 'Other world')
horizons = ['1d', '1w', '1m']
rows = []
for dimension, thresholds in [('bettors', [15, 50, 100]), ('volume', [1000, 5000, 20000])]:
    fig, axes = plt.subplots(2, 3, figsize=(14, 8), sharex=True, sharey=True)
    for i, typ in enumerate(['Status quo NO', 'Other world']):
        for j, horizon in enumerate(horizons):
            ax = axes[i,j]; ax.plot([0,1], [0,1], color='gray', lw=1)
            for threshold in thresholds:
                g = d[(d.type == typ) & (d.horizon == horizon) & (d.bettors >= 15) & (d[dimension] >= threshold)]
                bins = g.groupby('bin').agg(n=('y','size'), p=('prob','mean'), y=('y','mean'))
                for b, v in bins.iterrows():
                    rows.append(dict(analysis=dimension, threshold=threshold, type=typ, horizon=horizon, bin_low=EDGES[b], bin_high=EDGES[b+1], n=int(v.n), p=v.p, y=v.y))
                b = bins[bins.n >= 10]
                ax.plot(b.p, b.y, 'o-', ms=3, label=f'{threshold:,}+: n={len(g):,}')
            ax.set_title(f'{typ}, {horizon}'); ax.grid(alpha=.2); ax.legend(fontsize=8)
            ax.set_xlim(0,1); ax.set_ylim(0,1)
            if j == 0: ax.set_ylabel('Fraction resolved YES')
            if i == 1: ax.set_xlabel('Mean snapshot probability')
    fig.suptitle(f'ORIGINAL COUNTS: minimum {dimension} by snapshot (also at least 15 bettors)', color='red')
    fig.tight_layout(); fig.savefig(OUT / f'{dimension}.png', dpi=140); plt.close(fig)

fig, axes = plt.subplots(1, 2, figsize=(10, 4.5), sharex=True, sharey=True)
for ax, typ in zip(axes, ['Status quo NO', 'Other world']):
    g = d[(d.type == typ) & d.horizon.isin(horizons) & (d.bettors >= 15)]
    ids = g.groupby('id').horizon.nunique(); g = g[g.id.isin(ids[ids == 3].index)]
    ax.plot([0,1], [0,1], color='gray', lw=1)
    for h in horizons:
        x = g[g.horizon == h]; bins = x.groupby('bin').agg(n=('y','size'), p=('prob','mean'), y=('y','mean'))
        for b,v in bins.iterrows():
            rows.append(dict(analysis='same_cohort', threshold=15, type=typ, horizon=h, bin_low=EDGES[b], bin_high=EDGES[b+1], n=int(v.n), p=v.p, y=v.y))
        b = bins[bins.n >= 10]; ax.plot(b.p,b.y,'o-',ms=3,label=f'{h}: n={len(x):,}')
    ax.set_title(typ); ax.set_xlabel('Mean snapshot probability'); ax.grid(alpha=.2); ax.legend(); ax.set_xlim(0,1); ax.set_ylim(0,1)
axes[0].set_ylabel('Fraction resolved YES'); fig.suptitle('ORIGINAL COUNTS: same markets with at least 15 bettors at all three snapshots', color='red'); fig.tight_layout(); fig.savefig(OUT/'same_cohort.png', dpi=140); plt.close(fig)

# The first non-redemption price-moving bet's probBefore approximates initial price.
initial = []
for ident in d.id.unique():
    bets = json.load(open(ROOT / 'data/manifold/api/bets' / f'{ident}.json'))
    moves = [b for b in bets if not b.get('isRedemption') and b['probBefore'] != b['probAfter']]
    assert moves and all(a['createdTime'] <= b['createdTime'] for a,b in zip(bets,bets[1:]))
    initial.append((ident, moves[0]['probBefore'], len(bets), sum(bool(b.get('fills')) for b in bets), sum(bool(b.get('fills')) and any(f['timestamp'] > b['createdTime'] for f in b['fills']) for b in bets)))
d = d.merge(pd.DataFrame(initial, columns=['id','initial','bets','with_fills','later_fills']), on='id', validate='many_to_one')
summary = []
for (typ,h),g in d[(d.bettors >= 15) & d.horizon.isin(horizons)].groupby(['type','horizon']):
    for subset,x in [('all',g),('p_ge_50',g[g.prob >= .5]),('p_lt_50',g[g.prob < .5])]:
        summary.append(dict(type=typ,horizon=h,subset=subset,n=len(x),mean_p=x.prob.mean(),yes=x.y.mean(),initial_50=np.isclose(x.initial,.5).mean(),initial_40_60=x.initial.between(.4,.6).mean(),same_initial=np.isclose(x.prob,x.initial,atol=.005).mean(),median_age_days=x.age_days.median(),stale_1d=(x.age_days>=1).mean(),stale_7d=(x.age_days>=7).mean(),mean_bettors=x.bettors.mean(),median_volume=x.volume.median()))
pd.DataFrame(rows).to_csv(OUT/'bins.csv',index=False)
pd.DataFrame(summary).to_csv(OUT/'metrics.csv',index=False)
d[['id','initial','bets','with_fills','later_fills']].drop_duplicates().to_csv(OUT/'initial_checks.csv',index=False)
print(pd.DataFrame(summary).round(3).to_string(index=False))
print('initial price counts',d[['id','initial']].drop_duplicates().initial.round(2).value_counts().head(10).to_string())
print('bets audit',d[['id','bets','with_fills','later_fills']].drop_duplicates().sum(numeric_only=True).to_dict())
