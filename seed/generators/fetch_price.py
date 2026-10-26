"""Fetch OHLCV daily cho mỗi ticker trong dim_ticker → stock.fact_price_daily.

Dùng TCBS public API endpoint stock-insight/v2/stock/bars-long-term.
"""
from __future__ import annotations
import time
from datetime import date, datetime
from typing import Any

from .utils import bulk_insert, date_key
from .vn_api import VnApi


def _normalize_bar(ticker: str, b: dict) -> tuple[Any, ...] | None:
    """Convert 1 bar dict → tuple cho insert. Trả None nếu invalid."""
    d = b.get("trade_date")
    o = b.get("open")
    h = b.get("high")
    lo = b.get("low")
    c = b.get("close")
    vol = b.get("volume")
    val = b.get("value")

    if not isinstance(d, date) or o is None or h is None or lo is None or c is None:
        return None
    try:
        o = float(o); h = float(h); lo = float(lo); c = float(c)
    except (TypeError, ValueError):
        return None

    if o <= 0 or h <= 0 or lo <= 0 or c <= 0:
        return None
    if h < lo:
        return None
    slack = 0.001 * h
    if c < lo - slack or c > h + slack:
        return None

    # Volume: None → 0, âm → 0
    try:
        v = int(vol) if vol is not None else 0
        volume = max(0, v)
    except (TypeError, ValueError):
        volume = 0

    # Trade value: None → None (nullable), âm → None
    trade_value = None
    try:
        if val is not None:
            vraw = int(val)
            trade_value = vraw if vraw >= 0 else None
    except (TypeError, ValueError):
        trade_value = None

    return (ticker, date_key(d), d, o, h, lo, c, volume, trade_value)


def run(conn, cfg: dict) -> int:
    start_date = datetime.strptime(cfg["dates"]["start"], "%Y-%m-%d").date()
    end_date = datetime.strptime(cfg["dates"]["end"], "%Y-%m-%d").date()
    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])
    api = VnApi(throttle_sec=throttle, max_retries=max_retries)

    with conn.cursor() as cur:
        cur.execute("SELECT ticker FROM stock.dim_ticker WHERE is_active ORDER BY ticker")
        tickers = [t for (t,) in cur.fetchall()]
        cur.execute("SELECT date_key FROM stock.dim_date")
        valid_date_keys = {k for (k,) in cur.fetchall()}

    print(f"[price] Fetching OHLCV for {len(tickers)} tickers "
          f"({start_date} → {end_date}, throttle={throttle}s)...")

    total_rows = 0
    total_ok = 0
    skip_fetch = 0
    skip_empty = 0
    for i, ticker in enumerate(tickers, 1):
        try:
            bars = api.get_bars(ticker, start_date, end_date, kind="stock")
        except Exception as e:
            print(f"  [skip] {ticker}: fetch err {type(e).__name__}: {str(e)[:120]}")
            skip_fetch += 1
            api.throttle()
            continue

        if not bars:
            skip_empty += 1
            api.throttle()
            continue

        rows: list[tuple[Any, ...]] = []
        for b in bars:
            norm = _normalize_bar(ticker, b)
            if norm and norm[1] in valid_date_keys:
                rows.append(norm)

        if not rows:
            skip_empty += 1
            api.throttle()
            continue

        with conn.cursor() as cur:
            bulk_insert(
                cur, "stock.fact_price_daily",
                ["ticker", "date_key", "trade_date",
                 "open_price", "high_price", "low_price", "close_price",
                 "volume", "trade_value"],
                rows,
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
        total_rows += len(rows)
        total_ok += 1

        if i % 20 == 0:
            print(f"  [price] {i}/{len(tickers)} done — "
                  f"{total_rows:,} rows, {total_ok} OK, "
                  f"{skip_fetch} fetch-fail, {skip_empty} empty")
        api.throttle()

    print(f"[price] Finished: {total_ok}/{len(tickers)} tickers OK, {total_rows:,} price rows.")
    print(f"  Skips: {skip_fetch} fetch-fail, {skip_empty} empty")
    return total_rows
