"""Kéo VCI 2026-07-01 → hôm nay cho toàn bộ mã trong panel 2026-07-10 + VNINDEX.
Ghi candidate CSV (định dạng inbox) + kiểm tra chồng lấn với panel. KHÔNG upload Supabase."""
from __future__ import annotations
import datetime as dt, json, time
from pathlib import Path
import pandas as pd, requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools' / 'out' / 'vci_update'
PANEL = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet')
VNIDX = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'vnindex.parquet')
START, END = dt.date(2026, 7, 1), dt.date.today()
OVL_END = pd.Timestamp('2026-07-10')
TICKERS = sorted(PANEL[PANEL.date == OVL_END].ticker.unique().tolist()) + ['VNINDEX']
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120 Safari/537.36',
     'Content-Type': 'application/json', 'Origin': 'https://trading.vietcap.com.vn',
     'Referer': 'https://trading.vietcap.com.vn/'}
ts = lambda d: int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def vci(sym):
    n = len(pd.bdate_range(START, END)) + 1
    r = requests.post('https://trading.vietcap.com.vn/api/chart/OHLCChart/gap-chart', headers=H, timeout=30,
                      json={'timeFrame': 'ONE_DAY', 'symbols': [sym], 'to': ts(END) + 86400, 'countBack': n})
    if r.status_code != 200:
        raise RuntimeError(f'HTTP {r.status_code}')
    x = r.json(); x = x[0] if isinstance(x, list) else x['data'][0]
    d = pd.DataFrame({'t': x['t'], 'open': x['o'], 'high': x['h'], 'low': x['l'], 'close': x['c'], 'volume': x['v']})
    d['date'] = pd.to_datetime(d['t'].astype('int64'), unit='s').dt.normalize()
    d = d[d.date >= pd.Timestamp(START)]
    if sym == 'VNINDEX':
        return d[['date', 'open', 'high', 'low', 'close', 'volume']]
    # VCI: VND → nghìn đồng (khớp panel)
    for c in ['open', 'high', 'low', 'close']:
        d[c] = d[c] / 1000.0
    return d[['date', 'open', 'high', 'low', 'close', 'volume']]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    frames, fail, ovl = [], [], {}
    for i, t in enumerate(TICKERS, 1):
        try:
            d = vci(t)
        except Exception as e:
            fail.append(f'{t}:{str(e)[:60]}'); time.sleep(0.3); continue
        d.insert(0, 'ticker', t)
        d['gt_khop'] = d['close'] * d['volume'] * 1000 if t != 'VNINDEX' else pd.NA
        frames.append(d)
        ref = VNIDX[VNIDX.ticker == 'VNINDEX'] if t == 'VNINDEX' else PANEL[PANEL.ticker == t]
        ref = ref[ref.date == OVL_END]
        if len(ref):
            r = float(d[d.date == OVL_END].close.iloc[0] / ref.close.iloc[0]) if (d.date == OVL_END).any() else None
            ovl[t] = r
        time.sleep(0.3)
    all_ = pd.concat(frames)
    all_.to_csv(OUT / 'inbox_candidate.csv', index=False, encoding='utf-8')
    ratios = pd.Series({k: v for k, v in ovl.items() if v is not None and k != 'VNINDEX'}, dtype=float)
    rep = {'tickers': len(TICKERS), 'ok': len(frames), 'fail': fail,
           'rows': int(len(all_)), 'date_min': str(all_.date.min().date()), 'date_max': str(all_.date.max().date()),
           'overlap_0710_ratio_within_0.5pct': int(((ratios - 1).abs() <= 0.005).sum()),
           'overlap_0710_ratio_outside_0.5pct': int(((ratios - 1).abs() > 0.005).sum()),
           'index_0710_ratio': ovl.get('VNINDEX')}
    (OUT / 'report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    print('VCIUPD ' + json.dumps(rep, ensure_ascii=False))


if __name__ == '__main__':
    main()
