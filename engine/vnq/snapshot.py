"""Snapshot dự báo hằng ngày → quyết toán thực tế sau 5 phiên → chấm điểm live.

Mỗi ngày dữ liệu t ghi MỘT dòng cho mọi mã đủ điều kiện (dự báo chốt tại t, không sửa về sau):
  TN07: p_up_5, p_lr, rank_all, tn07_pick (nằm trong top 10 đã chọn)
  TN06-R (docs/TN06R_spec.md): tn06r_regime_on, tn06r_signal (sự kiện capitulation khi tầng 1 BẬT)
Khi có đủ open t+1 → close t+5: điền real/net/y_bin. Chấm điểm theo ngày ở state/live_eval.csv.
Nguồn 'backfill' = dòng dựng lại cho ngày đã qua bằng model/spec đã đóng băng; 'live' = ghi đúng ngày chạy.
"""
import pandas as pd, numpy as np
from pathlib import Path
from .backtest import net, realized

H = 5
PRED_COLS = ['data_date', 'ticker', 'source', 'model_version', 'industry', 'close', 'p_up_5', 'p_lr', 'rank_all', 'value_top30',
             'value_score', 'regime', 'trend_score', 'tn07_pick', 'rsi14', 'vol_ratio20', 'tn06r_regime_on', 'tn06r_signal']
DESC_COLS = ['industry', 'value_score', 'regime', 'trend_score']   # mô tả trạng thái tại t (không phải dự báo) → được điền bổ sung
ACT_COLS = ['status', 'real', 'net', 'y_bin', 'settled_on']


def _path(cfg): return Path(cfg['paths']['state']) / 'predictions_log.parquet'


def load(cfg):
    p = _path(cfg)
    return pd.read_parquet(p) if p.exists() else pd.DataFrame(columns=PRED_COLS + ACT_COLS)


def tn06r_flags(cfg, sc):
    """Điều kiện TN06-R tại mỗi (ticker, date) chỉ dùng dữ liệu ≤ t."""
    v = pd.read_parquet(cfg['paths']['vnindex']).sort_values('date')
    v['regime_on'] = v.close < v.close.ewm(span=50, adjust=False, min_periods=50).mean()
    s = sc.sort_values(['ticker', 'date']).copy()
    dates = np.sort(s.date.unique()); di = pd.Series(np.arange(len(dates)), index=dates)
    s['di'] = s.date.map(di)
    g = s.groupby('ticker')
    for k in (1, 2):
        s[f'_r{k}'] = g.rsi14.shift(k).where(g.di.shift(k) == s.di - k)
    cap = (s.rsi14 < 30) & (s._r1 < 30) & (s._r2 < 30) & (s.vol_ratio20 >= 1.5)
    s = s.merge(v[['date', 'regime_on']], on='date', how='left')
    s['tn06r_regime_on'] = s.regime_on.fillna(False).astype(bool)
    s['tn06r_cond'] = cap.values & s.tn06r_regime_on
    return s.drop(columns=['_r1', '_r2', 'regime_on'])


def _dedupe(flags, prior):
    """Bỏ tín hiệu nếu cùng mã đã có tín hiệu trong 5 phiên trước (kể cả trong log đã ghi)."""
    last = {} if prior is None or prior.empty else \
        prior[prior.tn06r_signal.astype(bool)].groupby('ticker').di.max().to_dict()
    out = []
    for r in flags.sort_values('date').itertuples():
        ok = bool(r.tn06r_cond) and not (r.ticker in last and r.di - last[r.ticker] <= H)
        if ok: last[r.ticker] = r.di
        out.append(ok)
    return pd.Series(out, index=flags.sort_values('date').index).reindex(flags.index)


def record(cfg, sc, picks_by_date, source, quarantine=()):
    """Ghi snapshot cho các ngày trong picks_by_date ({date: set(ticker top10)}). Ngày đã có thì giữ nguyên (không sửa dự báo)."""
    log = load(cfg)
    have = set(pd.to_datetime(log.data_date).unique()) if len(log) else set()
    want = [d for d in sorted(picks_by_date) if pd.Timestamp(d) not in have]
    if not want: return log, 0
    f = tn06r_flags(cfg, sc)
    dates = np.sort(f.date.unique()); di = pd.Series(np.arange(len(dates)), index=dates)
    prior = None
    if len(log):
        prior = log[['data_date', 'ticker', 'tn06r_signal']].rename(columns={'data_date': 'date'})
        prior['di'] = pd.to_datetime(prior.date).map(di)
    f = f[f.date.isin(want)].copy()
    f['tn06r_signal'] = _dedupe(f, prior) & ~f.ticker.isin(quarantine)
    f['rank_all'] = f.groupby('date').p_up_5.rank(ascending=False, method='min').astype(int)
    f['tn07_pick'] = [t in picks_by_date[d] for t, d in zip(f.ticker, f.date)]
    f = f.rename(columns={'date': 'data_date'}).assign(source=source, model_version=cfg['model_version'], status='open')
    new = f[PRED_COLS + ['status']].reindex(columns=PRED_COLS + ACT_COLS)
    log = pd.concat([log, new], ignore_index=True) if len(log) else new
    log.to_parquet(_path(cfg), index=False)
    return log, len(want)


