"""Fetch OHLCV daily cho mỗi ticker trong dim_ticker → stock.fact_price_daily.

vnstock sometimes returns None, raises network errors, or returns partial data.
Defensive: retry per-ticker, skip on failure, continue."""
from __future__ import annotations
import time
from typing import Any

import pandas as pd

from .utils import bulk_insert, date_key


def _fetch_history(ticker: str, start: str, end: str, source: str,
                   interval: str, max_retries: int) -> pd.DataFrame | None:
    from vnstock import Vnstock  # type: ignore

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            s = Vnstock().stock(symbol=ticker, source=source)
            df = s.quote.history(start=start, end=end, interval=interval)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:
            last_err = e
            time.sleep(1.5 ** attempt)
    print(f"  [skip] {ticker}: {last_err}")
    return None


def _normalize(df: pd.DataFrame) -> list[tuple[Any, ...]]:
    """Normalize vnstock OHLCV DataFrame → list of tuples cho insert.

    Columns thường gặp: time/date, open, high, low, close, volume, value
    """
    cols_lower = {c.lower(): c for c in df.columns}

    def pick(*candidates: str) -> str | None:
        for c in candidates:
            if c.lower() in cols_lower:
                return cols_lower[c.lower()]
        return None

    col_date = pick("time", "date", "trading_date")
    col_open = pick("open", "openprice")
    col_high = pick("high", "highprice")
    col_low = pick("low", "lowprice")
    col_close = pick("close", "closeprice", "adjust_close")
    col_vol = pick("volume", "totalvolume")
    col_val = pick("value", "totalvalue", "trade_value")

    required = [col_date, col_open, col_high, col_low, col_close, col_vol]
    if any(c is None for c in required):
        return []

    df = df.copy()
    df[col_date] = pd.to_datetime(df[col_date], errors="coerce").dt.date
    df = df.dropna(subset=[col_date])

    out: list[tuple[Any, ...]] = []
    for _, r in df.iterrows():
        d = r[col_date]
        out.append((
            None,                                  # ticker — fill ngoài
            date_key(d),
            d,
            float(r[col_open]),
            float(r[col_high]),
            float(r[col_low]),
            float(r[col_close]),
            int(r[col_vol]) if pd.notna(r[col_vol]) else 0,
            int(r[col_val]) if col_val and pd.notna(r[col_val]) else None,
        ))
    return out


def run(conn, cfg: dict) -> int:
    start = cfg["dates"]["start"]
    end = cfg["dates"]["end"]
    source = cfg["vnstock"]["source"]
    interval = cfg["vnstock"]["interval"]
    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])

    with conn.cursor() as cur:
        cur.execute("SELECT ticker FROM stock.dim_ticker WHERE is_active ORDER BY ticker")
        tickers = [t for (t,) in cur.fetchall()]
        cur.execute("SELECT date_key FROM stock.dim_date")
        valid_date_keys = {k for (k,) in cur.fetchall()}

    print(f"[price] Fetching OHLCV for {len(tickers)} tickers "
          f"({start} → {end}, source={source})...")

    total_rows = 0
    total_ok = 0
    for i, ticker in enumerate(tickers, 1):
        df = _fetch_history(ticker, start, end, source, interval, max_retries)
        if df is None:
            time.sleep(throttle)
            continue

        rows = _normalize(df)
        if not rows:
            print(f"  [skip] {ticker}: unexpected columns {list(df.columns)}")
            time.sleep(throttle)
            continue

        # Fill ticker + filter by valid_date_keys
        filled = [
            (ticker, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8])
            for r in rows if r[1] in valid_date_keys
        ]

        if filled:
            with conn.cursor() as cur:
                bulk_insert(
                    cur, "stock.fact_price_daily",
                    ["ticker", "date_key", "trade_date",
                     "open_price", "high_price", "low_price", "close_price",
                     "volume", "trade_value"],
                    filled,
                    on_conflict=(
                        "(ticker, date_key) DO UPDATE SET "
                        "open_price = EXCLUDED.open_price, "
                        "high_price = EXCLUDED.high_price, "
                        "low_price = EXCLUDED.low_price, "
                        "close_price = EXCLUDED.close_price, "
                        "volume = EXCLUDED.volume, "
                        "trade_value = EXCLUDED.trade_value"
                    ),
                    page_size=500,
                )
            conn.commit()
            total_rows += len(filled)
            total_ok += 1

        if i % 20 == 0:
            print(f"  [price] {i}/{len(tickers)} done — {total_rows:,} rows")
        time.sleep(throttle)

    print(f"[price] Finished: {total_ok}/{len(tickers)} tickers OK, {total_rows:,} price rows.")
    return total_rows
