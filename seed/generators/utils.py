"""Shared helpers for all generators."""
from __future__ import annotations
import os
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Iterable, Iterator, Sequence, TypeVar

import psycopg2
from psycopg2.extras import execute_values

T = TypeVar("T")


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


def chunked(seq: Iterable[T], n: int) -> Iterator[list[T]]:
    buf: list[T] = []
    for x in seq:
        buf.append(x)
        if len(buf) >= n:
            yield buf
            buf = []
    if buf:
        yield buf
