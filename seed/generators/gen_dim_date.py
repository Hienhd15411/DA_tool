"""Generate dim_date covering config range (+1 month buffer for future dates)."""
from __future__ import annotations
from datetime import date, timedelta
from .utils import bulk_insert, daterange, date_key

MONTH_NAMES = ["", "January","February","March","April","May","June",
               "July","August","September","October","November","December"]
DAY_NAMES = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]


def run(conn, cfg):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"]) + timedelta(days=90)   # buffer tương lai
    # Buffer quá khứ đủ rộng để cover customer signup (730 days) + seller join (1200 days)
    start = start - timedelta(days=1500)

    sale_days = {date.fromisoformat(s) for s in cfg["dates"]["sale_days"]}
    holidays  = {date.fromisoformat(s) for s in cfg["dates"]["holidays"]}
    payday_d  = set(cfg["dates"]["payday"])

    rows = []
    for d in daterange(start, end):
        dow = d.isoweekday()  # 1..7
        is_payday = d.day in payday_d
        is_sale   = d in sale_days or (d.day == d.month)  # coincidence 3/3, 4/4, 5/5...
        rows.append((
            date_key(d), d,
            d.day, d.month, d.year, (d.month - 1) // 3 + 1,
            MONTH_NAMES[d.month], dow, DAY_NAMES[dow - 1],
            d.isocalendar()[1],
            dow >= 6,
            d in holidays,
            is_sale or is_payday,
            f"{d.year}-Q{(d.month - 1) // 3 + 1}",
        ))

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.dim_date",
            ["date_key","full_date","day","month","year","quarter",
             "month_name","day_of_week","day_name","week_of_year",
             "is_weekend","is_holiday","is_sale_day","fiscal_period"],
            rows,
            on_conflict="(date_key) DO NOTHING",
        )
    conn.commit()
    return n
