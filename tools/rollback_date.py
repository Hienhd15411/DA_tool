"""Rút toàn bộ dữ liệu của MỘT ngày khỏi Storage + Supabase (dùng khi ngày đó bị nạp nến chưa chốt).

python tools/rollback_date.py 2026-10-27
Storage: panel/vnindex (bỏ nến ngày đó), state/predictions_log.parquet, state/signals_log.csv (bỏ dự báo ngày đó).
Supabase: xóa dòng data_date = ngày đó ở các bảng kết quả. Lần chạy sau sẽ tính lại từ dữ liệu đã chốt.
"""
import io, os, sys
import pandas as pd, requests

D = pd.Timestamp(sys.argv[1])
U, K = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'apikey': K, 'Authorization': f'Bearer {K}'}
B = os.environ.get('VNQ_BUCKET', 'vnq-data')


def sget(k):
    r = requests.get(f'{U}/storage/v1/object/{B}/{k}', headers=H, timeout=300)
    return None if r.status_code in (400, 404) else r.content


def sput(k, data):
    r = requests.post(f'{U}/storage/v1/object/{B}/{k}', headers={**H, 'x-upsert': 'true', 'Content-Type': 'application/octet-stream'}, data=data, timeout=300)
    r.raise_for_status()


for key, col in [('data/panel.parquet', 'date'), ('data/vnindex.parquet', 'date'), ('state/predictions_log.parquet', 'data_date')]:
    raw = sget(key)
    if raw is None: print(key, 'không có'); continue
    df = pd.read_parquet(io.BytesIO(raw))
    m = pd.to_datetime(df[col]) == D
    sput(f'data/backup/{key.split("/")[-1]}.before_rollback_{D:%Y%m%d}', raw)
    buf = io.BytesIO(); df[~m].to_parquet(buf, index=False); sput(key, buf.getvalue())
    print(f'{key}: bỏ {int(m.sum())} dòng ngày {D:%Y-%m-%d}, còn {int((~m).sum())}; max {pd.to_datetime(df[~m][col]).max():%Y-%m-%d}')
raw = sget('state/signals_log.csv')
if raw is not None:
    lg = pd.read_csv(io.BytesIO(raw)); m = pd.to_datetime(lg.data_date) == D
    sput('state/signals_log.csv', lg[~m].to_csv(index=False).encode()); print(f'signals_log: bỏ {int(m.sum())} dòng')
for t in ['gate_snapshots', 'signals', 'scores_daily', 'predictions_daily', 'live_eval_daily', 'daily_runs']:
    r = requests.delete(f'{U}/rest/v1/{t}', headers={**H, 'Prefer': 'return=representation'}, params={'data_date': f'eq.{D:%Y-%m-%d}'}, timeout=60)
    print(t, r.status_code, (len(r.json()) if r.status_code < 300 else r.text[:150]))
