"""Kéo dữ liệu OHLCV hằng ngày trên máy cá nhân → upload vào Supabase Storage inbox (vnq-data/inbox/).

Chạy trên Windows:
  set SUPABASE_URL=https://wozvgbhqbzxnpfypbndt.supabase.co
  set SUPABASE_SERVICE_ROLE_KEY=<service_role key>
  python tools/fetch_daily.py --tickers tickers.txt --start 2026-07-13 --end 2026-10-26

Chỉ hàm fetch_bars() phụ thuộc nguồn dữ liệu. Phần còn lại (kiểm tra, ghi CSV, upload) cố định.
Định dạng đầu ra theo docs/02_ARCHITECTURE.md: ticker,date,open,high,low,close,volume,gt_khop.
Giá phải là nghìn đồng và đã điều chỉnh quyền. VNINDEX dùng ticker = VNINDEX.
"""
from __future__ import annotations
import argparse, datetime as dt, os, sys
from pathlib import Path

import pandas as pd
import requests

BUCKET = 'vnq-data'
OUT_DIR = Path(__file__).resolve().parent / 'out'
COLS = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'gt_khop']


def fetch_bars(ticker: str, start: str, end: str) -> pd.DataFrame | None:
    """Trả về DataFrame với cột: date, open, high, low, close, volume, gt_khop (tùy chọn).
    Trả None nếu không có dữ liệu. Triển khai theo nguồn đã chọn.
    Nếu nguồn trả giá đơn vị đồng (VD 65000) thì chia 1000 để ra nghìn đồng.
    """
    raise NotImplementedError('Chưa chọn nguồn dữ liệu — triển khai fetch_bars() cho nguồn đã chọn.')


def clean(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    df = df.copy()
    df['ticker'] = ticker
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.normalize()
    if 'gt_khop' not in df:
        df['gt_khop'] = pd.NA
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['date', 'open', 'high', 'low', 'close', 'volume'])
    ok = (df[['open', 'high', 'low', 'close']] > 0).all(axis=1) & (df['high'] >= df['low'])
    dropped = int((~ok).sum())
    if dropped:
        print(f'  [{ticker}] bỏ {dropped} dòng giá không hợp lệ')
    return df.loc[ok, COLS]


def write_csv(frames: list[pd.DataFrame], stamp: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f'inbox_{stamp}.csv'
    pd.concat(frames).sort_values(['ticker', 'date']).to_csv(out, index=False, encoding='utf-8')
    return out


def upload(path: Path, url: str, key: str) -> None:
    headers = {'Authorization': f'Bearer {key}', 'apikey': key,
               'Content-Type': 'text/csv', 'x-upsert': 'true'}
    with open(path, 'rb') as f:
        r = requests.post(f'{url}/storage/v1/object/{BUCKET}/inbox/{path.name}',
                          data=f.read(), headers=headers, timeout=300)
    if r.status_code not in (200, 201):
        sys.exit(f'Upload lỗi {r.status_code}: {r.text[:300]}')
    print(f'Đã upload {path.name} → {BUCKET}/inbox/')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--tickers', required=True, help='file txt, mỗi dòng một mã (VD VNM), thêm VNINDEX nếu cần')
    ap.add_argument('--start', required=True)
    ap.add_argument('--end', default=dt.date.today().isoformat())
    ap.add_argument('--no-upload', action='store_true', help='chỉ ghi CSV local, không upload')
    a = ap.parse_args()

    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not a.no_upload and (not url or not key):
        sys.exit('Thiếu SUPABASE_URL hoặc SUPABASE_SERVICE_ROLE_KEY trong biến môi trường.')

    tickers = [t.strip().upper() for t in Path(a.tickers).read_text(encoding='utf-8').splitlines() if t.strip()]
    frames, failed = [], []
    for t in tickers:
        try:
            raw = fetch_bars(t, a.start, a.end)
        except NotImplementedError as e:
            sys.exit(str(e))
        except Exception as e:
            failed.append(t)
            print(f'  [{t}] lỗi: {type(e).__name__}: {str(e)[:120]}')
            continue
        if raw is None or raw.empty:
            failed.append(t)
            continue
        frames.append(clean(raw, t))
    if not frames:
        sys.exit('Không kéo được mã nào.')

    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    path = write_csv(frames, stamp)
    print(f'Ghi {path} — {sum(len(f) for f in frames)} dòng, {len(frames)} mã, lỗi/không có dữ liệu: {failed}')
    if not a.no_upload:
        upload(path, url, key)


if __name__ == '__main__':
    main()
