"""Rebuild world snapshots with nonzero-fill bettor counts and compare old/new."""
import json
from multiprocessing import Pool
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
from plot_calibration import load, EDGES
from snapshots import snapshots

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'plots/activity_analysis'
old = load().query("group == 'world' and anchor == 'after_creation' and horizon in ['1d','1w','1m']")
ids = set(old.id)
markets = [m for m in map(json.loads,open(ROOT/'data/manifold/api/markets.jsonl')) if m['id'] in ids]
assert len(markets) == len(ids)
with Pool(6) as pool:
    new = pd.DataFrame([r for rs in pool.imap_unordered(snapshots, markets, chunksize=30) for r in rs])
new = new.query("anchor == 'after_creation' and horizon in ['1d','1w','1m']")
x = old.merge(new[['id','anchor','horizon','bettors','prob','volume']],on=['id','anchor','horizon'],validate='one_to_one',suffixes=('_old','_new'))
assert len(x)==len(old) and (x.prob_old==x.prob_new).all() and (x.volume_old==x.volume_new).all()
x['type'] = x.quo.map({True:'Status quo NO', False:'Other world'})
rows=[]
fig, axes=plt.subplots(2,3,figsize=(13,8),sharex=True,sharey=True)
for i,typ in enumerate(['Status quo NO','Other world']):
 for j,h in enumerate(['1d','1w','1m']):
    ax=axes[i,j]; ax.plot([0,1],[0,1],color='gray',lw=1)
    g=x[(x.type==typ)&(x.horizon==h)]
    for col,label in [('bettors_old','Original'),('bettors_new','Corrected')]:
        z=g[g[col]>=15]; b=z.groupby('bin').agg(n=('y','size'),p=('prob_old','mean'),y=('y','mean'))
        rows.append(dict(type=typ,horizon=h,version=label,n=len(z),mean_prob=z.prob_old.mean(),yes=z.y.mean(),excluded_by_fix=((g.bettors_old>=15)&(g.bettors_new<15)).sum()))
        b=b[b.n>=10]; ax.plot(b.p,b.y,'o-',ms=3,label=f'{label}, n={len(z):,}')
    ax.set_title(f'{typ}, {h}');ax.legend(fontsize=8);ax.grid(alpha=.2);ax.set_xlim(0,1);ax.set_ylim(0,1)
    if j==0:ax.set_ylabel('Fraction resolved YES')
    if i==1:ax.set_xlabel('Mean snapshot probability')
fig.suptitle('CORRECTION: exclude zero-amount orders from bettor counts',color='red',fontsize=15,fontweight='bold')
fig.tight_layout(); fig.savefig(OUT/'bettor_count_before_after.png',dpi=140)
pd.DataFrame(rows).to_csv(OUT/'count_correction.csv',index=False)
x[['id','anchor','horizon','bettors_old','bettors_new']].to_csv(OUT/'corrected_counts.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False))
