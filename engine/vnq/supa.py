"""Kết nối Supabase qua REST (không cần supabase-py): Storage để giữ dữ liệu/trạng thái giữa các lần chạy,
PostgREST để publish kết quả cho dashboard. Credential lấy từ biến môi trường:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY   (chỉ dùng ở server/GitHub Actions — KHÔNG đưa ra web)
  VNQ_BUCKET (mặc định vnq-data)
"""
import os, json, logging, math
from pathlib import Path
import requests
import pandas as pd
import numpy as np

log = logging.getLogger('vnq')

# file đồng bộ: đường dẫn local (tương đối engine/) -> key trong bucket
SYNC_FILES = {
    'data/panel.parquet': 'data/panel.parquet',
    'data/vnindex.parquet': 'data/vnindex.parquet',
    'data/industry.csv': 'data/industry.csv',
    'data/exchange_map.csv': 'data/exchange_map.csv',
    'state/signals_log.csv': 'state/signals_log.csv',
    'state/quarantine.json': 'state/quarantine.json',
    'state/gate.json': 'state/gate.json',
    'state/experiments.csv': 'state/experiments.csv',
    'state/predictions_log.parquet': 'state/predictions_log.parquet',
}


class Supa:
    def __init__(self, url=None, key=None, bucket=None):
        self.url = (url or os.environ['SUPABASE_URL']).rstrip('/')
        self.key = key or os.environ['SUPABASE_SERVICE_ROLE_KEY']
        self.bucket = bucket or os.environ.get('VNQ_BUCKET', 'vnq-data')
        self.h = {'apikey': self.key, 'Authorization': f'Bearer {self.key}'}

    # ---------- Storage ----------
    def download(self, key, dest):
        r = requests.get(f'{self.url}/storage/v1/object/{self.bucket}/{key}', headers=self.h, timeout=120)
        if r.status_code in (400, 404):
            return False
        r.raise_for_status()
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        Path(dest).write_bytes(r.content)
        return True

    def upload(self, src, key, content_type='application/octet-stream'):
        with open(src, 'rb') as f:
            r = requests.post(f'{self.url}/storage/v1/object/{self.bucket}/{key}', data=f.read(), timeout=300,
                              headers={**self.h, 'x-upsert': 'true', 'Content-Type': content_type})
        r.raise_for_status()

    def list(self, prefix):
        r = requests.post(f'{self.url}/storage/v1/object/list/{self.bucket}', headers=self.h, timeout=60,
                          json={'prefix': prefix, 'limit': 1000, 'sortBy': {'column': 'name', 'order': 'asc'}})
        r.raise_for_status()
        return [o['name'] for o in r.json() if o.get('id')]  # bỏ "folder"

    def move(self, src, dst):
        r = requests.post(f'{self.url}/storage/v1/object/move', headers=self.h, timeout=60,
                          json={'bucketId': self.bucket, 'sourceKey': src, 'destinationKey': dst})
        r.raise_for_status()

    # ---------- PostgREST ----------
    def upsert(self, table, rows, on_conflict):
        if not rows: return 0
        for i in range(0, len(rows), 500):
            r = requests.post(f'{self.url}/rest/v1/{table}', params={'on_conflict': on_conflict}, timeout=120,
                              headers={**self.h, 'Content-Type': 'application/json',
                                       'Prefer': 'resolution=merge-duplicates,return=minimal'},
                              data=json.dumps(rows[i:i+500], default=_json_default))
            if r.status_code >= 300:
                raise RuntimeError(f'upsert {table} lỗi {r.status_code}: {r.text[:500]}')
        return len(rows)


def _json_default(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if math.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)): return bool(o)
    if isinstance(o, (pd.Timestamp,)): return o.strftime('%Y-%m-%d')
    return str(o)


def clean(v):
    if v is None: return None
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)): return None
    if isinstance(v, (np.floating,)): return None if np.isnan(v) else float(v)
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.bool_,)): return bool(v)
    return v


def records(df):
    return [{k: clean(v) for k, v in r.items()} for r in df.to_dict('records')]


def sb_has_rows(sb, table):
    r = requests.get(f'{sb.url}/rest/v1/{table}', params={'select': 'data_date', 'limit': 1}, headers=sb.h, timeout=60)
    return r.status_code < 300 and len(r.json()) > 0


# ---------- đồng bộ dữ liệu ----------
def pull(cfg, sb):
    root = Path(cfg['paths']['panel']).parent.parent
    got = {}
    for local, key in SYNC_FILES.items():
        got[local] = sb.download(key, root / local)
    inbox = Path(cfg['paths']['inbox'])
    moved = []
    for name in sb.list('inbox/'):
        if name.endswith(('.csv', '.parquet')):
            sb.download(f'inbox/{name}', inbox / name); moved.append(name)
    log.info('storage pull: %s | inbox: %s', {k: v for k, v in got.items() if v}, moved)
    if not got['data/panel.parquet']:
        raise SystemExit('Không có data/panel.parquet trong Storage — chạy `python -m vnq storage bootstrap` trước.')
    return moved


def push(cfg, sb, inbox_done=()):
    root = Path(cfg['paths']['panel']).parent.parent
    for local, key in SYNC_FILES.items():
        if (root / local).exists():
            sb.upload(root / local, key)
    for f in Path(cfg['paths']['reports']).glob('signals_*.*'):
        sb.upload(f, f'reports/{f.name}', 'text/html; charset=utf-8' if f.suffix == '.html' else 'text/plain; charset=utf-8')
    import datetime as dt
    ts = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    for name in inbox_done:
        sb.move(f'inbox/{name}', f'archive/{ts}_{name}')
    log.info('storage push xong; archive inbox: %s', list(inbox_done))


