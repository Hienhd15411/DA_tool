"""Shared helpers for all generators."""
from __future__ import annotations
import os
import random
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterable, Iterator, Sequence, TypeVar

import psycopg2
from psycopg2.extras import execute_values

T = TypeVar("T")

VN_CITIES = [
    # (city, province, region, is_major)
    ("TP HCM",      "TP HCM",       "south",   True),
    ("Hà Nội",      "Hà Nội",       "north",   True),
    ("Đà Nẵng",     "Đà Nẵng",      "central", True),
    ("Hải Phòng",   "Hải Phòng",    "north",   True),
    ("Cần Thơ",     "Cần Thơ",      "south",   True),
    ("Biên Hoà",    "Đồng Nai",     "south",   False),
    ("Nha Trang",   "Khánh Hoà",    "central", False),
    ("Huế",         "Thừa Thiên Huế","central", False),
    ("Vũng Tàu",    "Bà Rịa - Vũng Tàu", "south", False),
    ("Bắc Ninh",    "Bắc Ninh",     "north",   False),
    ("Thủ Dầu Một", "Bình Dương",   "south",   False),
    ("Quy Nhơn",    "Bình Định",    "central", False),
    ("Buôn Ma Thuột","Đắk Lắk",     "central", False),
    ("Nam Định",    "Nam Định",     "north",   False),
    ("Thái Nguyên", "Thái Nguyên",  "north",   False),
    ("Vinh",        "Nghệ An",      "central", False),
    ("Long Xuyên",  "An Giang",     "south",   False),
    ("Mỹ Tho",      "Tiền Giang",   "south",   False),
    ("Rạch Giá",    "Kiên Giang",   "south",   False),
    ("Phan Thiết",  "Bình Thuận",   "central", False),
]


def get_conn(dsn: str | None = None):
    dsn = dsn or os.environ["DATABASE_URL"]
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    return conn


@contextmanager
def transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def bulk_insert(
    cur,
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence],
    on_conflict: str = "DO NOTHING",
    page_size: int = 1000,
) -> int:
    """Idempotent bulk insert. Returns count attempted."""
    cols = ", ".join(columns)
    stmt = f"INSERT INTO {table} ({cols}) VALUES %s ON CONFLICT {on_conflict}"
    rows_list = list(rows)
    if not rows_list:
        return 0
    execute_values(cur, stmt, rows_list, page_size=page_size)
    return len(rows_list)


def daterange(start: date, end: date) -> Iterator[date]:
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def date_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def pick_weighted(rng: random.Random, options: Sequence[tuple[T, float]]) -> T:
    """options: [(value, weight), ...]"""
    vals, weights = zip(*options)
    return rng.choices(vals, weights=weights, k=1)[0]


def chunked(seq: Iterable[T], n: int) -> Iterator[list[T]]:
    buf: list[T] = []
    for x in seq:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf


def hhmm(h: int, m: int = 0) -> timedelta:
    return timedelta(hours=h, minutes=m)


def peak_hour_distribution(rng: random.Random) -> int:
    """Trả giờ trong ngày (0-23) theo phân phối realistic: peak 20-22h, dip 2-5h."""
    weights = [
        # 0  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20 21 22 23
          2, 1, 1, 1, 1, 1, 2, 3, 4, 5, 6, 6, 8, 6, 5, 5, 5, 6, 7, 8, 10,11, 9, 5
    ]
    return rng.choices(range(24), weights=weights, k=1)[0]
