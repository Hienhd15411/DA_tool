"""Rút toàn bộ dữ liệu của MỘT ngày khỏi Storage + Supabase (dùng khi ngày đó bị nạp nến chưa chốt).

python tools/rollback_date.py 2026-10-27
Storage: panel/vnindex (bỏ nến ngày đó), state/predictions_log.parquet (bỏ dự báo ngày đó + mở lại các dòng đã
quyết toán bằng giá ngày đó), state/signals_log.csv (bỏ ngày đó + mở lại tín hiệu 6 phiên trước).
Mỗi file ghi xong được đọc lại tới khi khớp (Storage có độ trễ đồng bộ).
Supabase: xóa dòng data_date = ngày đó; xóa chấm điểm live của các ngày bị mở lại. Lần chạy sau tính lại từ dữ liệu đã chốt.
"""
import io, os, sys, time
import pandas as pd, requests

D = pd.Timestamp(sys.argv[1])
U, K = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'apikey': K, 'Authorization': f'Bearer {K}'}
B = os.environ.get('VNQ_BUCKET', 'vnq-data')
ACT = ['real', 'net', 'y_bin', 'settled_on']


def sget(k):
    r = requests.get(f'{U}/storage/v1/object/{B}/{k}', headers={**H, 'Cache-Control': 'no-cache'}, params={'t': time.time()}, timeout=300)
    return None if r.status_code in (400, 404) else r.content


def sput(k, data, check=None):
    r = requests.post(f'{U}/storage/v1/object/{B}/{k}', headers={**H, 'x-upsert': 'true', 'Content-Type': 'application/octet-stream'}, data=data, timeout=300)
    r.raise_for_status()
    if check is None: return
    for i in range(18):   # đọc lại tới khi bản trên Storage là bản vừa ghi
        if check(sget(k)): return
        time.sleep(10)
    sys.exit(f'Storage chưa trả bản mới của {k} sau 3 phút — dừng để không chạy trên dữ liệu cũ')


def pq(raw): return pd.read_parquet(io.BytesIO(raw))
def to_pq(df): b = io.BytesIO(); df.to_parquet(b, index=False); return b.getvalue()


# 1) giá: bỏ nến ngày D
dates = None
for key in ('data/panel.parquet', 'data/vnindex.parquet'):
    raw = sget(key); df = pq(raw); m = df.date == D
    if key.endswith('panel.parquet'): dates = sorted(df[df.date < D].date.unique())
    if m.any():
        sput(f'data/backup/{key.split("/")[-1]}.before_rollback_{D:%Y%m%d}', raw)
        sput(key, to_pq(df[~m]), check=lambda r: r is not None and not (pq(r).date == D).any())
    print(f'{key}: bỏ {int(m.sum())} nến ngày {D:%Y-%m-%d}')
prev6 = [pd.Timestamp(x) for x in dates[-6:]]   # tín hiệu có t+5 / t+6 rơi vào D

# 2) snapshot dự báo: bỏ ngày D, mở lại dòng đã quyết toán bằng giá ngày D
raw = sget('state/predictions_log.parquet')
reopened = []
if raw is not None:
    lg = pq(raw); lg['data_date'] = pd.to_datetime(lg.data_date)
    drop = lg.data_date == D
    reo = lg.settled_on.astype(str).eq(f'{D:%Y-%m-%d}') & ~drop
    reopened = sorted({d.strftime('%Y-%m-%d') for d in lg[reo].data_date})
    lg.loc[reo, 'status'] = 'open'
    for c in ACT: lg.loc[reo, c] = None
    lg = lg[~drop]
    sput('state/predictions_log.parquet', to_pq(lg),
         check=lambda r: r is not None and not (pd.to_datetime(pq(r).data_date) == D).any()
         and not pq(r).settled_on.astype(str).eq(f'{D:%Y-%m-%d}').any())
    print(f'predictions_log: bỏ {int(drop.sum())} dòng ngày {D:%Y-%m-%d}; mở lại {int(reo.sum())} dòng đã quyết toán bằng giá ngày đó ({reopened})')

# 3) nhật ký tín hiệu top 10: bỏ ngày D, mở lại tín hiệu 6 phiên trước (kết quả có thể đã dùng giá D)
raw = sget('state/signals_log.csv')
if raw is not None:
    sl = pd.read_csv(io.BytesIO(raw)); sl['_d'] = pd.to_datetime(sl.data_date)
    drop = sl._d == D; reo = sl._d.isin(prev6) & sl.status.isin(['settled', 'unfilled_ceiling'])
    sl.loc[reo, 'status'] = 'open'
    for c in ('gross', 'net', 'y_bin', 'univ_mean', 'excess'): sl.loc[reo, c] = None
    out = sl[~drop].drop(columns='_d')
    sput('state/signals_log.csv', out.to_csv(index=False).encode(),
         check=lambda r: r is not None and not (pd.to_datetime(pd.read_csv(io.BytesIO(r)).data_date) == D).any())
    print(f'signals_log: bỏ {int(drop.sum())} dòng, mở lại {int(reo.sum())} tín hiệu')


# 4) Supabase
def rest(method, t, params, body=None):
    r = requests.request(method, f'{U}/rest/v1/{t}', headers={**H, 'Content-Type': 'application/json', 'Prefer': 'return=representation'},
                         params=params, json=body, timeout=60)
    print(f'  {method} {t} {params}: {r.status_code} {len(r.json()) if r.status_code < 300 else r.text[:150]}')


for t in ['gate_snapshots', 'signals', 'scores_daily', 'predictions_daily', 'live_eval_daily', 'daily_runs']:
    rest('DELETE', t, {'data_date': f'eq.{D:%Y-%m-%d}'})
if reopened:
    rest('DELETE', 'live_eval_daily', {'data_date': f'in.({",".join(reopened)})'})
    rest('PATCH', 'predictions_daily', {'data_date': f'in.({",".join(reopened)})'},
         {'status': 'open', 'real': None, 'net': None, 'y_bin': None, 'settled_on': None})
p6 = ','.join(d.strftime('%Y-%m-%d') for d in prev6)
rest('PATCH', 'signals', {'data_date': f'in.({p6})', 'status': 'in.(settled,unfilled_ceiling)'},
     {'status': 'open', 'gross': None, 'net': None, 'y_bin': None, 'univ_mean': None, 'excess': None})
