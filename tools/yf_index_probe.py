"""Thử các mã Yahoo cho VN-Index, đối chiếu với engine/data/seed/vnindex.parquet (01–10/07/2026)."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
REF = pd.read_parquet(ROOT / 'engine' / 'data' / 'seed' / 'vnindex.parquet')
REF = REF[(REF.date >= '2026-07-01') & (REF.date <= '2026-07-10')][['date', 'close']]
CANDIDATES = ['^VNINDEX', 'VNINDEX.VN', '^VNI', 'VNINDEX', '^VNINDEX.VN', 'E1VFVN30.VN']

for sym in CANDIDATES:
    try:
        h = yf.Ticker(sym).history(start='2026-07-01', end='2026-10-28', auto_adjust=True)
    except Exception as e:
        print(sym, 'ERR', type(e).__name__, str(e)[:120]); continue
    if h is None or h.empty:
        print(sym, 'NO DATA'); continue
    h = h.reset_index()
    h['date'] = pd.to_datetime(h['Date']).dt.tz_localize(None).dt.normalize()
    m = REF.merge(h[['date', 'Close']], on='date')
    diff = ((m['Close'] / m['close'] - 1).abs() * 100) if len(m) else pd.Series(dtype=float)
    info = {'rows': len(h), 'first': str(h.date.min().date()), 'last': str(h.date.max().date()),
            'last_close': round(float(h.Close.iloc[-1]), 2), 'overlap': len(m),
            'overlap_max_pct': round(float(diff.max()), 3) if len(m) else None,
            'overlap_mean_pct': round(float(diff.mean()), 3) if len(m) else None}
    print('RESULT', sym, json.dumps(info, ensure_ascii=False))
