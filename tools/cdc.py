"""CDC hằng ngày: kéo VCI 15 phiên gần nhất cho mọi mã trong panel + VNINDEX.
- Mã có giá lệch > adjust_tol trên ngày trùng → kéo lại toàn bộ lịch sử từ 2022 cho riêng mã đó (thay thế).
- Mã không lệch → chỉ thêm các phiên mới sau ngày cuối trong panel.
Ghi panel + vnindex lên Storage (sao lưu bản trước vào data/backup/prev_*), xác minh, rồi chạy daily."""
from __future__ import annotations
import datetime as dt, io, os, sys, time
from pathlib import Path
import pandas as pd, requests

ROOT = Path(__file__).resolve().parents[1]
BUCKET = 'vnq-data'
URL = os.environ['SUPABASE_URL'].rstrip('/')
KEY = os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'Authorization': f'Bearer {KEY}', 'apikey': KEY}
TOL = 0.005
START_FULL = dt.date(2022, 1, 1)
ICT = dt.timezone(dt.timedelta(hours=7))
NOW = dt.datetime.now(ICT)
TODAY = NOW.date()
SESSION_CLOSED = NOW.time() >= dt.time(15, 30)   # sau ATC 14:45 + độ trễ nguồn
OVERWRITE = 5   # luôn ghi đè N phiên gần nhất bằng dữ liệu VCI (sửa nến dở / điều chỉnh cuối ngày)
VH = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
      'Content-Type': 'application/json', 'Origin': 'https://trading.vietcap.com.vn',
      'Referer': 'https://trading.vietcap.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def vci(sym, start: dt.date):
    n = len(pd.bdate_range(start, TODAY)) + 5
    # VCI trả 418/429 khi bị gọi dồn (30/10/2026: chết cả job ở mã thứ N) → lùi 15/45/90 s rồi thử lại
    for wait in (15, 45, 90, None):
        try:
            r = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart', headers=VH, timeout=30,
                              json={'timeFrame': 'ONE_DAY', 'symbols': [sym], 'to': ts(TODAY) + 86400, 'countBack': n})
            if r.status_code == 200:
                break
            err = f'HTTP {r.status_code}'
            if r.status_code not in (418, 429) and r.status_code < 500:
                raise RuntimeError(err)
        except requests.RequestException as e:
            err = type(e).__name__
        if wait is None:
            raise RuntimeError(err)
        print(f'  {sym}: {err}, thử lại sau {wait}s', flush=True)
        time.sleep(wait)
    x = r.json(); x = x[0] if isinstance(x, list) else x['data'][0]
    d = pd.DataFrame({'t': x['t'], 'open': x['o'], 'high': x['h'], 'low': x['l'], 'close': x['c'], 'volume': x['v']})
    d['date'] = pd.to_datetime(d['t'].astype('int64'), unit='s').dt.normalize()
    d = d[d.date >= pd.Timestamp(start)]
    if sym != 'VNINDEX':
        for c in ['open', 'high', 'low', 'close']:
            d[c] = d[c] / 1000.0
    return d[['date', 'open', 'high', 'low', 'close', 'volume']].sort_values('date').reset_index(drop=True)


def sget(key) -> bytes:
    r = requests.get(f'{URL}/storage/v1/object/{BUCKET}/{key}', headers=H, timeout=300); r.raise_for_status()
    return r.content


def sput(key, data: bytes):
    r = requests.post(f'{URL}/storage/v1/object/{BUCKET}/{key}', data=data, timeout=600,
                      headers={**H, 'x-upsert': 'true', 'Content-Type': 'application/octet-stream'})
    if r.status_code not in (200, 201):
        sys.exit(f'upload {key} lỗi {r.status_code}: {r.text[:200]}')


