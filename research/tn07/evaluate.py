"""TN07 — backtest top10/ngày: lọc thanh khoản → value top30% → xếp hạng score → top10 (≤3 mã/ngành).
Entry open t+1, exit close t+5, trừ phí 2 chiều + thuế bán; bỏ lệnh nếu open t+1 kịch trần; exit trễ 1 phiên nếu t+5 kịch sàn."""
import pandas as pd, numpy as np, json, sys
from train import FEE, TAX, TOPK, MAX_PER_IND, daily_ic
rng = np.random.default_rng(7)

def net(gross): return (1-FEE)*(1+gross)*(1-FEE-TAX)-1

def realized(d):
    r = d.fwd_ret_5.copy()
    floor_lock = d.ret_t5_day <= -(d.limit-0.005)
    alt = d.close_t6/d.open_t1-1
    r[floor_lock & alt.notna()] = alt[floor_lock & alt.notna()]
    return r

def pick(g, col):
    g = g[g.value_top30].sort_values(col, ascending=False)
    out, cnt = [], {}
    for _, row in g.iterrows():
        k = row.industry if isinstance(row.industry, str) else row.ticker
        if cnt.get(k, 0) >= MAX_PER_IND: continue
        cnt[k] = cnt.get(k, 0)+1; out.append(row)
        if len(out) == TOPK: break
    return pd.DataFrame(out)

def block_boot(x, B=2000, block=5):
    x = np.asarray(x); n = len(x)
    if n < 2*block: return (np.nan, np.nan)
    nb = int(np.ceil(n/block)); means = []
    for _ in range(B):
        st = rng.integers(0, n-block+1, nb)
        means.append(np.concatenate([x[s:s+block] for s in st])[:n].mean())
    return tuple(np.percentile(means, [2.5, 97.5]))

def evaluate(d, col, name):
    d = d.dropna(subset=['fwd_ret_5']).copy()
    d['real'] = realized(d)
    rows = []
    for dt, g in d.groupby('date'):
        sel = pick(g, col)
        if sel.empty: continue
        ceil = sel.open_gap_t1 >= sel.limit-0.005
        s = sel[~ceil]
        rows.append(dict(date=dt, n_sel=len(s), n_skip_ceiling=int(ceil.sum()),
                         gross=s.real.mean(), net=net(s.real).mean(), hit=s.y_bin.mean(),
                         univ_mean=g.fwd_ret_5.mean(), pool_mean=g[g.value_top30].fwd_ret_5.mean(),
                         base_univ=g.y_bin.mean(), base_pool=g[g.value_top30].y_bin.mean()))
    r = pd.DataFrame(rows)
    r['excess_net_vs_univ'] = r.net-r.univ_mean
    r['excess_net_vs_pool'] = r.net-r.pool_mean
    ic_u = daily_ic(d, col); ic_p = daily_ic(d[d.value_top30], col)
    dec = d.copy(); dec['dec'] = dec.groupby('date')[col].transform(lambda s: pd.qcut(s.rank(method='first'), 10, labels=False))
    dm = dec.groupby(['date', 'dec']).fwd_ret_5.mean().unstack()
    spread = (dm[9]-dm[0]).dropna()
    cal = d.assign(b=pd.cut(d[col], [0, .2, .3, .4, .5, .6, 1])).groupby('b', observed=True).agg(p=(col, 'mean'), actual=('y_bin', 'mean'), n=('y_bin', 'size'))
    mono = bool(np.all(np.diff(cal.actual.values) > 0))
    res = dict(strategy=name, n_days=len(r), hit_top10=r.hit.mean(), base_pool=r.base_pool.mean(), base_univ=r.base_univ.mean(),
               lift_vs_pool=r.hit.mean()-r.base_pool.mean(), gross_top10=r.gross.mean(), net_top10=r.net.mean(),
               univ_mean=r.univ_mean.mean(), pool_mean=r.pool_mean.mean(),
               excess_ret_5_net=r.excess_net_vs_univ.mean(), excess_ci=block_boot(r.excess_net_vs_univ.values),
               excess_vs_pool_net=r.excess_net_vs_pool.mean(),
               IC_univ=ic_u.mean(), IC_univ_ci=block_boot(ic_u.values), IC_pool=ic_p.mean(), IC_pool_ci=block_boot(ic_p.values),
               decile_spread=spread.mean(), decile_ci=block_boot(spread.values), calib_monotone=mono,
               skipped_ceiling=int(r.n_skip_ceiling.sum()))
    return res, r, cal

if __name__ == '__main__':
    out = []
    for label, path in [('WF-OOS 2025-07..2026-06 (4 fold)', 'out/oos_walkforward.parquet'), ('TEST 2026-07-01..', 'out/test_scored.parquet')]:
        d = pd.read_parquet(path)
        d['rand'] = rng.random(len(d)); d['mom20'] = d.ret20
        cols = [('p_up_5', 'LightGBM'), ('p_lr', 'Logistic'), ('mom20', 'Momentum20'), ('rand', 'Random(pool)')]
        for col, nm in cols:
            res, daily, cal = evaluate(d, col, nm); res['set'] = label; out.append(res)
            if nm == 'LightGBM':
                daily.to_csv(f"out/daily_{'oos' if 'WF' in label else 'test'}_lgb.csv", index=False)
                cal.to_csv(f"out/calibration_{'oos' if 'WF' in label else 'test'}_lgb.csv")
                print(label, '\n', cal.round(3))
        if 'WF' in label:  # theo fold
            for f, g in d.groupby('fold'):
                res, _, _ = evaluate(g, 'p_up_5', f'LightGBM fold{f}'); res['set'] = label; out.append(res)
    o = pd.DataFrame(out)
    o.to_csv('out/backtest_summary.csv', index=False)
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
    show = ['set', 'strategy', 'n_days', 'hit_top10', 'base_pool', 'lift_vs_pool', 'net_top10', 'univ_mean', 'excess_ret_5_net', 'excess_ci', 'IC_univ', 'IC_univ_ci', 'IC_pool', 'decile_spread', 'calib_monotone', 'skipped_ceiling']
    print(o[show].to_string(float_format=lambda x: f'{x:.4f}'))
