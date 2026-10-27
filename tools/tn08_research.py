"""TN08 — chọn biến thể bằng walk-forward CHỈ trong giai đoạn train (2025-01-01 → 2026-06-30).

Không đọc / không chấm bất kỳ ngày nào >= ledger.test_start. Ledger giữ nguyên (horizon, topk,
value_top_pct, max_per_industry, chi phí, universe). Biến thể theo docs/TN07_bien_ban_kiem_dinh.md mục 6:
  V0  tn07 tái lập: LightGBM, y_bin (ATR), lọc value top 30% rồi xếp p
  V1  (a) target cross-sectional: y = fwd_ret_5 thuộc top 30% trong ngày
  V2  (a) bỏ feature thị trường (vni_*, breadth_ema50)
  V3  (a) cả hai: target cross-sectional + bỏ feature thị trường
  V4  (b) ML trên toàn universe, value làm ràng buộc mềm: score = 0.75·rank(p) + 0.25·rank(value_score)
  V5  (b) + (a): V4 dùng model V1
  V6  logistic (baseline TN07 nhưng làm chiến lược chính)

Mốc so sánh mỗi ngày (cùng chi phí): bốc ngẫu nhiên cùng số mã từ cùng pool (200 lần), thị trường
equal-weight toàn universe, và luật đơn giản R1–R3 (momentum 20 phiên, trend_score, value_score).
Luật chọn (ghi trước khi chạy): biến thể ML có IC TB > 0, thắng random VÀ thắng thị trường ở >= 3/4 fold,
và vs_market TB cao hơn luật đơn giản tốt nhất → chọn vs_market TB cao nhất. Không có biến thể nào đạt → không train TN08.
Mọi kết quả ghi vào tools/out/tn08/experiments.csv (để đẩy lên bảng experiments).
"""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path
import numpy as np, pandas as pd, yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from vnq import features as F  # noqa: E402
from vnq.backtest import pick, net, realized  # noqa: E402
from vnq.model import LGB_GRID, fit_lgb, daily_ic, _purge_end  # noqa: E402
import lightgbm as lgb  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.impute import SimpleImputer  # noqa: E402
warnings.filterwarnings('ignore')

RNG = np.random.default_rng(7)
MARKET = ['vni_ret5', 'vni_ret20', 'vni_dist_ema50', 'breadth_ema50']
OUT = ROOT / 'tools' / 'out' / 'tn08'


def load(cfg):
    panel = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'engine/data/seed/panel.parquet')
    vni = sys.argv[2] if len(sys.argv) > 2 else str(ROOT / 'engine/data/seed/vnindex.parquet')
    cfg['paths']['industry'] = str(ROOT / 'engine/data/seed/industry.csv')
    cfg['paths']['exchange_map'] = str(ROOT / 'engine/data/seed/__none__.csv')
    test_start = pd.Timestamp(cfg['ledger']['test_start'])
    p = pd.read_parquet(panel); v = pd.read_parquet(vni)
    # Nhãn h=5 của ngày cuối train cần 6 phiên sau → giữ tối đa 10 phiên sau train_end, rồi bỏ mọi hàng >= test_start.
    keep = pd.Timestamp(cfg['ledger']['train_end']) + pd.Timedelta(days=16)
    e = F.build(cfg, p[p.date <= keep], v[v.date <= keep])
    e = e[e.date < test_start].copy()
    e['y_xs'] = e.groupby('date').fwd_ret_5.rank(pct=True).ge(0.7).astype(float)
    e.loc[e.fwd_ret_5.isna(), 'y_xs'] = np.nan
    return e


def fit_lgb_y(tr, c, feats, y):
    m = lgb.LGBMClassifier(**c, subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, random_state=7, verbose=-1)
    m.fit(tr[feats], tr[y].astype(int)); return m


def fit_lr(tr, feats, y):
    m = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    m.fit(tr[feats].clip(-50, 50), tr[y].astype(int)); return m


def strat(va, col, cfg, soft_value=False):
    L, C = cfg['ledger'], cfg['costs']
    d = va.dropna(subset=['fwd_ret_5']).copy(); d['real'] = realized(d)
    if soft_value:
        g = d.groupby('date')
        d['_s'] = 0.75 * g[col].rank(pct=True) + 0.25 * g.value_score.rank(pct=True)
        d['value_top30'] = True; col = '_s'
    rows = []
    for dt_, g in d.groupby('date'):
        sel = pick(g, col, L['topk'], L['max_per_industry'])
        if sel.empty: continue
        s = sel[~(sel.open_gap_t1 >= sel.limit - 0.005)]
        if s.empty: continue
        # benchmark ngẫu nhiên: bốc len(s) mã từ CÙNG pool (sau lọc gap trần), 200 lần
        pool = g[g.value_top30 & ~(g.open_gap_t1 >= g.limit - 0.005)]
        rn = net(pool.real, C).values
        rand = float(np.mean([rn[RNG.choice(len(rn), min(len(s), len(rn)), replace=False)].mean() for _ in range(200)]))
        rows.append(dict(net=net(s.real, C).mean(), univ=net(g.real, C).mean(), rand=rand, hit=s.y_bin.mean(),
                         base=g[g.value_top30].y_bin.mean(), mkt_up=bool(g.vni_dist_ema50.iloc[0] > 0)))
    r = pd.DataFrame(rows)
    timed = np.where(r.mkt_up, r.net, 0.0)   # 'khi nào mua': chỉ vào lệnh khi VNINDEX trên EMA50, còn lại giữ tiền
    return dict(net=float(r.net.mean()), vs_random=float((r.net - r.rand).mean()), vs_market=float((r.net - r.univ).mean()),
                net_timed=float(timed.mean()), market_ew=float(r.univ.mean()), random=float(r.rand.mean()),
                lift=float((r.hit - r.base).mean()), ic=float(daily_ic(d, col).mean()), n_days=len(r), pct_mkt_up=float(r.mkt_up.mean()))


