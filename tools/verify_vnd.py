"""Đối chiếu VNDirect dchart với panel (đã điều chỉnh, nghìn đồng) và với Yahoo đã điều chỉnh. Không upload."""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import pandas as pd, requests, yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'out' / 'verify_vnd'
PANEL = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet')
VNIDX = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'vnindex.parquet')
START, END = dt.date(2026, 7, 1), dt.date(2026, 10, 26)
TICKERS = ['VNM', 'HPG', 'FPT', 'VCB', 'MWG', 'SZC', 'DIG', 'GMD', 'HDB', 'VPB', 'PHR', 'TRC', 'VHM', 'PVD']
UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
      'Origin': 'https://dstock.vndirect.com.vn', 'Referer': 'https://dstock.vndirect.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def vnd(sym):
    j = requests.get('https://dchart-api.vndirect.com.vn/dchart/history',
                     params={'resolution': 'D', 'symbol': sym, 'from': ts(START), 'to': ts(END) + 86400},
                     headers=UA, timeout=30).json()
    d = pd.DataFrame({'date': pd.to_datetime(j['t'], unit='s').normalize(), 'close_v': j['c']})
    return d


def yahoo_adj(sym):
    s = '^VNINDEX' if sym == 'VNINDEX' else f'{sym}.VN'
    h = yf.Ticker(s).history(start=START.isoformat(), end=(END + dt.timedelta(days=1)).isoformat(), auto_adjust=True)
    h = h.reset_index()
    h['date'] = pd.to_datetime(h['Date']).dt.tz_localize(None).dt.normalize()
    d = h[['date', 'Close']].rename(columns={'Close': 'close_y'})
    if sym != 'VNINDEX':
        d['close_y'] = d['close_y'] / 1000.0
    return d


def share(a, b):
    m = a.merge(b, on='date')
    if len(m) == 0:
        return None
    r = (m.iloc[:, 1] / m.iloc[:, 2] - 1).abs()
    return {'n': len(m), 'within_0.5pct': round(float((r <= 0.005).mean()), 3), 'max_pct': round(float(r.max() * 100), 2)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for t in TICKERS + ['VNINDEX']:
        try:
            v = vnd(t)
        except Exception as e:
            res[t] = f'vnd ERR {e}'; continue
        y = yahoo_adj(t)
        if t == 'VNINDEX':
            p = VNIDX[VNIDX.ticker == 'VNINDEX'][['date', 'close']].rename(columns={'close': 'close_p'})
        else:
            p = PANEL[PANEL.ticker == t][['date', 'close']].rename(columns={'close': 'close_p'})
        p = p[(p.date >= pd.Timestamp(START)) & (p.date <= pd.Timestamp(END))]
        res[t] = {
            'vnd_vs_panel_overlap': share(v.rename(columns={'close_v': 'c'}), p.rename(columns={'close_p': 'c2'})) if False else None,
            'vnd_vs_yahoo_adj': share(v, y.rename(columns={'close_y': 'close_y'}).assign(close_y=lambda x: x.close_y)) if False else None,
        }
        mv_p = v.merge(p, on='date'); mv_y = v.merge(y, on='date')
        res[t]['vnd_vs_panel'] = None if len(mv_p) == 0 else {
            'n': len(mv_p), 'within_0.5pct': round(float(((mv_p.close_v / mv_p.close_p - 1).abs() <= 0.005).mean()), 3),
            'max_pct': round(float((mv_p.close_v / mv_p.close_p - 1).abs().max() * 100), 2)}
        res[t]['vnd_vs_yahoo_adj'] = None if len(mv_y) == 0 else {
            'n': len(mv_y), 'within_0.5pct': round(float(((mv_y.close_v / mv_y.close_y - 1).abs() <= 0.005).mean()), 3),
            'max_pct': round(float((mv_y.close_v / mv_y.close_y - 1).abs().max() * 100), 2)}
        res[t].pop('vnd_vs_panel_overlap', None); res[t].pop('vnd_vs_yahoo_adj_tmp', None)
        res[t]['vnd_last'] = f"{v.date.max():%Y-%m-%d} {v.close_v.iloc[-1]}"
        time.sleep(0.3)
    (OUT / 'verify.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print('VERIFY ' + json.dumps(res, ensure_ascii=False))


if __name__ == '__main__':
    main()