def bootstrap(cfg, sb, seed_dir):
    """Lần đầu: đẩy dữ liệu seed (panel từ 2022, vnindex, ngành) lên Storage."""
    seed = Path(seed_dir)
    for name in ('panel.parquet', 'vnindex.parquet', 'industry.csv'):
        sb.upload(seed / name, f'data/{name}')
    log.info('bootstrap xong: %s', [p.name for p in seed.iterdir()])


# ---------- publish lên Postgres ----------
def publish(cfg, sb):
    st, rp = Path(cfg['paths']['state']), Path(cfg['paths']['reports'])
    last = json.load(open(st / 'last_run.json', encoding='utf-8'))
    d0 = last['data_date']
    mdir = Path(cfg['paths']['models']) / cfg['model_version']
    man = json.load(open(mdir / 'manifest.json', encoding='utf-8'))
    n = {}
    n['model_versions'] = sb.upsert('model_versions', [dict(
        version=man['version'], created_at=man['created'], ledger_hash=man['ledger_hash'], best=man['best'],
        params=man['lgb_params'], features=man['features'], train_start=man['train_start'], train_end=man['train_end'],
        train_end_effective=man['train_end_effective'], n_train=man['n_train'], wf_ic=man['wf_ic'], note=man.get('note', ''))], 'version')
    wf = pd.read_csv(mdir / 'walkforward_log.csv')
    wf['version'] = man['version']
    n['experiments'] = sb.upsert('experiments', records(wf[['version', 'fold', 'model', 'cfg', 'ic_mean', 'n_train', 'n_val']]),
                                 'version,fold,model')
    n['daily_runs'] = sb.upsert('daily_runs', [dict(
        data_date=d0, run_at=last['run_at'], model_version=last['model_version'], n_eligible=last['n_eligible'],
        n_pool=last['n_pool'], regime_universe=last['regime_universe'], regime_pool=last['regime_pool'],
        qc=last['qc'], warnings=last['warnings'], quarantine=last['quarantine'], gate_pass=last['gate_pass'],
        report_path=f"reports/{last['report_html']}")], 'data_date')
    g = json.load(open(st / 'gate.json', encoding='utf-8'))
    n['gate_snapshots'] = sb.upsert('gate_snapshots', [dict(
        data_date=d0, model_version=g['model_version'], test_start=g['test_start'],
        n_test_days=g['metrics']['lightgbm'].get('n_days', 0), checks=[{'name': k, 'pass': bool(v)} for k, v in g['checks'].items()], metrics=g['metrics'],
        strategy_pass=g['strategy_pass'], computed_at=g['updated'])], 'data_date')
    sc = pd.read_csv(rp / f'scores_{d0}.csv').rename(columns={'date': 'data_date'})
    n['scores_daily'] = sb.upsert('scores_daily', records(sc), 'data_date,ticker')
    tab = pd.read_csv(rp / f'signals_{d0}.csv')
    tab.insert(0, 'data_date', d0)
    tab['rank_sel'] = range(1, len(tab)+1)
    tab['model_version'] = last['model_version']; tab['gate_pass'] = last['gate_pass']
    cols = ['data_date', 'ticker', 'rank_sel', 'industry', 'close', 'p_up_5', 'rank_pool', 'rank_all', 'd_p', 'value_score',
            'value_mode', 'trend_score', 'regime', 'regime_prev', 'atr14_pct', 'liq20', 'action', 'risks', 'reasons',
            'model_version', 'gate_pass']
    n['signals'] = sb.upsert('signals', records(tab[cols]), 'data_date,ticker')
    lg = pd.read_csv(st / 'signals_log.csv')
    lg['data_date'] = pd.to_datetime(lg.data_date).dt.strftime('%Y-%m-%d')
    out = lg[['data_date', 'ticker', 'status', 'gross', 'net', 'y_bin', 'univ_mean', 'excess']]
    n['signals(outcomes)'] = sb.upsert('signals', records(out), 'data_date,ticker')
    # snapshot dự báo vs thực tế: chỉ đẩy 15 ngày dự báo gần nhất (phần có thể vừa được quyết toán) + toàn bộ chấm điểm
    try:
        pp = st / 'predictions_log.parquet'
        if pp.exists():
            pr = pd.read_parquet(pp)
            pr['data_date'] = pd.to_datetime(pr.data_date)
            recent = sorted(pr.data_date.unique())[-15:]
            first = not sb_has_rows(sb, 'predictions_daily')
            pr = pr if first else pr[pr.data_date.isin(recent)]
            pr['data_date'] = pr.data_date.dt.strftime('%Y-%m-%d')
            n['predictions_daily'] = sb.upsert('predictions_daily', records(pr), 'data_date,ticker')
        le = st / 'live_eval.csv'
        if le.exists():
            n['live_eval_daily'] = sb.upsert('live_eval_daily', records(pd.read_csv(le)), 'data_date')
    except RuntimeError as ex:   # bảng chưa được tạo (migration 20261027000000 chưa apply) → không làm hỏng lần chạy
        log.warning('Bỏ qua publish snapshot dự báo: %s', str(ex)[:200])
    log.info('publish %s: %s', d0, n)
    return n
