"""Kéo OHLCV từ VCI (trading.vietcap.com.vn, endpoint chart gap-chart — cùng endpoint thư viện vnstock dùng)
và đối chiếu với Yahoo (thô + đã điều chỉnh), VNDirect dchart và panel. Không upload Supabase."""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import pandas as pd, requests, yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'out' / 'vci'
PANEL = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet')
VNIDX = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'vnindex.parquet')
START, END = dt.date(2026, 7, 1), dt.date(2026, 10, 27)
TICKERS = ['VNM', 'HPG', 'FPT', 'VCB', 'MWG', 'SZC', 'DIG', 'GMD', 'HDB', 'VPB', 'PHR', 'TRC', 'VHM', 'PVD', 'VNINDEX']
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
     'Accept': 'application/json', 'Content-Type': 'application/json',
     'Origin': 'https://trading.vietcap.com.vn', 'Referer': 'https://trading.vietcap.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def vci(sym, start=START, end=END):
    n_bdays = len(pd.bdate_range(start, end)) + 1
    r = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart', headers=H, timeout=30,
                      json={'timeFrame': 'ONE_DAY', 'symbols': [sym], 'to': ts(end) + 86400, 'countBack': n_bdays})
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code} {r.text[:100]}')
    x = r.json()
    x = x[0] if isinstance(x, list) else x['data'][0]
    d = pd.DataFrame({'t': x['t'], 'o': x['o'], 'h': x['h'], 'l': x['l'], 'c': x['c'], 'v': x['v']})
    d['date'] = pd.to_datetime(d['t'].astype('int64'), unit='s').dt.normalize()
    d = d[(d.date >= pd.Timestamp(start)) & (d.date <= pd.Timestamp(end))].sort_values('date')
    return d[['date', 'o', 'h', 'l', 'c', 'v']]


def yahoo(sym, adj):
    s = '^VNINDEX' if sym == 'VNINDEX' else f'{sym}.VN'
    h = yf.Ticker(s).history(start=START.isoformat(), end=(END + dt.timedelta(days=1)).isoformat(), auto_adjust=adj)
    h = h.reset_index(); h['date'] = pd.to_datetime(h['Date']).dt.tz_localize(None).dt.normalize()
    return h[['date', 'Close']].rename(columns={'Close': 'c'})


def vnd(sym):
    j = requests.get('https://dchart-api.vndirect.com.vn/dchart/history',
                     params={'resolution': 'D', 'symbol': sym, 'from': ts(START), 'to': ts(END) + 86400},
                     headers={'User-Agent': H['User-Agent']}, timeout=30).json()
    return pd.DataFrame({'date': pd.to_datetime(j['t'], unit='s').normalize(), 'c': j['c']})


def cmp(a, b):
    m = a[['date', 'c']].merge(b[['date', 'c']], on='date', suffixes=('_a', '_b'))
    if len(m) == 0:
        return None
    r = m.c_a / m.c_b
    return {'n': len(m), 'median_ratio': round(float(r.median()), 5),
            'share_within_0.5pct': round(float(((r - 1).abs() <= 0.005).mean()), 3)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {}
    frames = []
    for t in TICKERS:
        try:
            v = vci(t)
        except Exception as e:
            rep[t] = {'vci_error': f'{type(e).__name__}: {str(e)[:150]}'}
            time.sleep(0.3); continue
        scale = 1000.0 if v.c.median() > 1000 else 1.0   # VCI trả VND → nghìn đồng
        vv = v.assign(c=v.c / scale)
        frames.append(vv.assign(ticker=t))
        pan = (VNIDX[VNIDX.ticker == 'VNINDEX'] if t == 'VNINDEX' else PANEL[PANEL.ticker == t])[['date', 'close']].rename(columns={'close': 'c'})
        pan = pan[(pan.date >= pd.Timestamp(START)) & (pan.date <= pd.Timestamp(END))]
        rep[t] = {'vci_rows': len(v), 'vci_last': f'{v.date.max():%Y-%m-%d} {v.c.iloc[-1]}',
                  'vci_scale_applied': scale,
                  'vs_panel': cmp(vv, pan)}
        if t != 'VNINDEX':
            rep[t]['vs_yahoo_raw'] = cmp(vv, yahoo(t, False).assign(c=lambda x: x.c / 1000.0))
            rep[t]['vs_yahoo_adj'] = cmp(vv, yahoo(t, True).assign(c=lambda x: x.c / 1000.0))
        rep[t]['vs_vnd'] = cmp(vv, vnd(t))
        time.sleep(0.3)
    if frames:
        pd.concat(frames).to_csv(OUT / 'vci_candidates.csv', index=False, encoding='utf-8')
    (OUT / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    print('VCIPROBE ' + json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    main()
