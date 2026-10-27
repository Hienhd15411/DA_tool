"""In tóm tắt bảng predictions_daily / live_eval_daily để kiểm tra snapshot đã lên Supabase."""
import os, requests

U, K = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'apikey': K, 'Authorization': f'Bearer {K}', 'Prefer': 'count=exact'}


def get(t, **p):
    r = requests.get(f'{U}/rest/v1/{t}', headers=H, params=p, timeout=60); r.raise_for_status()
    return r.json(), r.headers.get('content-range')


for t in ('predictions_daily', 'live_eval_daily'):
    _, cr = get(t, select='data_date', limit=1); print(t, 'rows', cr)
ev, _ = get('live_eval_daily', select='*', order='data_date')
print('eval days', len(ev), ev[0]['data_date'] if ev else '', '→', ev[-1]['data_date'] if ev else '')
for r in ev[-5:]: print(r)
s, cr = get('predictions_daily', select='data_date,ticker,rsi14,status,net', tn06r_signal='eq.true', order='data_date.desc', limit=10)
print('tn06r signals', cr); [print(x) for x in s]
op, cr = get('predictions_daily', select='data_date', status='eq.open', limit=1); print('open rows', cr)

nav, _ = get('paper_nav', select='*', order='date')
print('paper_nav', len(nav), nav[0] if nav else '', nav[-1] if nav else '')
tr, _ = get('paper_trades', select='signal_date,ticker,status,entry_date,entry_price,exit_date,pnl,sessions_left,held_sessions,source,data_date', order='signal_date.desc', limit=200)
from collections import Counter
print('paper_trades status', Counter(t['status'] for t in tr))
cl = [t['pnl'] for t in tr if t['status'] == 'closed']
if cl: print(f'closed {len(cl)} win {sum(p > 0 for p in cl) / len(cl):.0%} avg {sum(cl) / len(cl):+.2%}')
for t in tr:
    if t['status'] in ('planned', 'open'): print(t)
pr, _ = get('predictions_daily', select='data_date,ticker,regime,trend_score,industry', ticker='eq.PET', order='data_date', limit=3)
print('PET regime sample', pr)

import statistics as S
def win(rs):
    ic = [r['ic'] for r in rs if r['ic'] is not None]; ex = [r['tn07_net'] - r['market_net'] for r in rs if r['tn07_net'] is not None]
    return dict(n=len(rs), ic=S.mean(ic), ic_se2=2 * S.stdev(ic) / len(ic) ** .5, ex=S.mean(ex), ex_se2=2 * S.stdev(ex) / len(ex) ** .5,
                lift=S.mean(r['tn07_hit'] - r['pool_hit'] for r in rs if r['tn07_hit'] is not None),
                calib=S.mean(r['pred_mean'] - r['tn07_hit'] for r in rs if r['pred_mean'] is not None))
print('HEALTH last20', ev[-20][ 'data_date'], '→', ev[-1]['data_date'], win(ev[-20:]))
print('HEALTH prev20', ev[-40]['data_date'], '→', ev[-21]['data_date'], win(ev[-40:-20]))
print('HEALTH first20', win(ev[:20]))
