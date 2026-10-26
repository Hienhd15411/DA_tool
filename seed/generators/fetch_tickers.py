"""Fetch HOSE ticker list + metadata → stock.dim_industry + stock.dim_ticker.

Dùng vndirect finfo API (listing) + TCBS ticker overview (metadata chi tiết).
"""
from __future__ import annotations
from datetime import date, datetime

from .utils import bulk_insert, date_key
from .vn_api import VnApi


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s)[:10]).date()
    except (ValueError, TypeError):
        return None


def run(conn, cfg: dict) -> tuple[int, int]:
    """Returns (n_industries, n_tickers)."""
    exchange = cfg["tickers"]["exchange"]
    limit = cfg["tickers"].get("limit")
    skip = set(cfg["tickers"].get("skip") or [])
    vn30 = set(cfg.get("vn30") or [])

    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])
    api = VnApi(throttle_sec=throttle, max_retries=max_retries)

    print(f"[tickers] Fetching listing from vndirect (exchange={exchange})...")
    raw = api.list_tickers_hose()
    if not raw:
        raise RuntimeError("vndirect listing API trả rỗng — kiểm tra endpoint.")

    # Normalize + filter 3-char tickers (chuẩn HOSE)
    tickers_raw: list[dict] = []
    for r in raw:
        sym = str(r.get("symbol", "")).upper()
        if len(sym) != 3 or sym in skip:
            continue
        tickers_raw.append({
            "ticker":    sym,
            "name":      r.get("companyName") or r.get("companyNameEng") or sym,
            "industry":  r.get("icbName3") or r.get("icbName2") or r.get("icbName1") or "Khác",
            "sector":    r.get("icbName1"),
            "listed":    _parse_date(r.get("listingDate")),
            "shares":    r.get("outstandingShares"),
            "capital":   r.get("charterCapital"),
        })

    if limit:
        tickers_raw = tickers_raw[: int(limit)]
    print(f"[tickers] After filter: {len(tickers_raw)} tickers.")

    # dim_industry: unique list
    industries = sorted({t["industry"] for t in tickers_raw if t["industry"]})
    sector_map: dict[str, str | None] = {}
    for t in tickers_raw:
        ind = t["industry"]
        if ind and ind not in sector_map:
            sector_map[ind] = t["sector"]

    ind_rows = [(name, sector_map.get(name)) for name in industries]
    with conn.cursor() as cur:
        bulk_insert(
            cur, "stock.dim_industry",
            ["industry_name", "sector"],
            ind_rows,
            on_conflict="(industry_name) DO UPDATE SET sector = EXCLUDED.sector",
        )
        cur.execute("SELECT industry_name, industry_id FROM stock.dim_industry")
        industry_id_map = dict(cur.fetchall())
    conn.commit()
    print(f"[tickers] dim_industry: {len(ind_rows)} rows.")

    # dim_ticker
    with conn.cursor() as cur:
        cur.execute("SELECT date_key FROM stock.dim_date")
        valid_date_keys = {k for (k,) in cur.fetchall()}

    ticker_rows = []
    for t in tickers_raw:
        ind_id = industry_id_map.get(t["industry"])
        listed_date = t["listed"]
        listed_key = date_key(listed_date) if listed_date else None
        if listed_key is not None and listed_key not in valid_date_keys:
            listed_key = None     # FK sẽ fail → set NULL
        try:
            shares_int = int(t["shares"]) if t["shares"] is not None else None
        except (TypeError, ValueError):
            shares_int = None
        try:
            cap_int = int(t["capital"]) if t["capital"] is not None else None
        except (TypeError, ValueError):
            cap_int = None

        ticker_rows.append((
            t["ticker"],
            str(t["name"])[:200],
            exchange,
            ind_id,
            listed_date,
            listed_key,
            shares_int,
            cap_int,
            t["ticker"] in vn30,
            True,
        ))

    with conn.cursor() as cur:
        bulk_insert(
            cur, "stock.dim_ticker",
            ["ticker", "company_name", "exchange", "industry_id",
             "listed_date", "listed_date_key", "outstanding_shares",
             "charter_capital", "is_vn30", "is_active"],
            ticker_rows,
            on_conflict=(
                "(ticker) DO UPDATE SET "
                "company_name = EXCLUDED.company_name, "
                "industry_id = EXCLUDED.industry_id, "
                "outstanding_shares = EXCLUDED.outstanding_shares, "
                "charter_capital = EXCLUDED.charter_capital, "
                "is_vn30 = EXCLUDED.is_vn30"
            ),
        )
    conn.commit()
    print(f"[tickers] dim_ticker: {len(ticker_rows)} rows.")
    return len(ind_rows), len(ticker_rows)
