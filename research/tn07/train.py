"""TN07 — walk-forward 4 fold trong train, chọn config theo IC trung bình fold, fit 1 lần cuối, đánh giá test 1 lần."""
import pandas as pd, numpy as np, json, warnings, itertools
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from features import FEATURES
warnings.filterwarnings('ignore')

TRAIN_START, TRAIN_END, TEST_START = '2025-01-01', '2026-06-30', '2026-07-01'
FEE, TAX = 0.0015, 0.001   # phí môi giới/chiều GIẢ ĐỊNH 0.15% (CHƯA XÁC NHẬN), thuế bán 0.1%
TOPK, MAX_PER_IND = 10, 3
SEED = 7

e = pd.read_parquet('dataset.parquet')
panel_ind = pd.read_parquet('/mnt/user-data/uploads/panel.parquet', columns=['ticker', 'industry']).dropna().drop_duplicates('ticker', keep='last')
e = e.drop(columns=['industry'], errors='ignore').merge(panel_ind, on='ticker', how='left')
dates = np.sort(e.date.unique())
didx = {d: i for i, d in enumerate(dates)}
e['di'] = e.date.map(didx)

def purge_end(end):  # chỉ giữ mẫu có t+5 <= end (nhãn không chạm vùng sau)
    return dates[np.searchsorted(dates, np.datetime64(end), side='right') - 1 - 5]

FOLDS = [('2025-07-01', '2025-09-30'), ('2025-10-01', '2025-12-31'),
         ('2026-01-01', '2026-03-31'), ('2026-04-01', '2026-06-30')]

LGB_GRID = [dict(num_leaves=15, learning_rate=0.03, n_estimators=300, min_child_samples=200),
            dict(num_leaves=31, learning_rate=0.03, n_estimators=300, min_child_samples=200),
            dict(num_leaves=15, learning_rate=0.02, n_estimators=600, min_child_samples=400),
            dict(num_leaves=7, learning_rate=0.03, n_estimators=400, min_child_samples=300)]
COMMON = dict(subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, random_state=SEED, verbose=-1)

def fit_lgb(tr, cfg):
    m = lgb.LGBMClassifier(**cfg, **COMMON); m.fit(tr[FEATURES], tr.y_bin.astype(int)); return m

def fit_lr(tr):
    m = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    m.fit(tr[FEATURES].clip(-50, 50), tr.y_bin.astype(int)); return m

def pred(m, d, lr=False):
    X = d[FEATURES].clip(-50, 50) if lr else d[FEATURES]
    return m.predict_proba(X)[:, 1]

def daily_ic(d, col):
    x = d.dropna(subset=['fwd_ret_5'])
    return x.groupby('date').apply(lambda g: g[col].rank().corr(g.fwd_ret_5.rank()) if len(g) > 5 else np.nan).dropna()

lab = e.dropna(subset=['y_bin'])
log = []
oos = []
for fi, (vs, ve) in enumerate(FOLDS):
    tr = lab[(lab.date >= TRAIN_START) & (lab.date <= purge_end(pd.Timestamp(vs) - pd.Timedelta(days=1)))]
    va = lab[(lab.date >= vs) & (lab.date <= purge_end(ve))]
    va = va.copy()
    for ci, cfg in enumerate(LGB_GRID):
        va[f'p_lgb{ci}'] = pred(fit_lgb(tr, cfg), va)
        ic = daily_ic(va, f'p_lgb{ci}')
        log.append(dict(fold=fi+1, val=f'{vs}..{ve}', n_train=len(tr), n_val=len(va), model=f'lgb{ci}', cfg=json.dumps(cfg), ic_mean=ic.mean()))
    va['p_lr'] = pred(fit_lr(tr), va, lr=True)
    ic = daily_ic(va, 'p_lr')
    log.append(dict(fold=fi+1, val=f'{vs}..{ve}', n_train=len(tr), n_val=len(va), model='logreg', cfg='C=0.1', ic_mean=ic.mean()))
    va['fold'] = fi+1
    oos.append(va)
log = pd.DataFrame(log)
log.to_csv('out/config_log.csv', index=False)
summ = log.groupby('model').ic_mean.agg(['mean', 'std', 'min'])
print(log.pivot(index='model', columns='fold', values='ic_mean').round(4)); print(summ.round(4))
best = summ.drop('logreg')['mean'].idxmax(); bi = int(best[3:])
print('BEST', best, LGB_GRID[bi])
oos = pd.concat(oos)
oos['p_up_5'] = oos[f'p_lgb{bi}']
oos.to_parquet('out/oos_walkforward.parquet')

# ---- fit cuối 1 lần trên toàn train ----
tr = lab[(lab.date >= TRAIN_START) & (lab.date <= purge_end(TRAIN_END))]
m_lgb = fit_lgb(tr, LGB_GRID[bi]); m_lr = fit_lr(tr)
allp = e[e.date >= TEST_START].copy()
allp['p_up_5'] = pred(m_lgb, allp); allp['p_lr'] = pred(m_lr, allp, lr=True)
allp.to_parquet('out/test_scored.parquet')
fi_ = pd.DataFrame({'feature': FEATURES, 'gain': m_lgb.booster_.feature_importance('gain')}).sort_values('gain', ascending=False)
fi_.to_csv('out/feature_importance_tn07.csv', index=False)
json.dump(dict(best=best, cfg=LGB_GRID[bi], common=COMMON, n_train_final=len(tr), train_end_effective=str(purge_end(TRAIN_END))[:10],
               features=FEATURES, fee=FEE, tax=TAX, liq_min=5e9, topk=TOPK, max_per_ind=MAX_PER_IND), open('out/config_final.json', 'w'), indent=1, default=str)
print('train rows', len(tr), 'effective end', purge_end(TRAIN_END))
print(fi_.head(12))
