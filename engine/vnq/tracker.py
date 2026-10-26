"""Nhật ký tín hiệu (paper trading): ghi top-K mỗi ngày, tự quyết toán khi đủ 5 phiên."""
import pandas as pd, numpy as np
from pathlib import Path
from .backtest import net, realized

COLS = ['data_date', 'ticker', 'rank_pool', 'p_up_5', 'value_score', 'trend_score', 'regime', 'action', 'reasons',
        'gate_pass', 'model_version', 'status', 'entry_date_est', 'gross', 'net', 'y_bin', 'univ_mean', 'excess']


def _path(cfg): return Path(cfg['paths']['state']) / 'signals_log.csv'


def load(cfg):
    p = _path(cfg)
    if p.exists():
        d = pd.read_csv(p, parse_dates=['data_date'])
        return d
    return pd.DataFrame(columns=COLS)


def append(cfg, sel, data_date, gate_pass):
    log = load(cfg)
    log = log[log.data_date != pd.Timestamp(data_date)]  # chạy lại cùng ngày thì ghi đè
    new = sel.assign(data_date=pd.Timestamp(data_date), gate_pass=gate_pass, model_version=cfg['model_version'],
                     status='open')[[c for c in COLS if c in sel.columns or c in ('data_date', 'gate_pass', 'model_version', 'status')]]
    log = pd.concat([log, new], ignore_index=True).reindex(columns=COLS)
    log.to_csv(_path(cfg), index=False)
    return log


def settle(cfg, e):
    log = load(cfg)
    if log.empty: return log
    d = e.dropna(subset=['fwd_ret_5']).copy(); d['real'] = realized(d)
    univ = d.groupby('date').fwd_ret_5.mean()
    key = d.set_index(['ticker', 'date'])
    for i, r in log[log.status == 'open'].iterrows():
        k = (r.ticker, pd.Timestamp(r.data_date))
        if k not in key.index: continue
        x = key.loc[k]
        if x.open_gap_t1 >= x.limit-0.005:
            log.loc[i, 'status'] = 'unfilled_ceiling'; continue
        log.loc[i, ['status', 'gross', 'net', 'y_bin', 'univ_mean']] = ['settled', x.real, net(x.real, cfg['costs']), x.y_bin, univ.get(k[1], np.nan)]
        log.loc[i, 'excess'] = log.loc[i, 'net'] - log.loc[i, 'univ_mean']
    log.to_csv(_path(cfg), index=False)
    return log


def summary(log):
    s = log[log.status == 'settled']
    if s.empty: return None
    for c in ('net', 'y_bin', 'excess'): s[c] = s[c].astype(float)
    by = s.groupby('action').agg(n=('net', 'size'), hit=('y_bin', 'mean'), net=('net', 'mean'), excess=('excess', 'mean'))
    return dict(n=len(s), days=s.data_date.nunique(), hit=s.y_bin.mean(), net=s.net.mean(), excess=s.excess.mean(),
                by_action=by.reset_index().to_dict('records'), open=int((log.status == 'open').sum()))
