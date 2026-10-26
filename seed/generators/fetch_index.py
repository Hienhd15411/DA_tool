"""Fetch indices (VN-Index, VN30, HNX-Index) → stock.fact_index_daily.

Spec yêu cầu VN-Index làm benchmark cho đánh giá rổ 10 mã.
"""
from __future__ import annotations
import time
from typing import Any

import pandas as pd

from .utils import bulk_insert, date_key


def _fetch_history(code: str, source: str, start: str, end: str,
                   interval: str, max_retries: int) -> pd.DataFrame | None:
    from vnstock import Vnstock  # type: ignore

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            # VNINDEX / VN30 / HNXINDEX được treat như symbol đặc biệt trong VCI
            s = Vnstock().stock(symbol=code, source=source)
            df = s.quote.history(start=start, end=end, interval=interval)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:
            last_err = e
            time.sleep(1.5 ** attempt)
    print(f"  [skip] {code}: {last_err}")
    return None


def _normalize(df: pd.DataFrame) -> list[tuple[Any, ...]]:
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
    col_close = pick("close", "closeprice")
    col_vol = pick("volume", "totalvolume")
    col_val = pick("value", "totalvalue", "trade_value")

    required = [col_date, col_open, col_close]
    if any(c is None for c in required):
        return []

    df = df.copy()
    df[col_date] = pd.to_datetime(df[col_date], errors="coerce").dt.date
    df = df.dropna(subset=[col_date, col_open, col_close])

    out: list[tuple[Any, ...]] = []
    for _, r in df.iterrows():
        d = r[col_date]
        try:
            o = float(r[col_open])
            c = float(r[col_close])
            if o <= 0 or c <= 0 or pd.isna(o) or pd.isna(c):
                continue
            h = float(r[col_high]) if col_high and pd.notna(r[col_high]) else None
            lo = float(r[col_low]) if col_low and pd.notna(r[col_low]) else None
            vol = int(r[col_vol]) if col_vol and pd.notna(r[col_vol]) and r[col_vol] >= 0 else None
            val = int(r[col_val]) if col_val and pd.notna(r[col_val]) and r[col_val] >= 0 else None
        except (TypeError, ValueError):
            continue
        out.append((None, date_key(d), d, o, h, lo, c, vol, val))
    return out


def run(conn, cfg: dict) -> int:
    indices = cfg.get("indices") or []
    if not indices:
        print("[index] Không có index nào trong config → skip.")
        return 0

    start = cfg["dates"]["start"]
    end = cfg["dates"]["end"]
    interval = cfg["vnstock"]["interval"]
    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])

    with conn.cursor() as cur:
        cur.execute("SELECT date_key FROM stock.dim_date")
        valid_date_keys = {k for (k,) in cur.fetchall()}

    print(f"[index] Fetching {len(indices)} indices ({start} → {end})...")

    total_rows = 0
    for idx in indices:
        code = idx["code"]
        source = idx.get("source") or cfg["vnstock"]["source"]
        df = _fetch_history(code, source, start, end, interval, max_retries)
        if df is None or df.empty:
            print(f"  [skip] {code}: no data")
            time.sleep(throttle)
            continue

        raw_rows = _normalize(df)
        if not raw_rows:
            print(f"  [skip] {code}: unexpected columns {list(df.columns)}")
            time.sleep(throttle)
            continue

        filled = [
            (code, r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8])
            for r in raw_rows if r[1] in valid_date_keys
        ]

        if filled:
            with conn.cursor() as cur:
                bulk_insert(
                    cur, "stock.fact_index_daily",
                    ["index_code", "date_key", "trade_date",
                     "open_price", "high_price", "low_price", "close_price",
                     "volume", "trade_value"],
                    filled,
                    on_conflict=(
                        "(index_code, date_key) DO UPDATE SET "
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
            print(f"  [index] {code} ← {len(filled):,} rows")
        else:
            print(f"  [index] {code}: 0 rows pass date_key filter")

        time.sleep(throttle)

    print(f"[index] Finished: {total_rows:,} total rows.")
    return total_rows
