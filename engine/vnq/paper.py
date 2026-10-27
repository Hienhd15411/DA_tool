"""Danh mục mô phỏng (paper trading) theo luật TN06-R — trả lời: khi nào mua, mua gì, bao nhiêu, bán gì, bán bao nhiêu.

Luật (docs/TN06R_spec.md, đã chốt):
  Khi nào mua : tín hiệu TN06-R tại ngày t (tầng 1 BẬT: VNINDEX < EMA50) → vào lệnh giá MỞ CỬA phiên t+1
                (bỏ nếu mở cửa sát trần).
  Mua bao nhiêu: mỗi lệnh 10% giá trị danh mục (NAV đóng cửa ngày t), tối đa 10 lệnh cùng lúc, ≤ 3 mã/ngành,
                nhiều tín hiệu hơn chỗ trống → ưu tiên RSI14 thấp nhất. Tiền nhàn rỗi để tiền mặt.
  Bán gì      : lệnh đã giữ đủ 5 phiên (vào open t+1 → bán ĐÓNG CỬA phiên t+5); phiên đó kẹt sàn → bán phiên sau.
  Bán bao nhiêu: bán 100% vị thế của lệnh đó. Không cắt lỗ / chốt lời giữa chừng (spec không có).
Phí 0,15%/chiều + thuế bán 0,1%. Không dùng giá sau ngày dữ liệu.
"""
import pandas as pd, numpy as np
from pathlib import Path

H, SLOTS, MAX_IND = 5, 10, 3