VARIANTS = {
    'V0_tn07':        dict(y='y_bin', drop_mkt=False, soft=False, algo='lgb'),
    'V1_xs_target':   dict(y='y_xs',  drop_mkt=False, soft=False, algo='lgb'),
    'V2_no_market':   dict(y='y_bin', drop_mkt=True,  soft=False, algo='lgb'),
    'V3_xs_no_mkt':   dict(y='y_xs',  drop_mkt=True,  soft=False, algo='lgb'),
    'V4_soft_value':  dict(y='y_bin', drop_mkt=False, soft=True,  algo='lgb'),
    'V5_soft_xs':     dict(y='y_xs',  drop_mkt=False, soft=True,  algo='lgb'),
    'V6_logistic':    dict(y='y_bin', drop_mkt=False, soft=False, algo='lr'),
    # luật đơn giản không ML — mốc so sánh 'logic khác'
    'R1_momentum20':  dict(y='y_bin', drop_mkt=False, soft=False, algo='rule', col='ret20'),
    'R2_trend_score': dict(y='y_bin', drop_mkt=False, soft=False, algo='rule', col='trend_score'),
    'R3_lowvol_value': dict(y='y_bin', drop_mkt=False, soft=False, algo='rule', col='value_score'),
}


def main():
    from vnq.config import load as load_cfg
    cfg = load_cfg(str(ROOT / 'engine/config.yaml'))
    L, h = cfg['ledger'], cfg['ledger']['horizon']
    e = load(cfg)
    print(f'rows={len(e)} dates {e.date.min():%Y-%m-%d}→{e.date.max():%Y-%m-%d} (test_start {L["test_start"]} bị loại)')
    dates = np.sort(e.date.unique())
    logs = []
    for name, V in VARIANTS.items():
        feats = [f for f in F.FEATURES if not (V['drop_mkt'] and f in MARKET)]
        lab = e.dropna(subset=[V['y']])
        for fi, (vs, ve) in enumerate(L['wf_folds']):
            tr = lab[(lab.date >= L['train_start']) & (lab.date <= _purge_end(dates, pd.Timestamp(vs) - pd.Timedelta(days=1), h))]
            va = e[(e.date >= vs) & (e.date <= _purge_end(dates, ve, h))].copy()
            if V['algo'] == 'rule':
                va['p'] = va[V['col']]; best = 'rule'
            elif V['algo'] == 'lr':
                cands = [('C=0.1', fit_lr(tr, feats, V['y']))]
                va['p'] = cands[0][1].predict_proba(va[feats].clip(-50, 50))[:, 1]
                best = cands[0][0]
            else:
                # chọn cấu hình LGB trong fold bằng IC trên chính fold đó = như tn07 (grid nhỏ, cố định)
                best, bic = None, -9
                for ci, c in enumerate(LGB_GRID):
                    p = fit_lgb_y(tr, c, feats, V['y']).predict_proba(va[feats])[:, 1]
                    ic = daily_ic(va.assign(p=p), 'p').mean()
                    if ic > bic: best, bic, bp = f'lgb{ci}', ic, p
                va['p'] = bp
            m = strat(va, 'p', cfg, soft_value=V['soft'])
            logs.append(dict(version='tn08-research', variant=name, fold=fi + 1, model=best, cfg=json.dumps(V),
                             n_train=len(tr), n_val=len(va), **m))
            print(f'{name:15s} f{fi+1} {best:6s} net={m["net"]:+.4f} vsRand={m["vs_random"]:+.4f} vsMkt={m["vs_market"]:+.4f} IC={m["ic"]:+.4f}', flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(logs); df.to_csv(OUT / 'experiments.csv', index=False)
    s = df.groupby('variant').agg(net=('net', 'mean'), net_timed=('net_timed', 'mean'), vs_random=('vs_random', 'mean'),
                                  vs_market=('vs_market', 'mean'), ic=('ic', 'mean'), lift=('lift', 'mean'),
                                  folds_beat_rand=('vs_random', lambda x: int((x > 0).sum())),
                                  folds_beat_mkt=('vs_market', lambda x: int((x > 0).sum())))
    s['eligible'] = (s.ic > 0) & (s.folds_beat_rand >= 3) & (s.folds_beat_mkt >= 3) & ~s.index.str.startswith('R')
    print(s.round(4).sort_values('vs_market', ascending=False).to_string())
    rules_best = s[s.index.str.startswith('R')].vs_market.max()
    el = s[s.eligible & (s.vs_market > rules_best)]   # phải thắng cả luật đơn giản tốt nhất
    choice = el.vs_market.idxmax() if len(el) else None
    print('CHOICE', choice)
    s.to_csv(OUT / 'summary.csv'); (OUT / 'choice.txt').write_text(str(choice))


if __name__ == '__main__':
    main()
