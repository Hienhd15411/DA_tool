"""Đối chiếu giá thô Yahoo (auto_adjust=False) với các nguồn VN độc lập, trên runner GitHub.
Ghi tools/out/crosscheck/report.json. Không upload Supabase."""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import pandas as pd, requests, yfinance as yf

OUT = Path(__file__).resolve().parents[1] / 'tools' / 'out' / 'crosscheck'
TICKERS = ['VNM', 'HPG', 'FPT', 'VCB', 'MWG', 'SZC', 'DIG', 'VNINDEX']
START, END = dt.date(2026, 7, 1), dt.date(2026, 10, 26)
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
      'Origin': 'https://dstock.vndirect.com.vn', 'Referer': 'https://dstock.vndirect.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def src_vnd(sym):
    r = requests.get('https://dchart-api.vndirect.com.vn/dchart/history',
                     params={'resolution': 'D', 'symbol': sym, 'from': ts(START), 'to': ts(END) + 86400},
                     headers=UA, timeout=30)
    j = r.json()
    if j.get('s') != 'ok' or not j.get('t'):
        raise RuntimeError(f"status={r.status_code} s={j.get('s')}")
    return pd.DataFrame({'date': pd.to_datetime(j['t'], unit='s').normalize(), 'close': j['c'],
                         'open': j['o'], 'high': j['h'], 'low': j['l'], 'volume': j['v']})


def src_tcbs(sym):
    r = requests.get('https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term',
                     params={'resolution': 'D', 'ticker': sym, 'type': 'index' if sym == 'VNINDEX' else 'stock',
                             'to': ts(END) + 86400, 'countBack': 1000}, headers=UA, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code} {r.text[:80]}')
    d = pd.DataFrame(r.json()['data'])
    d['date'] = pd.to_datetime(d['tradingDate']).dt.tz_localize(None).dt.normalize()
    return d.rename(columns={'volume': 'volume'})[['date', 'close', 'open', 'high', 'low', 'volume']]


def src_vci(sym):
    r = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart', headers=UA, timeout=30,
                      json={'timeFrame': 'ONE_DAY', 'symbols': [sym], 'to': ts(END) + 86400, 'countBack': 1000})
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code} {r.text[:80]}')
    x = r.json()[0]
    d = pd.DataFrame({'date': pd.to_datetime(x['t'], unit='s').normalize(), 'close': x['c'], 'open': x['o'],
                      'high': x['h'], 'low': x['l'], 'volume': x['v']})
    return d[(d.date >= pd.Timestamp(START)) & (d.date <= pd.Timestamp(END))]


def src_yahoo_raw(sym):
    h = yf.Ticker(f'{sym}.VN' if sym != 'VNINDEX' else '^VNINDEX').history(start=START.isoformat(),
                                                                         end=(END + dt.timedelta(days=1)).isoformat(),
                                                                         auto_adjust=False)
    h = h.reset_index()
    h['date'] = pd.to_datetime(h['Date']).dt.tz_localize(None).dt.normalize()
    return h.rename(columns={'Close': 'close', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Volume': 'volume'})[
        ['date', 'close', 'open', 'high', 'low', 'volume']]


SOURCES = {'vnd_dchart': src_vnd, 'tcbs': src_tcbs, 'vci': src_vci}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {'availability': {}, 'compare': {}}
    for name, fn in SOURCES.items():
        rep['availability'][name] = {}
        for t in TICKERS:
            try:
                d = fn(t)
                rep['availability'][name][t] = f'ok {len(d)} rows, last {d.date.max():%Y-%m-%d}, close_last {d.close.iloc[-1]}'
            except Exception as e:
                rep['availability'][name][t] = f'ERR {type(e).__name__}: {str(e)[:120]}'
            time.sleep(0.3)
    yraw = {}
    for t in TICKERS:
        try:
            yraw[t] = src_yahoo_raw(t)
        except Exception as e:
            rep['availability'].setdefault('yahoo_raw', {})[t] = f'ERR {e}'
    for name, fn in SOURCES.items():
        rep['compare'][name] = {}
        for t in TICKERS:
            if t not in yraw:
                continue
            try:
                src = fn(t)
            except Exception:
                continue
            m = yraw[t][['date', 'close']].merge(src[['date', 'close']], on='date', suffixes=('_y', '_s'))
            if len(m) == 0:
                rep['compare'][name][t] = 'no overlap'
                continue
            ratio = m.close_s / m.close_y
            rep['compare'][name][t] = {'n': len(m), 'median_ratio': round(float(ratio.median()), 4),
                                       'share_within_0.5pct_raw': round(float(((ratio - 1).abs() <= 0.005).mean()), 3),
                                       'share_within_0.5pct_x1000': round(float(((ratio * 1000 - 1).abs() <= 0.005).mean()), 3)}
    (OUT / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    print('CROSSCHECK ' + json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    main()
