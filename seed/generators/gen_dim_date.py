"""Generate stock.dim_date — calendar 2024-2025 với flag ngày giao dịch VN."""
from __future__ import annotations
from datetime import date, datetime
from typing import Any

from .utils import bulk_insert, daterange, date_key

ENGLISH_MONTH = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
ENGLISH_DAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _parse_holidays(cfg: dict) -> dict[date, str]:
    """Trả về dict {date: holiday_name} từ config."""
    holidays: dict[date, str] = {}
    for _year, items in (cfg.get("holidays") or {}).items():
        for item in items or []:
            d = datetime.strptime(item["date"], "%Y-%m-%d").date()
            holidays[d] = item["name"]
    return holidays


def run(conn, cfg: dict) -> int:
    start = datetime.strptime(cfg["dates"]["start"], "%Y-%m-%d").date()
    end = datetime.strptime(cfg["dates"]["end"], "%Y-%m-%d").date()
    holidays = _parse_holidays(cfg)

    rows: list[tuple[Any, ...]] = []
    for d in daterange(start, end):
        dow = d.weekday()  # Mon=0..Sun=6
        is_weekend = dow >= 5
        is_holiday = d in holidays
        is_trading = not (is_weekend or is_holiday)
        rows.append((
            date_key(d),
            d,
            d.day,
            d.month,
            d.year,
            (d.month - 1) // 3 + 1,
            ENGLISH_MONTH[d.month - 1],
            dow + 1,                                # 1=Mon..7=Sun
            ENGLISH_DAY[dow],
            int(d.strftime("%V")),                  # ISO week
            is_weekend,
            is_trading,
            is_holiday,
            holidays.get(d),
            f"{d.year}Q{(d.month - 1) // 3 + 1}",
        ))

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "stock.dim_date",
            ["date_key", "full_date", "day", "month", "year", "quarter",
             "month_name", "day_of_week", "day_name", "week_of_year",
             "is_weekend", "is_trading_day", "is_holiday", "holiday_name",
             "fiscal_quarter"],
            rows,
            on_conflict="(date_key) DO NOTHING",
        )
    conn.commit()
    return n