def run(cfg, log, panel, sc, start):
    C = cfg['costs']; fee, tax = C['fee_per_side'], C['sell_tax']
    px = panel[panel.date >= pd.Timestamp(start) - pd.Timedelta(days=10)]
    dates = np.sort(panel.date.unique()); dates = dates[dates >= np.datetime64(pd.Timestamp(start))]
    if not len(dates): return None
    di = {pd.Timestamp(d): i for i, d in enumerate(dates)}
    op = px.pivot(index='date', columns='ticker', values='open')
    cl = px.pivot(index='date', columns='ticker', values='close').ffill()
    lim = sc.groupby('ticker').limit.last().to_dict()
    sig = log[log.tn06r_signal.astype(bool)].copy()
    sig['data_date'] = pd.to_datetime(sig.data_date)
    sig = sig[sig.data_date >= pd.Timestamp(start)].sort_values(['data_date', 'rsi14'])
    by_day = {d: g for d, g in sig.groupby('data_date')}

    cash, pos, trades, nav_hist = 1.0, [], [], []
    nav_prev = 1.0
    for i, d in enumerate(dates):
        d = pd.Timestamp(d)
        prev = pd.Timestamp(dates[i - 1]) if i else None
        # 1) mở cửa: vào lệnh cho tín hiệu của phiên trước
        if prev is not None and prev in by_day:
            for r in by_day[prev].itertuples():
                t = dict(signal_date=prev, ticker=r.ticker, industry=r.industry, rsi14=r.rsi14, source=r.source,
                         entry_date=d, weight=1 / SLOTS)
                ind = r.industry if isinstance(r.industry, str) else r.ticker
                o, c0 = op.at[d, r.ticker] if r.ticker in op else np.nan, cl.at[prev, r.ticker] if r.ticker in cl else np.nan
                if len(pos) >= SLOTS: t['status'] = 'skipped_full'
                elif sum(p['ind'] == ind for p in pos) >= MAX_IND: t['status'] = 'skipped_industry'
                elif any(p['ticker'] == r.ticker for p in pos): t['status'] = 'skipped_holding'
                elif not np.isfinite(o) or o <= 0: t['status'] = 'skipped_no_price'
                elif o / c0 - 1 >= lim.get(r.ticker, 0.07) - 0.005: t['status'] = 'skipped_ceiling'
                else:
                    amt = min(nav_prev / SLOTS, cash)
                    if amt <= 1e-9: t['status'] = 'skipped_full'
                    else:
                        cash -= amt
                        p = dict(ticker=r.ticker, ind=ind, shares=amt * (1 - fee) / o, amt=amt, exit_i=di[prev] + H, tid=len(trades))
                        pos.append(p); t.update(status='open', entry_price=o, amount=amt, planned_exit_i=p['exit_i'])
                trades.append(t)
        # 2) đóng cửa: bán lệnh đến hạn (kẹt sàn → hoãn 1 phiên, một lần)
        keep = []
        for p in pos:
            if i >= p['exit_i']:
                c, cp = cl.at[d, p['ticker']], cl.at[prev, p['ticker']]
                if i == p['exit_i'] and c / cp - 1 <= -(lim.get(p['ticker'], 0.07) - 0.005):
                    p['exit_i'] += 1; keep.append(p); continue
                proceeds = p['shares'] * c * (1 - fee - tax); cash += proceeds
                trades[p['tid']].update(status='closed', exit_date=d, exit_price=c, pnl=proceeds / p['amt'] - 1)
            else:
                keep.append(p)
        pos = keep
        nav = cash + sum(p['shares'] * cl.at[d, p['ticker']] for p in pos)
        nav_hist.append(dict(date=d, nav=nav, cash_pct=cash / nav, n_open=len(pos)))
        nav_prev = nav

    last = pd.Timestamp(dates[-1]); i_last = len(dates) - 1
    tr = pd.DataFrame(trades)
    for p in pos:   # vị thế đang mở: lãi/lỗ tạm tính theo đóng cửa ngày dữ liệu
        c = cl.at[last, p['ticker']]
        tr.loc[p['tid'], 'mark_price'] = c
        tr.loc[p['tid'], 'pnl'] = p['shares'] * c * (1 - fee - tax) / p['amt'] - 1
        tr.loc[p['tid'], 'sessions_left'] = p['exit_i'] - i_last
    if len(tr):
        tr['held_sessions'] = [i_last - di[e] + 1 if s == 'open' else np.nan for s, e in zip(tr.status, tr.entry_date)]
    # tín hiệu của chính ngày dữ liệu → lệnh vào ở phiên kế tiếp
    plan = []
    if last in by_day:
        n_open = len(pos); inds = [p['ind'] for p in pos]; held = {p['ticker'] for p in pos}
        for r in by_day[last].itertuples():
            ind = r.industry if isinstance(r.industry, str) else r.ticker
            st = 'planned'
            if n_open >= SLOTS: st = 'skipped_full'
            elif inds.count(ind) >= MAX_IND: st = 'skipped_industry'
            elif r.ticker in held: st = 'skipped_holding'
            if st == 'planned': n_open += 1; inds.append(ind)
            plan.append(dict(signal_date=last, ticker=r.ticker, industry=r.industry, rsi14=r.rsi14, source=r.source,
                             status=st, weight=1 / SLOTS, amount=nav_prev / SLOTS if st == 'planned' else np.nan,
                             signal_close=cl.at[last, r.ticker]))
    tr = pd.concat([tr, pd.DataFrame(plan)], ignore_index=True) if plan else tr
    nav = pd.DataFrame(nav_hist)
    v = pd.read_parquet(cfg['paths']['vnindex']).sort_values('date').set_index('date').close
    nav['vnindex_rel'] = [v.asof(d) / v.asof(pd.Timestamp(dates[0])) for d in nav.date]
    st = Path(cfg['paths']['state'])
    tr.to_csv(st / 'paper_trades.csv', index=False); nav.to_csv(st / 'paper_nav.csv', index=False)
    return dict(nav=float(nav.nav.iloc[-1]), vnindex=float(nav.vnindex_rel.iloc[-1]), n_open=len(pos),
                planned=sum(p['status'] == 'planned' for p in plan),
                due_next=int(sum(p['exit_i'] == i_last + 1 for p in pos)))
