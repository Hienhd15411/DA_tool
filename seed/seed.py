#!/usr/bin/env python
"""Seed orchestrator.

Usage:
  # Apply all migrations + generate full dataset
  python seed.py --mode=full

  # Only run migrations (no data change)
  python seed.py --mode=migrate

  # Only generate data (assumes schema exists)
  python seed.py --mode=data

  # Drop all shopee data and re-seed (learning schema preserved)
  python seed.py --mode=reset
"""
from __future__ import annotations
import argparse
import os
import random
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from faker import Faker

from generators.utils import get_conn, transaction
from generators import (
    gen_dim_date, gen_dim_location, gen_dim_category,
    gen_dim_customer, gen_dim_seller, gen_dim_product,
    gen_dim_campaign, gen_dim_voucher,
    gen_fact_orders, gen_fact_shipment, gen_fact_returns,
    gen_fact_ad_spend, gen_fact_ad_performance,
    gen_fact_voucher_usage, gen_fact_traffic,
    gen_fact_inventory, gen_fact_cs_tickets,
)

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


def reset_shopee_data(conn):
    print("Dropping all shopee.* tables (learning schema preserved)...")
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA shopee CASCADE;")
        cur.execute("CREATE SCHEMA shopee;")
    conn.commit()


def generate_data(conn, cfg):
    rng = random.Random(cfg["seed"])
    Faker.seed(cfg["seed"])

    pipeline = [
        ("dim_date",               lambda: gen_dim_date.run(conn, cfg)),
        ("dim_location",           lambda: gen_dim_location.run(conn, cfg)),
        ("dim_category",           lambda: gen_dim_category.run(conn, cfg)),
        ("dim_customer",           lambda: gen_dim_customer.run(conn, cfg, rng)),
        ("dim_seller",             lambda: gen_dim_seller.run(conn, cfg, rng)),
        ("dim_product",            lambda: gen_dim_product.run(conn, cfg, rng)),
        ("dim_campaign",           lambda: gen_dim_campaign.run(conn, cfg, rng)),
        ("dim_voucher",            lambda: gen_dim_voucher.run(conn, cfg, rng)),
        ("fact_orders + items",    lambda: gen_fact_orders.run(conn, cfg, rng)),
        ("fact_shipment",          lambda: gen_fact_shipment.run(conn, cfg, rng)),
        ("fact_returns",           lambda: gen_fact_returns.run(conn, cfg, rng)),
        ("fact_ad_spend",          lambda: gen_fact_ad_spend.run(conn, cfg, rng)),
        ("fact_ad_performance",    lambda: gen_fact_ad_performance.run(conn, cfg, rng)),
        ("fact_voucher_usage",     lambda: gen_fact_voucher_usage.run(conn, cfg, rng)),
        ("fact_traffic_session",   lambda: gen_fact_traffic.run(conn, cfg, rng)),
        ("fact_inventory_weekly",  lambda: gen_fact_inventory.run(conn, cfg, rng)),
        ("fact_cs_ticket",         lambda: gen_fact_cs_tickets.run(conn, cfg, rng)),
    ]

    for name, fn in pipeline:
        print(f"\n[seed] {name} ...")
        n = fn()
        print(f"[seed] {name} ← {n:,} rows")


def main():
    load_dotenv()
    if not os.environ.get("DATABASE_URL"):
        sys.exit("ERROR: set DATABASE_URL in .env or environment")

    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["full", "migrate", "data", "reset"], default="full")
    args = ap.parse_args()

    cfg = load_config()
    conn = get_conn()

    try:
        if args.mode == "reset":
            reset_shopee_data(conn)
            apply_migrations(conn)
            generate_data(conn, cfg)
        elif args.mode == "migrate":
            apply_migrations(conn)
        elif args.mode == "data":
            generate_data(conn, cfg)
        else:  # full
            apply_migrations(conn)
            generate_data(conn, cfg)
    finally:
        conn.close()

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
