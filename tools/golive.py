"""Go-live: thay panel + vnindex trên Supabase Storage bằng lịch sử VCI từ 2022 (đã duyệt bởi Hardy).
Sao lưu bản cũ vào data/backup/ trước khi ghi đè. Ghi đúng định dạng engine: ticker,date,open,high,low,close,volume,gt_khop."""
from __future__ import annotations
import datetime as dt, io, os, sys, time
from pathlib import Path
import pandas as pd, requests

ROOT = Path(__file__).resolve().parents[1]
BUCKET = 'vnq-data'
URL = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'Authorization': f'Bearer {KEY}', 'apikey': KEY}
PANEL_OLD = ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet'
_old = pd.read_parquet(PANEL_OLD, columns=['ticker', 'date'])
TICKERS = sorted(_old[_old.date == pd.Timestamp('2026-07-10')].ticker.unique().tolist())
assert len(TICKERS) > 300, f'danh sách mã bất thường: {len(TICKERS)}'
START, END = dt.date(2022, 1, 1), dt.date.today()
VH = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
      'Content-Type': 'application/json', 'Origin': 'https://trading.vietcap.com.vn',
      'Referer': 'https://trading.vietcap.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def vci(sym):
    n = len(pd.bdate_range(START, END)) + 5
    r = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart', headers=VH, timeout=60,
                      json={'timeFrame': 'ONE_DAY', 'symbols': [sym], 'to': ts(END) + 86400, 'countBack': n})
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}')
    x = r.json(); x = x[0] if isinstance(x, list) else x['data'][0]
    d = pd.DataFrame({'t': x['t'], 'open': x['o'], 'high': x['h'], 'low': x['l'], 'close': x['c'], 'volume': x['v']})
    d['date'] = pd.to_datetime(d['t'].astype('int64'), unit='s').dt.normalize()
    d = d[d.date >= pd.Timestamp(START)]
    if sym != 'VNINDEX':
        for c in ['open', 'high', 'low', 'close']:
            d[c] = d[c] / 1000.0   # VND → nghìn đồng như panel
    return d[['date', 'open', 'high', 'low', 'close', 'volume']].sort_values('date').reset_index(drop=True)


def storage_get(key):
    r = requests.get(f'{URL}/storage/v1/object/{BUCKET}/{key}', headers=H, timeout=300)
    r.raise_for_status()
    return r.content


def storage_put(key, data: bytes, ctype='application/octet-stream'):
    r = requests.post(f'{URL}/storage/v1/object/{BUCKET}/{key}', data=data, timeout=600,
                      headers={**H, 'x-upsert': 'true', 'Content-Type': ctype})
    if r.status_code not in (200, 201):
        sys.exit(f'upload {key} lỗi {r.status_code}: {r.text[:200]}')


def main():
    frames, idx, fail = [], None, []
    for t in TICKERS + ['VNINDEX']:
        try:
            d = vci(t)
        except Exception as e:
            fail.append(f'{t}:{str(e)[:60]}'); time.sleep(0.3); continue
        if t == 'VNINDEX':
            idx = d.assign(ticker='VNINDEX')
        else:
            frames.append(d.assign(ticker=t, gt_khop=lambda x: x.close * x.volume * 1000))
        time.sleep(0.3)
    if fail:
        sys.exit(f'Dừng: lỗi lấy dữ liệu {fail}')
    panel = pd.concat(frames)[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'gt_khop']]
    panel = panel.sort_values(['ticker', 'date']).reset_index(drop=True)
    idx = idx[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']]
    checks = {'dups': int(panel.duplicated(['ticker', 'date']).sum()),
              'nonpositive': int((panel[['open', 'high', 'low', 'close']] <= 0).any(axis=1).sum()),
              'high_lt_low': int((panel.high < panel.low).sum())}
    if any(checks.values()):
        sys.exit(f'Dừng: kiểm tra không đạt {checks}')
    print(f'Panel mới: {len(panel):,} dòng, {panel.ticker.nunique()} mã, {panel.date.min():%Y-%m-%d} → {panel.date.max():%Y-%m-%d}')
    print(f'VNINDEX: {len(idx):,} dòng, đến {idx.date.max():%Y-%m-%d}')

    stamp = '20260710'
    for key in ['data/panel.parquet', 'data/vnindex.parquet']:
        old = storage_get(key)
        storage_put(key.replace('data/', f'data/backup/{key.split("/")[-1].replace(".parquet", "")}_{stamp}.parquet'), old)
        print(f'Sao lưu {key} → data/backup/')

    buf = io.BytesIO(); panel.to_parquet(buf, index=False); storage_put('data/panel.parquet', buf.getvalue())
    buf = io.BytesIO(); idx.to_parquet(buf, index=False); storage_put('data/vnindex.parquet', buf.getvalue())
    print('Đã ghi panel.parquet và vnindex.parquet lên Storage.')


if __name__ == '__main__':
    main()
