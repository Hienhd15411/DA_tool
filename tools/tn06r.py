"""TN06-R — backtest hệ 2 tầng capitulation theo docs/TN06R_spec.md (spec chốt trước).

Dùng: python tools/tn06r.py <panel.parquet> <vnindex.parquet>
Ra: tools/out/tn06r/{summary.json, trades_*.csv, equity.csv}
"""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from vnq import features as F  # noqa: E402
from vnq.config import load as load_cfg  # noqa: E402
from vnq.backtest import net, realized, block_boot  # noqa: E402
warnings.filterwarnings('ignore')
OUT = ROOT / 'tools' / 'out' / 'tn06r'
RNG = np.random.default_rng(7)
H, SLOTS, MAX_IND = 5, 10, 3
IS = ('2022-10-24', '2026-06-30')
OOS_START = '2026-07-01'


def prepare(cfg, p, v):
    e = F.build(cfg, p, v).sort_values(['ticker', 'date']).reset_index(drop=True)
    dates = np.sort(p.date.unique())
    di = {d: i for i, d in enumerate(dates)}
    e['di'] = e.date.map(di)
    g = e.groupby('ticker')
    # RSI 3 phiên liên tiếp: chỉ tính khi 2 hàng trước đúng là 2 phiên giao dịch liền trước
    for k in (1, 2):
        ok = g.di.shift(k) == e.di - k
        e[f'rsi_l{k}'] = g.rsi14.shift(k).where(ok)
    e['cond_rsi1'] = e.rsi14 < 30
    e['cond_cap'] = e.cond_rsi1 & (e.rsi_l1 < 30) & (e.rsi_l2 < 30) & (e.vol_ratio20 >= 1.5)
    v = v.sort_values('date').copy()
    # sửa đổi R1 (docs/TN06R_spec.md §9): BẬT khi VNINDEX < EMA50
    v['ema50'] = v.close.ewm(span=50, adjust=False, min_periods=50).mean()
    v['regime_on'] = v.close < v.ema50
    v['vni5'] = v.close.shift(-H) / v.close - 1
    e = e.merge(v[['date', 'regime_on', 'vni5']], on='date', how='left')
    e['regime_on'] = e.regime_on.fillna(False).astype(bool)
    e = e[e.fwd_ret_5.notna()].copy()
    e['real'] = realized(e)
    e['net'] = net(e.real, cfg['costs'])
    e['buyable'] = ~(e.open_gap_t1 >= e.limit - 0.005)
    return e, v


def dedupe(ev):
    """Bỏ sự kiện cùng mã trong 5 phiên sau sự kiện trước (chống đếm trùng)."""
    keep, last = [], {}
    for r in ev.sort_values('date').itertuples():
        if r.ticker in last and r.di - last[r.ticker] <= H: continue
        last[r.ticker] = r.di; keep.append(r.Index)
    return ev.loc[keep]


def events(e, cond, use_regime):
    m = e[cond] & e.buyable
    if use_regime: m &= e.regime_on
    return dedupe(e[m])


def bench(e, ev, cfg):
    """Mỗi ngày có sự kiện: so với random (cùng số mã), thị trường EW, VNINDEX."""
    rows = []
    for d, g in ev.groupby('date'):
        u = e[(e.date == d) & e.buyable]
        un = u.net.values; k = min(len(g), len(un))
        rand = np.mean([un[RNG.choice(len(un), k, replace=False)].mean() for _ in range(500)])
        rows.append(dict(date=d, n=len(g), net=g.net.mean(), random=rand, market=un.mean(), vnindex=g.vni5.iloc[0]))
    return pd.DataFrame(rows)


def stats(ev, b, G):
    if ev.empty: return dict(n_trades=0)
    out = dict(n_trades=len(ev), n_days=len(b), net_per_trade=ev.net.mean(), hit_net_pos=(ev.net > 0).mean(),
               hit_ybin=ev.y_bin.mean(), median=ev.net.median())
    w = b.n.values
    for k in ('random', 'market', 'vnindex'):
        x = (b.net - b[k]).values
        out[f'vs_{k}'] = float(np.average(x, weights=w))           # trung bình theo lệnh
        out[f'vs_{k}_ci'] = block_boot(np.repeat(x, w), G['bootstrap'], G['block'])
    return {k: (round(float(v), 5) if isinstance(v, (float, np.floating)) else v) for k, v in out.items()}