def main():
    panel = pd.read_parquet(io.BytesIO(sget('data/panel.parquet')))
    idx = pd.read_parquet(io.BytesIO(sget('data/vnindex.parquet')))
    tickers = sorted(panel.ticker.unique().tolist())
    last = panel.groupby('ticker').date.max()
    new_rows, replaced, appended, failed = [], [], [], []
    for t in tickers + ['VNINDEX']:
        try:
            recent = vci(t, TODAY - dt.timedelta(days=30))
        except Exception as e:
            failed.append(f'{t}:{str(e)[:60]}'); continue
        if not SESSION_CLOSED:   # phiên hôm nay chưa đóng → không lấy nến dở
            recent = recent[recent.date.dt.date < TODAY]
        ref = idx if t == 'VNINDEX' else panel[panel.ticker == t]
        ref = ref[['date', 'close']]
        # so khớp phần chồng lấn CŨ (trước OVERWRITE phiên gần nhất) để phát hiện điều chỉnh quyền
        keep_from = sorted(recent.date.unique())[-OVERWRITE] if len(recent) >= OVERWRITE else recent.date.min()
        m = recent[recent.date < keep_from][['date', 'close']].merge(ref, on='date', suffixes=('_v', '_p'))
        mismatch = len(m) > 0 and ((m.close_v / m.close_p - 1).abs() > TOL).any()
        if mismatch:
            full = vci(t, START_FULL)
            if not SESSION_CLOSED:
                full = full[full.date.dt.date < TODAY]
            if t == 'VNINDEX':
                idx = full.assign(ticker='VNINDEX')[idx.columns]
            else:
                panel = panel[panel.ticker != t]
                panel = pd.concat([panel, full.assign(ticker=t, gt_khop=lambda x: x.close * x.volume * 1000)])
            replaced.append(t)
        else:
            # ghi đè OVERWRITE phiên gần nhất + thêm phiên mới (nến dở/khối lượng thiếu được thay bằng nến chốt)
            add = recent[recent.date >= keep_from]
            if len(add):
                if t == 'VNINDEX':
                    idx = pd.concat([idx[~idx.date.isin(add.date)], add.assign(ticker='VNINDEX')[idx.columns]])
                else:
                    panel = panel[~((panel.ticker == t) & panel.date.isin(add.date))]
                    panel = pd.concat([panel, add.assign(ticker=t, gt_khop=lambda x: x.close * x.volume * 1000)])
                appended.append(f'{t}+{len(add)}')
        time.sleep(0.6)   # giãn nhịp gọi VCI để tránh 418
    if failed:
        sys.exit(f'Dừng: không lấy được {failed}')
    panel = panel.sort_values(['ticker', 'date']).reset_index(drop=True)
    panel = panel[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'gt_khop']]
    checks = {'dups': int(panel.duplicated(['ticker', 'date']).sum()),
              'nonpositive': int((panel[['open', 'high', 'low', 'close']] <= 0).any(axis=1).sum()),
              'high_lt_low': int((panel.high < panel.low).sum())}
    if any(checks.values()):
        sys.exit(f'Dừng: kiểm tra không đạt {checks}')
    print(f'Phiên hôm nay {"đã" if SESSION_CLOSED else "CHƯA"} đóng ({NOW:%H:%M} ICT)')
    print(f'Thay lịch sử: {replaced}')
    print(f'Thêm phiên mới: {len(appended)} mã')
    print(f'Panel: {len(panel):,} dòng, đến {panel.date.max():%Y-%m-%d}; VNINDEX đến {idx.date.max():%Y-%m-%d}')

    stamp = 'prev'
    sput(f'data/backup/panel_{stamp}.parquet', sget('data/panel.parquet'))
    sput(f'data/backup/vnindex_{stamp}.parquet', sget('data/vnindex.parquet'))
    buf = io.BytesIO(); panel.to_parquet(buf, index=False); sput('data/panel.parquet', buf.getvalue())
    buf = io.BytesIO(); idx.to_parquet(buf, index=False); sput('data/vnindex.parquet', buf.getvalue())
    for _ in range(12):
        back = pd.read_parquet(io.BytesIO(sget('data/panel.parquet')), columns=['date'])
        if back.date.max() == panel.date.max():
            break
        time.sleep(10)
    if back.date.max() != panel.date.max():
        sys.exit(f'Xác minh thất bại: Storage đến {back.date.max():%Y-%m-%d}')
    print('Ghi và xác minh OK.')


if __name__ == '__main__':
    main()