def fill_descriptive(cfg, sc):
    """Điền cột mô tả (ngành/regime/trend/value tại t) cho dòng snapshot cũ còn thiếu. Không đụng cột dự báo."""
    log = load(cfg)
    if log.empty: return 0
    for c in DESC_COLS:
        if c not in log: log[c] = np.nan
    miss = log.regime.isna()
    if not miss.any(): return 0
    src = sc[['ticker', 'date'] + DESC_COLS].rename(columns={'date': 'data_date'})
    key = pd.MultiIndex.from_arrays([log.ticker, pd.to_datetime(log.data_date)])
    src = src.set_index(['ticker', 'data_date'])
    ok = miss.values & key.isin(src.index)
    for c in DESC_COLS:
        log[c] = log[c].astype(object) if c in ('industry', 'regime') else log[c]
        log.loc[ok, c] = src.loc[key[ok], c].values
    log = log.reindex(columns=PRED_COLS + ACT_COLS)
    log.to_parquet(_path(cfg), index=False)
    (Path(cfg['paths']['state']) / 'predictions_full_push').touch()
    return int(ok.sum())


def settle(cfg, e):
    """Điền thực tế cho dòng 'open' khi đã có close t+5 (kẹt sàn t+5 → close t+6, như backtest)."""
    log = load(cfg)
    if log.empty: return log
    d = e.dropna(subset=['fwd_ret_5']).copy(); d['real'] = realized(d)
    d = d.set_index(['ticker', 'date'])
    idx = pd.MultiIndex.from_arrays([log.ticker, pd.to_datetime(log.data_date)])
    hit = (log.status == 'open').values & idx.isin(d.index)
    if hit.any():
        log['settled_on'] = log.settled_on.astype(object)
        x = d.loc[idx[hit]]
        ceiling = (x.open_gap_t1 >= x.limit - 0.005).values
        log.loc[hit, 'real'] = x.real.values
        log.loc[hit, 'net'] = net(x.real, cfg['costs']).values
        log.loc[hit, 'y_bin'] = x.y_bin.values
        log.loc[hit, 'status'] = np.where(ceiling, 'unfilled_ceiling', 'settled')
        log.loc[hit, 'settled_on'] = e.date.max().strftime('%Y-%m-%d')
    log.to_parquet(_path(cfg), index=False)
    return log


def evaluate(cfg, log):
    """Chấm theo ngày dự báo (đã quyết toán). Random = kỳ vọng bốc ngẫu nhiên cùng pool = trung bình pool."""
    s = log[log.status.isin(['settled', 'unfilled_ceiling'])].copy()
    if s.empty: return pd.DataFrame()
    s['data_date'] = pd.to_datetime(s.data_date)
    for c in ('net', 'y_bin', 'p_up_5', 'real'): s[c] = s[c].astype(float)
    filled = s[s.status == 'settled']
    rows = []
    for d, g in s.groupby('data_date'):
        f = filled[filled.data_date == d]
        pool = f[f.value_top30.astype(bool)]
        pk = f[f.tn07_pick.astype(bool)]
        tn6 = f[f.tn06r_signal.astype(bool)]
        q = f.p_up_5.rank(pct=True)
        rows.append(dict(
            data_date=d.strftime('%Y-%m-%d'), source=g.source.iloc[0], model_version=g.model_version.iloc[0],
            n=len(f), ic=float(f.p_up_5.rank().corr(f.real.rank())) if len(f) > 5 else None,
            market_net=f.net.mean(), pool_net=pool.net.mean() if len(pool) else None,
            tn07_n=len(pk), tn07_net=pk.net.mean() if len(pk) else None, tn07_hit=pk.y_bin.mean() if len(pk) else None,
            pool_hit=pool.y_bin.mean() if len(pool) else None,
            pred_mean=float(pk.p_up_5.mean()) if len(pk) else None,   # calibration: dự báo TB vs hit thực tế của top 10
            top_decile_net=f[q > 0.9].net.mean(), bottom_decile_net=f[q <= 0.1].net.mean(),
            tn06r_regime_on=bool(g.tn06r_regime_on.astype(bool).iloc[0]), tn06r_n=len(tn6),
            tn06r_net=tn6.net.mean() if len(tn6) else None))
    ev = pd.DataFrame(rows)
    ev.to_csv(Path(cfg['paths']['state']) / 'live_eval.csv', index=False)
    return ev


def summary(ev):
    """Tổng hợp: mỗi hệ so với thị trường (EW) và random (TB pool); chỉ tính ngày có lệnh."""
    if ev is None or ev.empty: return None
    out = {}
    for src in ('live', 'all'):
        e = ev if src == 'all' else ev[ev.source == 'live']
        if e.empty: continue
        a = e.dropna(subset=['tn07_net'])
        b = e[e.tn06r_n > 0]
        out[src] = dict(days=len(e), ic_mean=float(e.ic.mean()), ic_pos_days=float((e.ic > 0).mean()),
                        tn07_net=float(a.tn07_net.mean()), tn07_vs_market=float((a.tn07_net - a.market_net).mean()),
                        tn07_vs_random=float((a.tn07_net - a.pool_net).mean()), tn07_hit=float(a.tn07_hit.mean()),
                        tn07_pred_mean=float(a.pred_mean.mean()),
                        tn06r_trades=int(b.tn06r_n.sum()),
                        tn06r_net=float(np.average(b.tn06r_net, weights=b.tn06r_n)) if len(b) else None,
                        tn06r_vs_market=float(np.average(b.tn06r_net - b.market_net, weights=b.tn06r_n)) if len(b) else None)
    return out
