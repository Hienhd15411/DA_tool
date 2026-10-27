"""TN08 — mở test MỘT lần cho biến thể đã chốt trước bằng walk-forward trong train.

Đã chốt (tools/out/tn08/choice.txt, commit trước khi chạy file này): V4_soft_value
  model: LightGBM lgb2 (cấu hình được chọn ở 3/4 fold của V4), target y_bin (ATR), đủ 36 feature
  chọn mã: score = 0.75·rank(p) + 0.25·rank(value_score) trên toàn universe, top 10, ≤3 mã/ngành
  bỏ mã gap trần ở open t+1; vào lệnh open t+1, bán close t+5; phí 2 chiều + thuế bán
  mua bao nhiêu: mỗi ngày giải ngân 1/5 vốn (giữ 5 phiên → 5 rổ chồng nhau), chia đều cho các mã trong rổ
Train: 2025-01-01 → train_end (purge 5 phiên). Test: từ ledger.test_start đến ngày có nhãn cuối.

So sánh (cùng chi phí, cùng ngày): bốc ngẫu nhiên (cùng số mã, cùng pool, 500 lần), thị trường
equal-weight toàn universe, VNINDEX (close t → close t+5), luật đơn giản R1 momentum20 / R2 trend_score
/ R3 value_score, và TN07 (V0). CI95 bằng block bootstrap như gate.
Dùng: python tools/tn08_test.py <panel.parquet> <vnindex.parquet>
"""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from vnq import features as F  # noqa: E402
from vnq.config import load as load_cfg  # noqa: E402
from vnq.backtest import pick, net, realized, block_boot  # noqa: E402
from vnq.model import LGB_GRID, daily_ic, _purge_end  # noqa: E402
import lightgbm as lgb  # noqa: E402
warnings.filterwarnings('ignore')
OUT = ROOT / 'tools' / 'out' / 'tn08'
RNG = np.random.default_rng(7)


def fit(tr, c):
    m = lgb.LGBMClassifier(**c, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, random_state=7, verbose=-1)
    m.fit(tr[F.FEATURES], tr.y_bin.astype(int)); return m


def daily(d, col, cfg, soft, vni5):
    L, C = cfg['ledger'], cfg['costs']
    d = d.copy()
    if soft:
        g = d.groupby('date')
        d['_s'] = 0.75 * g[col].rank(pct=True) + 0.25 * g.value_score.rank(pct=True)
        d['value_top30'] = True; col = '_s'
    rows, picks = [], []
    for dt_, g in d.groupby('date'):
        sel = pick(g, col, L['topk'], L['max_per_industry'])
        s = sel[~(sel.open_gap_t1 >= sel.limit - 0.005)] if len(sel) else sel
        if s.empty: continue
        pool = g[g.value_top30 & ~(g.open_gap_t1 >= g.limit - 0.005)]
        rn = net(pool.real, C).values
        rand = np.array([rn[RNG.choice(len(rn), min(len(s), len(rn)), replace=False)].mean() for _ in range(500)])
        nt = net(s.real, C).mean()
        rows.append(dict(date=dt_, n=len(s), net=nt, random=rand.mean(), rand_pctile=float((rand < nt).mean()),
                         market_ew=net(g.real, C).mean(), vnindex=vni5.get(dt_, np.nan), hit=s.y_bin.mean()))
        picks.append(s.assign(date=dt_)[['date', 'ticker', 'industry', 'real']])
    return pd.DataFrame(rows), pd.concat(picks) if picks else pd.DataFrame()


def summarize(r, G):
    out = {'n_days': len(r), 'net_per_trade': r.net.mean(), 'hit': r.hit.mean(),
           'random_pctile_avg': r.rand_pctile.mean(),
           # mua bao nhiêu: 1/5 vốn mỗi ngày → lợi nhuận danh mục mỗi ngày ≈ trung bình 5 rổ đang giữ / 5 phiên
           'portfolio_cum': float(np.prod(1 + r.net.values / 5) - 1)}
    for b in ['random', 'market_ew', 'vnindex']:
        x = (r.net - r[b]).dropna().values
        out[f'vs_{b}'] = float(x.mean()); out[f'vs_{b}_ci'] = block_boot(x, G['bootstrap'], G['block'])
        out[f'vs_{b}_win_days'] = float((x > 0).mean())
        out[f'{b}_cum'] = float(np.prod(1 + r[b].dropna().values / 5) - 1)
    return out


def main():
    cfg = load_cfg(str(ROOT / 'engine/config.yaml'))
    cfg['paths']['industry'] = str(ROOT / 'engine/data/seed/industry.csv')
    L, G, h = cfg['ledger'], cfg['gate'], cfg['ledger']['horizon']
    p, v = pd.read_parquet(sys.argv[1]), pd.read_parquet(sys.argv[2])
    e = F.build(cfg, p, v)
    dates = np.sort(e.date.unique())
    tr = e.dropna(subset=['y_bin'])
    tr = tr[(tr.date >= L['train_start']) & (tr.date <= _purge_end(dates, L['train_end'], h))]
    te = e[e.date >= L['test_start']].dropna(subset=['fwd_ret_5']).copy(); te['real'] = realized(te)
    vs = v.sort_values('date').set_index('date').close
    vni5 = (vs.shift(-h) / vs - 1).to_dict()
    print(f'train {tr.date.min():%Y-%m-%d}→{tr.date.max():%Y-%m-%d} n={len(tr)} | test {te.date.min():%Y-%m-%d}→{te.date.max():%Y-%m-%d} days={te.date.nunique()}')
    # V4 và V0 dùng cùng model; khác nhau ở cách chọn mã (V0 = lọc value top 30% cứng như TN07)
    te['p'] = fit(tr, LGB_GRID[2]).predict_proba(te[F.FEATURES])[:, 1]
    strategies = {'TN08_V4_soft_value': ('p', True), 'TN07_style_V0': ('p', False),
                  'R1_momentum20': ('ret20', False), 'R2_trend_score': ('trend_score', False), 'R3_value_score': ('value_score', False)}
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for nm, (col, soft) in strategies.items():
        r, pk = daily(te, col, cfg, soft, vni5)
        res[nm] = {k: (round(x, 5) if isinstance(x, float) else x) for k, x in summarize(r, G).items()}
        res[nm]['ic'] = round(float(daily_ic(te, col).mean()), 4)
        r.to_csv(OUT / f'test_daily_{nm}.csv', index=False)
        if nm.startswith('TN08'): pk.to_csv(OUT / 'test_picks_tn08.csv', index=False)
        print(nm, json.dumps(res[nm], default=str), flush=True)
    json.dump(res, open(OUT / 'test_summary.json', 'w'), indent=1, default=str)
    t = pd.DataFrame(res).T[['n_days', 'net_per_trade', 'vs_random', 'vs_random_ci', 'vs_market_ew', 'vs_market_ew_ci',
                              'vs_vnindex', 'portfolio_cum', 'market_ew_cum', 'vnindex_cum', 'random_pctile_avg', 'ic']]
    print(t.to_string())


if __name__ == '__main__':
    main()
