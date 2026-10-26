"""Train (walk-forward chọn config + fit cuối 1 lần) và nạp model đóng băng.
Nguyên tắc: một version đã train thì KHÔNG train đè. Mọi config thử đều ghi vào state/experiments.csv."""
import pandas as pd, numpy as np, json, joblib, datetime as dt, warnings
from pathlib import Path
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from .features import FEATURES
from .config import ledger_hash
warnings.filterwarnings('ignore')

LGB_GRID = [dict(num_leaves=15, learning_rate=0.03, n_estimators=300, min_child_samples=200),
            dict(num_leaves=31, learning_rate=0.03, n_estimators=300, min_child_samples=200),
            dict(num_leaves=15, learning_rate=0.02, n_estimators=600, min_child_samples=400),
            dict(num_leaves=7, learning_rate=0.03, n_estimators=400, min_child_samples=300)]
COMMON = dict(subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=5.0, random_state=7, verbose=-1)


def _purge_end(dates, end, h):
    return dates[np.searchsorted(dates, np.datetime64(pd.Timestamp(end)), side='right') - 1 - h]


def daily_ic(d, col):
    x = d.dropna(subset=['fwd_ret_5'])
    return x.groupby('date').apply(lambda g: g[col].rank().corr(g.fwd_ret_5.rank()) if len(g) > 5 else np.nan).dropna()


def fit_lgb(tr, cfg):
    m = lgb.LGBMClassifier(**cfg, **COMMON); m.fit(tr[FEATURES], tr.y_bin.astype(int)); return m


def fit_lr(tr):
    m = make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    m.fit(tr[FEATURES].clip(-50, 50), tr.y_bin.astype(int)); return m


def train(cfg, e, version, note=''):
    L, h = cfg['ledger'], cfg['ledger']['horizon']
    mdir = Path(cfg['paths']['models']) / version
    if (mdir / 'manifest.json').exists():
        raise SystemExit(f'Model {version} đã tồn tại và đã đóng băng. Đặt version mới để train lại.')
    dates = np.sort(e.date.unique())
    lab = e.dropna(subset=['y_bin'])
    logs, ics = [], {}
    for fi, (vs, ve) in enumerate(L['wf_folds']):
        tr = lab[(lab.date >= L['train_start']) & (lab.date <= _purge_end(dates, pd.Timestamp(vs) - pd.Timedelta(days=1), h))]
        va = lab[(lab.date >= vs) & (lab.date <= _purge_end(dates, ve, h))].copy()
        for ci, c in enumerate(LGB_GRID):
            va['p'] = fit_lgb(tr, c).predict_proba(va[FEATURES])[:, 1]
            ic = daily_ic(va, 'p').mean(); ics.setdefault(ci, []).append(ic)
            logs.append(dict(version=version, fold=fi+1, model=f'lgb{ci}', cfg=json.dumps(c), ic_mean=ic, n_train=len(tr), n_val=len(va)))
        va['p'] = fit_lr(tr).predict_proba(va[FEATURES].clip(-50, 50))[:, 1]
        logs.append(dict(version=version, fold=fi+1, model='logreg', cfg='C=0.1', ic_mean=daily_ic(va, 'p').mean(), n_train=len(tr), n_val=len(va)))
    bi = max(ics, key=lambda k: np.mean(ics[k]))
    tr = lab[(lab.date >= L['train_start']) & (lab.date <= _purge_end(dates, L['train_end'], h))]
    m_lgb, m_lr = fit_lgb(tr, LGB_GRID[bi]), fit_lr(tr)
    mdir.mkdir(parents=True)
    m_lgb.booster_.save_model(str(mdir / 'lgb.txt'))
    joblib.dump(m_lr, mdir / 'logreg.joblib')
    man = dict(version=version, created=dt.datetime.now().isoformat(timespec='seconds'), ledger_hash=ledger_hash(cfg),
               best=f'lgb{bi}', lgb_params={**LGB_GRID[bi], **COMMON}, features=FEATURES,
               train_start=L['train_start'], train_end=L['train_end'],
               train_end_effective=str(_purge_end(dates, L['train_end'], h))[:10], n_train=len(tr),
               wf_ic={f'lgb{k}': float(np.mean(v)) for k, v in ics.items()}, note=note)
    json.dump(man, open(mdir / 'manifest.json', 'w'), indent=1, ensure_ascii=False)
    exp = Path(cfg['paths']['state']) / 'experiments.csv'
    pd.DataFrame(logs).to_csv(exp, mode='a', header=not exp.exists(), index=False)
    pd.DataFrame(logs).to_csv(mdir / 'walkforward_log.csv', index=False)
    return man


class Frozen:
    def __init__(self, cfg, version=None):
        version = version or cfg['model_version']
        self.dir = Path(cfg['paths']['models']) / version
        self.man = json.load(open(self.dir / 'manifest.json', encoding='utf-8'))
        if self.man['ledger_hash'] != ledger_hash(cfg):
            raise SystemExit(f"config.yaml (ledger/universe) đã đổi so với lúc train {version}. "
                             'Khôi phục config hoặc train version mới — không dùng model cũ với ledger mới.')
        self.lgb = lgb.Booster(model_file=str(self.dir / 'lgb.txt'))
        self.lr = joblib.load(self.dir / 'logreg.joblib')

    def score(self, d):
        d = d.copy()
        d['p_up_5'] = self.lgb.predict(d[FEATURES])
        d['p_lr'] = self.lr.predict_proba(d[FEATURES].clip(-50, 50))[:, 1]
        return d