def portfolio(e, ev, v, start, end):
    """10 slot, mỗi slot 10% equity lúc vào lệnh, ưu tiên RSI thấp, ≤3 mã/ngành đang giữ."""
    dates = np.sort(e.date.unique()); dates = dates[(dates >= np.datetime64(start)) & (dates <= np.datetime64(end))]
    by_day = {d: g.sort_values('rsi14') for d, g in ev.groupby('date')}
    cash, eq_hist, open_pos, taken = 1.0, [], [], []
    for d in dates:
        di = e.loc[e.date == d, 'di'].iloc[0] if (e.date == d).any() else None
        # đóng vị thế đến hạn (exit index đã tính sẵn)
        still = []
        for pos in open_pos:
            if di is not None and di >= pos['exit_di']: cash += pos['amt'] * (1 + pos['net'])
            else: still.append(pos)
        open_pos = still
        equity = cash + sum(p['amt'] for p in open_pos)   # vị thế đang mở tính theo giá vốn
        eq_hist.append(dict(date=d, equity=equity, n_open=len(open_pos)))
        if d in by_day:
            for r in by_day[d].itertuples():
                if len(open_pos) >= SLOTS: break
                ind = r.industry if isinstance(r.industry, str) else r.ticker
                if any(p['ticker'] == r.ticker for p in open_pos): continue
                if sum(p['ind'] == ind for p in open_pos) >= MAX_IND: continue
                amt = min(equity / SLOTS, cash)
                if amt <= 0: break
                lock = (r.ret_t5_day <= -(r.limit - 0.005)) and pd.notna(r.close_t6)
                cash -= amt
                open_pos.append(dict(ticker=r.ticker, ind=ind, amt=amt, net=r.net, exit_di=r.di + H + (2 if lock else 1)))
                taken.append(dict(date=d, ticker=r.ticker, industry=ind, rsi14=r.rsi14, vol_ratio20=r.vol_ratio20, net=r.net))
    for p in open_pos: cash += p['amt'] * (1 + p['net'])
    eq = pd.DataFrame(eq_hist)
    vs = v.set_index('date').close
    vni_bh = float(vs.asof(pd.Timestamp(dates[-1])) / vs.asof(pd.Timestamp(dates[0])) - 1)
    ew = e[(e.date >= dates[0]) & (e.date <= dates[-1])].groupby('date').ret1.mean()
    return dict(final_return=round(cash - 1, 4), vnindex_buyhold=round(vni_bh, 4),
                ew_universe_buyhold=round(float((1 + ew).prod() - 1), 4), n_taken=len(taken),
                avg_slots_used=round(float(eq.n_open.mean()), 2),
                max_drawdown=round(float((eq.equity / eq.equity.cummax() - 1).min()), 4)), eq, pd.DataFrame(taken)


def main():
    cfg = load_cfg(str(ROOT / 'engine/config.yaml'))
    cfg['paths']['industry'] = str(ROOT / 'engine/data/seed/industry.csv')
    G = cfg['gate']
    p, v = pd.read_parquet(sys.argv[1]), pd.read_parquet(sys.argv[2])
    e, v = prepare(cfg, p, v)
    OUT.mkdir(parents=True, exist_ok=True)
    systems = {'TN06R': ('cond_cap', True), 'L1_rsi30_only': ('cond_rsi1', True), 'L2_no_regime': ('cond_cap', False)}
    res = {}
    for per, (a, b_) in {'IS': IS, 'OOS': (OOS_START, '2100-01-01')}.items():
        ep = e[(e.date >= a) & (e.date <= b_)]
        res[per] = {'regime_on_pct': round(float(ep.groupby('date').regime_on.first().mean()), 3),
                    'first': str(ep.date.min().date()), 'last': str(ep.date.max().date())}
        for nm, (c, reg) in systems.items():
            ev = events(ep, c, reg)
            b = bench(ep, ev, cfg) if len(ev) else pd.DataFrame()
            res[per][nm] = stats(ev, b, G)
            ev[['date', 'ticker', 'industry', 'rsi14', 'vol_ratio20', 'regime_on', 'real', 'net', 'y_bin', 'vni5']].to_csv(OUT / f'trades_{per}_{nm}.csv', index=False)
        # T1 — chỉ canh thời điểm: ngày BẬT mua đều toàn universe vs mua đều mọi ngày
        day = ep[ep.buyable].groupby('date').agg(net=('net', 'mean'), on=('regime_on', 'first'))
        t1, allx = day[day.on].net, day.net
        res[per]['T1_timing'] = dict(days_on=int(len(t1)), net_on=round(float(t1.mean()), 5) if len(t1) else None,
                                     net_on_ci=block_boot(t1.values, G['bootstrap'], G['block']),
                                     net_all_days=round(float(allx.mean()), 5),
                                     net_off=round(float(day[~day.on].net.mean()), 5) if (~day.on).any() else None)
        ev = events(ep, 'cond_cap', True)
        if len(ev):
            pf, eq, tk = portfolio(ep, ev, v, a, ep.date.max())
            res[per]['portfolio_TN06R'] = pf
            eq.to_csv(OUT / f'equity_{per}.csv', index=False); tk.to_csv(OUT / f'portfolio_trades_{per}.csv', index=False)
    o, l1 = res['OOS']['TN06R'], res['OOS']['L1_rsi30_only']
    n = o.get('n_trades', 0)
    checks = {'>=30 lệnh': n >= 30,
              'vs thị trường > 0, CI95 không chứa 0': n > 0 and o['vs_market'] > 0 and (o['vs_market_ci'][0] or -1) > 0,
              'vs random > 0': n > 0 and o['vs_random'] > 0,
              'thắng L1 (vs thị trường)': n > 0 and l1.get('n_trades', 0) > 0 and o['vs_market'] > l1['vs_market']}
    t = res['OOS']['T1_timing']
    tchecks = {'>=20 ngày BẬT': t['days_on'] >= 20,
               'lãi TB ngày BẬT > 0, CI95 không chứa 0': t['days_on'] > 0 and t['net_on'] > 0 and (t['net_on_ci'][0] or -1) > 0,
               '> mua đều mọi ngày': t['days_on'] > 0 and t['net_on'] > t['net_all_days']}
    res['gate'] = dict(checks=checks, verdict='GO' if all(checks.values()) else ('CHƯA ĐỦ BẰNG CHỨNG' if n < 30 else 'NO-GO'),
                       timing_checks=tchecks,
                       timing_verdict='GO' if all(tchecks.values()) else ('CHƯA ĐỦ BẰNG CHỨNG' if t['days_on'] < 20 else 'NO-GO'))
    json.dump(res, open(OUT / 'summary.json', 'w'), indent=1, ensure_ascii=False, default=str)
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
