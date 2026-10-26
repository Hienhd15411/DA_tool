#!/usr/bin/env python
"""Seed orchestrator cho dataset chứng khoán VN (vnstock → Supabase).

Usage:
  # Full: migrations + fetch tickers + price + fundamentals
  python seed.py --mode=full

  # Chỉ chạy migrations (không fetch data)
  python seed.py --mode=migrate

  # Chỉ fetch data (giả định schema đã có)
  python seed.py --mode=data

  # Drop toàn bộ stock + chạy lại từ đầu (learning schema giữ nguyên)
  python seed.py --mode=reset

  # Chỉ fetch price daily (bỏ qua tickers + fundamentals — nhanh cho refresh)
  python seed.py --mode=price-only
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from generators.utils import get_conn
from generators import gen_dim_date, fetch_tickers, fetch_price, fetch_fundamental, fetch_index

ROOT = Path(__file__).parent
MIGRATIONS = ROOT / "migrations"


def load_config():
    with open(ROOT / "config.yml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def apply_migrations(conn):
    files = sorted(MIGRATIONS.glob("*.sql"))
    print(f"Applying {len(files)} migrations...")
    with conn.cursor() as cur:
        for f in files:
            print(f"  → {f.name}")
            cur.execute(f.read_text(encoding="utf-8"))
    conn.commit()


def reset_stock_data(conn):
    print("Dropping stock schema (learning preserved)...")
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS stock CASCADE;")
        cur.execute("CREATE SCHEMA stock;")
    conn.commit()


def generate_data(conn, cfg, *, skip_tickers=False, skip_fundamental=False, skip_index=False):
    print("\n[seed] dim_date...")
    n = gen_dim_date.run(conn, cfg)
    print(f"[seed] dim_date ← {n:,} rows")

    if not skip_tickers:
        print("\n[seed] dim_industry + dim_ticker (via vnstock)...")
        n_ind, n_tick = fetch_tickers.run(conn, cfg)
        print(f"[seed] dim_industry ← {n_ind} rows, dim_ticker ← {n_tick} rows")

    print("\n[seed] fact_price_daily (via vnstock OHLCV)...")
    n_price = fetch_price.run(conn, cfg)
    print(f"[seed] fact_price_daily ← {n_price:,} rows")

    if not skip_index:
        print("\n[seed] fact_index_daily (VN-Index + benchmarks)...")
        n_idx = fetch_index.run(conn, cfg)
        print(f"[seed] fact_index_daily ← {n_idx:,} rows")

    if not skip_fundamental:
        print("\n[seed] fact_fundamental_quarterly (via vnstock BCTC)...")
        n_fund = fetch_fundamental.run(conn, cfg)
        print(f"[seed] fact_fundamental_quarterly ← {n_fund:,} rows")

    # ANALYZE to refresh planner stats + n_live_tup cho get_schema_info
    print("\n[seed] ANALYZE stock.* ...")
    conn.commit()
    old_autocommit = conn.autocommit
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(
            "SELECT schemaname || '.' || tablename "
            "FROM pg_tables WHERE schemaname = 'stock' ORDER BY tablename"
        )
        for (fq,) in cur.fetchall():
            cur.execute(f"ANALYZE {fq}")
    conn.autocommit = old_autocommit


def main():
    load_dotenv()
    if not os.environ.get("DATABASE_URL"):
        sys.exit("ERROR: set DATABASE_URL in .env or environment")

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--mode",
        choices=["full", "migrate", "data", "reset", "price-only", "price-and-index"],
        default="full",
    )
    args = ap.parse_args()

    cfg = load_config()
    conn = get_conn()

    try:
        if args.mode == "reset":
            reset_stock_data(conn)
            apply_migrations(conn)
            generate_data(conn, cfg)
        elif args.mode == "migrate":
            apply_migrations(conn)
        elif args.mode == "data":
            generate_data(conn, cfg)
        elif args.mode == "price-only":
            generate_data(conn, cfg, skip_tickers=True, skip_fundamental=True, skip_index=True)
        elif args.mode == "price-and-index":
            generate_data(conn, cfg, skip_tickers=True, skip_fundamental=True)
        else:  # full
            apply_migrations(conn)
            generate_data(conn, cfg)
    finally:
        conn.close()

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
