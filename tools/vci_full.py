"""Kéo VCI toàn bộ lịch sử từ 2022-01-01 đến hôm nay cho mã trong panel + VNINDEX.
Chỉ ghi artifact, KHÔNG upload Supabase. Kiểm tra số phiên so với lịch giao dịch ước tính."""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import pandas as pd, requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'out' / 'vci_full'
PANEL = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet', columns=['ticker', 'date'])
START, END = dt.date(2022, 1, 1), dt.date.today()
TICKERS = sorted(PANEL[PANEL.date == '2026-07-10'].ticker.unique().tolist()) + ['VNINDEX']
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
     'Content-Type': 'application/json', 'Origin': 'https://trading.vietcap.com.vn',
     'Referer': 'https://trading.vietcap.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def vci(sym, count_back):
    r = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart', headers=H, timeout=60,
                      json={'timeFrame': 'ONE_DAY', 'symbols': [sym], 'to': ts(END) + 86400, 'countBack': count_back})
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code} {r.text[:80]}')
    x = r.json(); x = x[0] if isinstance(x, list) else x['data'][0]
    d = pd.DataFrame({'t': x['t'], 'open': x['o'], 'high': x['h'], 'low': x['l'], 'close': x['c'], 'volume': x['v']})
    d['date'] = pd.to_datetime(d['t'].astype('int64'), unit='s').dt.normalize()
    d = d[d.date >= pd.Timestamp(START)]
    if sym != 'VNINDEX':
        for c in ['open', 'high', 'low', 'close']:
            d[c] = d[c] / 1000.0
    return d[['date', 'open', 'high', 'low', 'close', 'volume']].sort_values('date')


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    expected = len(pd.bdate_range(START, END))  # trần số ngày thường; số phiên thực tế thấp hơn (lễ)
    frames, rep = [], {'expected_weekdays': expected, 'per_ticker': {}, 'fail': []}
    for i, t in enumerate(TICKERS, 1):
        try:
            d = vci(t, count_back=expected + 5)
        except Exception as e:
            rep['fail'].append(f'{t}:{str(e)[:80]}'); time.sleep(0.3); continue
        d.insert(0, 'ticker', t)
        frames.append(d)
        rep['per_ticker'][t] = {'rows': len(d), 'first': str(d.date.min().date()), 'last': str(d.date.max().date())}
        time.sleep(0.3)
    all_ = pd.concat(frames)
    summ = {'tickers_ok': len(frames), 'fail': rep['fail'], 'rows': int(len(all_)),
            'dup_ticker_date': int(all_.duplicated(['ticker', 'date']).sum()),
            'nonpositive_close': int((all_.close <= 0).sum()),
            'high_lt_low': int((all_.high < all_.low).sum()),
            'min_rows': min(v['rows'] for v in rep['per_ticker'].values()),
            'max_rows': max(v['rows'] for v in rep['per_ticker'].values()),
            'first_date_min': min(v['first'] for v in rep['per_ticker'].values()),
            'first_date_max': max(v['first'] for v in rep['per_ticker'].values())}
    all_.to_csv(OUT / 'full_history.csv', index=False, encoding='utf-8')
    (OUT / 'report.json').write_text(json.dumps({'summary': summ, 'per_ticker': rep['per_ticker']}, ensure_ascii=False, indent=1), encoding='utf-8')
    print('VCIFULL ' + json.dumps(summ, ensure_ascii=False))


if __name__ == '__main__':
    main()
