"""Chọn top-K, backtest sau chi phí, và gate mục 6 trên tập test (không refit)."""
import pandas as pd, numpy as np, json, datetime as dt
from pathlib import Path
from .model import daily_ic


def net(gross, c):
    return (1-c['fee_per_side'])*(1+gross)*(1-c['fee_per_side']-c['sell_tax'])-1


def realized(d):
    r = d.fwd_ret_5.copy()
    lock = d.ret_t5_day <= -(d.limit-0.005)
    alt = d.close_t6/d.open_t1-1
    m = lock & alt.notna(); r[m] = alt[m]
    return r


def pick(g, col, topk, max_ind, exclude=()):
    g = g[g.value_top30 & ~g.ticker.isin(exclude)].sort_values(col, ascending=False)
    out, cnt = [], {}
    for _, row in g.iterrows():
        k = row.industry if isinstance(row.industry, str) else row.ticker
        if cnt.get(k, 0) >= max_ind: continue
        cnt[k] = cnt.get(k, 0)+1; out.append(row)
        if len(out) == topk: break
    return pd.DataFrame(out)


def block_boot(x, B, block, seed=7):
    rng = np.random.default_rng(seed); x = np.asarray(x); n = len(x)
    if n < 2*block: return [None, None]
    nb = int(np.ceil(n/block))
    m = [np.concatenate([x[s:s+block] for s in rng.integers(0, n-block+1, nb)])[:n].mean() for _ in range(B)]
    return [float(v) for v in np.percentile(m, [2.5, 97.5])]


def strategy_eval(d, col, cfg):
    L, C, G = cfg['ledger'], cfg['costs'], cfg['gate']
    d = d.dropna(subset=['fwd_ret_5']).copy(); d['real'] = realized(d)
    rows = []
    for dt_, g in d.groupby('date'):
        sel = pick(g, col, L['topk'], L['max_per_industry'])
        if sel.empty: continue
        s = sel[~(sel.open_gap_t1 >= sel.limit-0.005)]
        if s.empty: continue
        rows.append(dict(date=dt_, hit=s.y_bin.mean(), net=net(s.real, C).mean(), univ=g.fwd_ret_5.mean(),
                         base_pool=g[g.value_top30].y_bin.mean()))
    r = pd.DataFrame(rows)
    if r.empty:
        return dict(n_days=0), r
    r['excess'] = r.net - r.univ
    ic = daily_ic(d, col)
    cal = d.assign(b=pd.cut(d[col], [0, .2, .3, .4, .5, .6, 1])).groupby('b', observed=True).agg(p=(col, 'mean'), actual=('y_bin', 'mean'), n=('y_bin', 'size'))
    cal = cal[cal.n >= 30]
    dec = d.copy(); dec['dec'] = dec.groupby('date')[col].transform(lambda s: pd.qcut(s.rank(method='first'), 10, labels=False))
    dm = dec.groupby(['date', 'dec']).fwd_ret_5.mean().unstack(); spread = (dm[9]-dm[0]).dropna()
    res = dict(n_days=len(r), first=str(r.date.min().date()), last=str(r.date.max().date()),
               hit_top10=float(r.hit.mean()), base_pool=float(r.base_pool.mean()), lift=float(r.hit.mean()-r.base_pool.mean()),
               net_top10=float(r.net.mean()), univ_mean=float(r.univ.mean()),
               excess_ret_5=float(r.excess.mean()), excess_ci=block_boot(r.excess.values, G['bootstrap'], G['block']),
               ic_daily=float(ic.mean()), ic_ci=block_boot(ic.values, G['bootstrap'], G['block']),
               decile_spread=float(spread.mean()),
               calibration=[dict(bin=str(i), p=float(a.p), actual=float(a.actual), n=int(a.n)) for i, a in cal.iterrows()],
               calib_monotone=bool(len(cal) >= 3 and np.all(np.diff(cal.actual.values) > 0)))
    return res, r


def gate(cfg, scored):
    """Đánh giá chiến lược trên test (từ test_start) với model đóng băng → state/gate.json."""
    L, G = cfg['ledger'], cfg['gate']
    t = scored[scored.date >= L['test_start']]
    res = {}
    for col, nm in [('p_up_5', 'lightgbm'), ('p_lr', 'logistic')]:
        res[nm], daily = strategy_eval(t, col, cfg)
        if nm == 'lightgbm' and len(daily):
            daily.to_csv(Path(cfg['paths']['state']) / 'test_daily_lgb.csv', index=False)
    m, b = res['lightgbm'], res['logistic']
    n = m.get('n_days', 0)
    checks = {
        f'Đủ ngày test (>= {G["min_test_days"]})': n >= G['min_test_days'],
        'excess_ret_5 > 0 sau chi phí': n > 0 and m['excess_ret_5'] > 0,
        'IC_daily > 0, CI95 không chứa 0': n > 0 and m['ic_daily'] > 0 and (m['ic_ci'][0] or -1) > 0,
        'lift > 0': n > 0 and m['lift'] > 0,
        'Calibration đơn điệu': n > 0 and m['calib_monotone'],
        'Vượt baseline logistic (nguyên tắc 6)': n > 0 and b.get('n_days', 0) > 0 and m['excess_ret_5'] > b['excess_ret_5'],
    }
    out = dict(updated=dt.datetime.now().isoformat(timespec='seconds'), model_version=cfg['model_version'],
               test_start=L['test_start'], checks=checks, strategy_pass=all(checks.values()), metrics=res)
    json.dump(out, open(Path(cfg['paths']['state']) / 'gate.json', 'w'), indent=1, ensure_ascii=False, default=str)
    return out
