"""Kiểm tra panel trên Storage: ngày lớn nhất, và header cache khi tải có/không query tránh cache."""
import io, os, time
import pandas as pd, requests
URL = os.environ['SUPABASE_URL'].rstrip('/'); KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'Authorization': f'Bearer {KEY}', 'apikey': KEY}
def check(label, u):
    r = requests.get(u, headers=H, timeout=300)
    p = pd.read_parquet(io.BytesIO(r.content), columns=['ticker', 'date'])
    print(f"{label}: status={r.status_code} bytes={len(r.content)} max_date={p.date.max():%Y-%m-%d} rows={len(p)} "
          f"cache={r.headers.get('cache-control')} age={r.headers.get('age')} etag={r.headers.get('etag')}")
base = f'{URL}/storage/v1/object/vnq-data/data/panel.parquet'
check('plain', base)
check('cachebust', f'{base}?t={int(time.time())}')
r = requests.post(f'{URL}/storage/v1/object/list/vnq-data', headers=H, json={'prefix': 'data/', 'limit': 50}, timeout=60)
print('list data/:', [(o['name'], o.get('updated_at'), (o.get('metadata') or {}).get('size')) for o in r.json()])
print('panel meta:', [ (o['name'], o.get('updated_at'), (o.get('metadata') or {}).get('size'), (o.get('metadata') or {}).get('eTag')) for o in requests.post(f'{URL}/storage/v1/object/list/vnq-data', headers=H, json={'prefix': 'data/', 'limit': 50}, timeout=60).json() if o['name'] in ('panel.parquet',)])
print('backup list:', requests.post(f'{URL}/storage/v1/object/list/vnq-data', headers=H, json={'prefix': 'data/backup/', 'limit': 50}, timeout=60).json())
