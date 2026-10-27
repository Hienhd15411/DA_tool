"""Kéo lịch sử giá THÔ (auto_adjust=False) 2022-01-01 → hôm nay cho các mã trong panel 2026-07-10.
Ghi tools/out/raw/raw_history.csv + summary.json. Không sửa panel, không upload Supabase."""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import pandas as pd, yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'out' / 'raw'
PANEL = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet', columns=['ticker', 'date'])
TICKERS = sorted(PANEL[PANEL.date == '2026-07-10'].ticker.unique())
START, END = '2022-01-01', (dt.date.today() + dt.timedelta(days=1)).isoformat()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames, summary = [], {'n': len(TICKERS), 'ok': 0, 'no_data': [], 'error': [], 'events_div': 0, 'events_split': 0}
    for i, t in enumerate(TICKERS, 1):
        try:
            h = yf.Ticker(f'{t}.VN').history(start=START, end=END, auto_adjust=False, actions=True)
        except Exception as e:
            summary['error'].append(f'{t}:{type(e).__name__}'); time.sleep(0.3); continue
        if h is None or h.empty:
            summary['no_data'].append(t); time.sleep(0.3); continue
        h = h.reset_index()
        h['date'] = pd.to_datetime(h['Date']).dt.tz_localize(None).dt.normalize()
        d = h.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume',
                              'Dividends': 'dividend', 'Stock Splits': 'split'})
        d['ticker'] = t
        summary['events_div'] += int((d['dividend'] > 0).sum())
        summary['events_split'] += int((d['split'] > 0).sum())
        frames.append(d[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'dividend', 'split']])
        summary['ok'] += 1
        if i % 50 == 0: print(f'  {i}/{len(TICKERS)} ok={summary["ok"]}')
        time.sleep(0.3)
    all_ = pd.concat(frames)
    all_.to_csv(OUT / 'raw_history.csv', index=False, encoding='utf-8')
    summary['rows'] = int(len(all_))
    summary['date_min'] = str(all_.date.min().date()); summary['date_max'] = str(all_.date.max().date())
    summary['dup_ticker_date'] = int(all_.duplicated(['ticker', 'date']).sum())
    summary['nonpositive_close'] = int((all_.close <= 0).sum())
    summary['high_lt_low'] = int((all_.high < all_.low).sum())
    (OUT / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print('RAWSUM ' + json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
