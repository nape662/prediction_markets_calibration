"""Sample raw orders and compare their timestamps with stored snapshot fields."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # manifold/
from plot_calibration import load

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'manifold/other/plots/activity_analysis'
d = load().query("anchor == 'after_creation' and group == 'world' and horizon == '1w' and bettors >= 15")
ids = set(np.random.default_rng(42).choice(d.id.unique(), min(500, d.id.nunique()), replace=False))
markets = {m['id']:m for m in map(json.loads, open(ROOT/'data/manifold/api/markets.jsonl')) if m['id'] in ids}
rows = []
examples = []
for ident in ids:
    bets = [b for b in json.load(open(ROOT/'data/manifold/api/bets'/f'{ident}.json')) if not b.get('isRedemption')]
    m = markets[ident]; t = m['createdTime'] + 7*86400_000
    moves = [b for b in bets if b['probBefore'] != b['probAfter'] and b['createdTime'] <= t]
    affected = [b for b in moves if any(f['timestamp'] > t and f.get('amount',0) != 0 for f in b.get('fills',[]))]
    last = moves[-1]
    last_future = any(f['timestamp'] > t and f.get('amount',0) != 0 for f in last.get('fills',[]))
    fills = [(f['timestamp'], abs(f['amount']), b['userId']) for b in bets for f in b.get('fills') or [dict(timestamp=b['createdTime'], amount=b['amount'])] if f['timestamp'] <= t]
    users_all = {u for _,_,u in fills}; users_nonzero = {u for _,a,u in fills if a > 0}
    rows.append(dict(id=ident, any_future_fill_price_move=bool(affected), last_price_move_has_future_fill=last_future, bettors_all=len(users_all), bettors_nonzero=len(users_nonzero), zero_only_users=len(users_all-users_nonzero), delayed_orders=sum(any(f['timestamp'] > b['createdTime'] and f['amount'] != 0 for f in b.get('fills',[])) for b in bets), unfilled_zero=sum(not b.get('fills') and b['amount']==0 for b in bets), bets=len(bets)))
    if last_future and len(examples)<5:
        examples.append(dict(id=ident,question=m['question'],snapshot=t,order={k:last.get(k) for k in ['id','createdTime','probBefore','probAfter','amount','fills','isFilled','isCancelled','limitProb']}))
pd.DataFrame(rows).to_csv(OUT/'audit_sample.csv',index=False)
(OUT/'audit_examples.json').write_text(json.dumps(examples,indent=2))
print(pd.DataFrame(rows).sum(numeric_only=True).to_string())
print('markets',len(rows))
