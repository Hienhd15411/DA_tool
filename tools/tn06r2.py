"""TN06-R2 — TN06-R + chốt lời sớm (docs/TN06R_spec.md, mục TN06-R2; đăng ký trước).

Dùng: python tools/tn06r2.py <panel.parquet> <vnindex.parquet>
Chọn TP trên IS bằng luật cố định, rồi chấm OOS một lần. In kết quả + ghi tools/out/tn06r2/summary.json.
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT.parent / 'engine'))
import tn06r as R  # noqa: E402
from vnq.config import load as load_cfg  # noqa: E402
from vnq.backtest import net  # noqa: E402

TP_GRID = [0.02, 0.03, 0.05, 0.08]
OUT = ROOT / 'out' / 'tn06r2'


def with_tp(ev, tp, O, Hh, C, cfg):
    """Lãi sau phí khi đặt LO chốt lời TP; chỉ bán được từ phiên t+3 (T+2). Không chạm → giữ tới ATC t+5 (realized)."""
    ev = ev.copy(); gross, held, hit = [], [], []
    for r in ev.itertuples():
        i, tk = int(r.di), r.ticker
        entry = O[i + 1, tk]; target = entry * (1 + tp); g, h, k = r.real, R.H, False
        for d in (i + 3, i + 4, i + 5):
            if d >= len(O.index): break
            o, hi = O[d, tk], Hh[d, tk]
            if np.isfinite(o) and o >= target: g, h, k = o / entry - 1, d - i, True; break
            if np.isfinite(hi) and hi >= target: g, h, k = tp, d - i, True; break
        gross.append(g); held.append(h); hit.append(k)
    ev['real'] = gross; ev['net'] = net(pd.Series(gross, index=ev.index), cfg['costs']); ev['held'] = held; ev['tp_hit'] = hit
    return ev


class Grid:
    """Truy cập giá theo (chỉ số phiên, mã)."""
    def __init__(self, df): self.df, self.index = df, df.index
    def __getitem__(self, k):
        i, tk = k
        try: return float(self.df.iat[i, self.df.columns.get_loc(tk)])
        except (IndexError, KeyError): return np.nan


def summarize(ev, b, G):
    s = R.stats(ev, b, G)
    if len(ev):
        s.update(tp_hit_rate=round(float(np.mean(ev.tp_hit)), 3) if 'tp_hit' in ev else 0.0,
                 avg_held_sessions=round(float(np.mean(ev.held)), 2) if 'held' in ev else float(R.H))
    return s


def main():
    cfg = load_cfg(str(ROOT.parent / 'engine/config.yaml'))
    cfg['paths']['industry'] = str(ROOT.parent / 'engine/data/seed/industry.csv')
    G = cfg['gate']
    p, v = pd.read_parquet(sys.argv[1]), pd.read_parquet(sys.argv[2])
    e, v = R.prepare(cfg, p, v)
    dates = np.sort(p.date.unique())
    piv = lambda c: Grid(p.pivot(index='date', columns='ticker', values=c).reindex(dates))
    O, Hh, C = piv('open'), piv('high'), piv('close')
    res = {}
    for per, (a, b_) in {'IS': R.IS, 'OOS': (R.OOS_START, '2100-01-01')}.items():
        ep = e[(e.date >= a) & (e.date <= b_)]
        base = R.events(ep, 'cond_cap', True)
        res[per] = {'n_events': len(base)}
        variants = {'R1_no_tp': base.assign(held=R.H, tp_hit=False)} | {f'TP{int(t * 100)}': with_tp(base, t, O, Hh, C, cfg) for t in TP_GRID}
        for nm, ev in variants.items():
            bb = R.bench(ep, ev, cfg) if len(ev) else pd.DataFrame()
            res[per][nm] = summarize(ev, bb, G)
            print(per, nm, json.dumps(res[per][nm], ensure_ascii=False, default=str), flush=True)
        if per == 'IS':   # luật chọn cố định (spec): lãi TB/lệnh cao nhất và phải hơn R1 trên IS
            cands = {k: res['IS'][k]['net_per_trade'] for k in res['IS'] if k.startswith('TP')}
            best = max(cands, key=cands.get)
            choice = best if cands[best] > res['IS']['R1_no_tp']['net_per_trade'] else None
            res['choice'] = choice
            print('CHOICE (chọn trên IS):', choice, flush=True)
            if choice is None: break
    if res.get('choice'):
        o, r1 = res['OOS'][res['choice']], res['OOS']['R1_no_tp']
        n = o.get('n_trades', 0)
        checks = {'>=30 lệnh': n >= 30, 'lãi TB/lệnh > TN06-R': n > 0 and o['net_per_trade'] > r1['net_per_trade'],
                  'vs thị trường > 0': n > 0 and o['vs_market'] > 0}
        res['gate'] = dict(checks=checks, verdict='GO (thay TN06-R trong paper trading)' if all(checks.values()) else 'NO-GO')
        print('GATE', json.dumps(res['gate'], ensure_ascii=False))
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(OUT / 'summary.json', 'w'), indent=1, ensure_ascii=False, default=str)


if __name__ == '__main__':
    main()
