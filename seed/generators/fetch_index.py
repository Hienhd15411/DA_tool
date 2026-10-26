"""Fetch indices (VN-Index, VN30, HNX-Index) → stock.fact_index_daily.

Dùng TCBS bars-long-term endpoint với type=index.
"""
from __future__ import annotations
from datetime import datetime
from typing import Any

from .utils import bulk_insert, date_key
from .vn_api import VnApi


def run(conn, cfg: dict) -> int:
    indices = cfg.get("indices") or []
    if not indices:
        print("[index] Không có index nào trong config → skip.")
        return 0

    start_date = datetime.strptime(cfg["dates"]["start"], "%Y-%m-%d").date()
    end_date = datetime.strptime(cfg["dates"]["end"], "%Y-%m-%d").date()
    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])
    api = VnApi(throttle_sec=throttle, max_retries=max_retries)

    with conn.cursor() as cur:
        cur.execute("SELECT date_key FROM stock.dim_date")
        valid_date_keys = {k for (k,) in cur.fetchall()}

    print(f"[index] Fetching {len(indices)} indices "
          f"({start_date} → {end_date})...")

    total_rows = 0
    for idx in indices:
        code = idx["code"]
        try:
            bars = api.get_bars(code, start_date, end_date, kind="index")
        except Exception as e:
            print(f"  [skip] {code}: fetch err {type(e).__name__}: {str(e)[:120]}")
            api.throttle()
            continue

        if not bars:
            print(f"  [skip] {code}: no data")
            api.throttle()
            continue

        rows: list[tuple[Any, ...]] = []
        for b in bars:
            d = b.get("trade_date")
            o = b.get("open")
            c = b.get("close")
            if d is None or o is None or c is None:
                continue
            try:
                o = float(o); c = float(c)
                h = float(b["high"]) if b.get("high") is not None else None
                lo = float(b["low"]) if b.get("low") is not None else None
            except (TypeError, ValueError):
                continue
            if o <= 0 or c <= 0:
                continue
            vol = None
            if b.get("volume") is not None:
                try:
                    v = int(b["volume"])
                    vol = v if v >= 0 else None
                except (TypeError, ValueError):
                    vol = None
            val = None
            if b.get("value") is not None:
                try:
                    vv = int(b["value"])
                    val = vv if vv >= 0 else None
                except (TypeError, ValueError):
                    val = None

            dk = date_key(d)
            if dk not in valid_date_keys:
                continue
            rows.append((code, dk, d, o, h, lo, c, vol, val))

        if rows:
            with conn.cursor() as cur:
                bulk_insert(
                    cur, "stock.fact_index_daily",
                    ["index_code", "date_key", "trade_date",
                     "open_price", "high_price", "low_price", "close_price",
                     "volume", "trade_value"],
                    rows,
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
            total_rows += len(rows)
            print(f"  [index] {code} ← {len(rows):,} rows")
        else:
            print(f"  [index] {code}: 0 rows pass filter")

        api.throttle()

    print(f"[index] Finished: {total_rows:,} total rows.")
    return total_rows
