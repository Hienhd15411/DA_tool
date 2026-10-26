"""Fetch HOSE ticker list từ hardcoded config + metadata TCBS → dim_industry + dim_ticker.

vndirect finfo API bị chặn geo từ GitHub Actions runner → dùng list cứng
trong config.yml. Industry info lấy từ TCBS /ticker/overview endpoint (dùng
chung infra TCBS cho price + fundamentals → ít dependency).
"""
from __future__ import annotations
from datetime import date, datetime

from .utils import bulk_insert, date_key
from .vn_api import VnApi


def _parse_date(s) -> date | None:
    if not s:
        return None
    try:
        if isinstance(s, (int, float)):
            # Unix ts
            return datetime.fromtimestamp(s / 1000 if s > 1e12 else s).date()
        return datetime.fromisoformat(str(s)[:10]).date()
    except (ValueError, TypeError):
        return None


def _safe_int(v) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def run(conn, cfg: dict) -> tuple[int, int]:
    """Returns (n_industries, n_tickers)."""
    exchange = cfg["tickers"]["exchange"]
    limit = cfg["tickers"].get("limit")
    skip = set(cfg["tickers"].get("skip") or [])
    vn30 = set(cfg.get("vn30") or [])

    hardcoded = cfg["tickers"].get("hardcoded_list") or []
    tickers_list = sorted(set(hardcoded) - skip)
    if limit:
        tickers_list = tickers_list[: int(limit)]

    if not tickers_list:
        raise RuntimeError("Không có ticker trong config.tickers.hardcoded_list")

    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])
    api = VnApi(throttle_sec=throttle, max_retries=max_retries)

    print(f"[tickers] Fetching metadata for {len(tickers_list)} hardcoded tickers via TCBS...")

    enriched: list[dict] = []
    skip_meta = 0
    for i, ticker in enumerate(tickers_list, 1):
        meta = api.get_ticker_overview(ticker)
        api.throttle()

        if not meta:
            skip_meta += 1
            # Vẫn thêm với metadata rỗng để có mã trong dim_ticker
            enriched.append({
                "ticker": ticker,
                "name":   ticker,
                "industry": "Khác",
                "sector": None,
                "listed": None,
                "shares": None,
                "capital": None,
            })
            continue

        # TCBS overview response fields:
        # 'exchange', 'shortName', 'companyName', 'industry', 'industryEn',
        # 'establishedYear', 'noEmployees', 'noShareholders',
        # 'foreignPercent', 'outstandingShare', 'issueShare', ...
        enriched.append({
            "ticker": ticker,
            "name":   meta.get("companyName") or meta.get("shortName") or ticker,
            "industry": meta.get("industry") or meta.get("industryEn") or "Khác",
            "sector":   meta.get("industryEn"),  # fallback English name
            "listed":   _parse_date(meta.get("listingDate")),
            "shares":   _safe_int(meta.get("outstandingShare") or meta.get("issueShare")),
            "capital":  None,  # TCBS overview không có charter capital trực tiếp
        })

        if i % 20 == 0:
            print(f"  [tickers] {i}/{len(tickers_list)} metadata fetched "
                  f"({skip_meta} no-metadata)")

    print(f"[tickers] Metadata done: {len(enriched) - skip_meta} ok, {skip_meta} no-metadata")

    # dim_industry: unique list
    industries = sorted({t["industry"] for t in enriched if t["industry"]})
    sector_map: dict[str, str | None] = {}
    for t in enriched:
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
    for t in enriched:
        ind_id = industry_id_map.get(t["industry"])
        listed_date = t["listed"]
        listed_key = date_key(listed_date) if listed_date else None
        if listed_key is not None and listed_key not in valid_date_keys:
            listed_key = None

        ticker_rows.append((
            t["ticker"],
            str(t["name"])[:200],
            exchange,
            ind_id,
            listed_date,
            listed_key,
            t["shares"],
            t["capital"],
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
                "is_vn30 = EXCLUDED.is_vn30"
            ),
        )
    conn.commit()
    print(f"[tickers] dim_ticker: {len(ticker_rows)} rows.")
    return len(ind_rows), len(ticker_rows)
