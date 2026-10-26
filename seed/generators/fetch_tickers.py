"""Fetch HOSE ticker list + metadata → stock.dim_industry + stock.dim_ticker.

Uses vnstock Listing API. Tolerant to vnstock version differences.
"""
from __future__ import annotations
from datetime import date

import pandas as pd

from .utils import bulk_insert, date_key


def _fetch_listing(exchange: str = "HSX") -> pd.DataFrame:
    """Lấy danh sách tất cả mã trên 1 sàn. Trả DataFrame với các cột
    ticker, organ_name, industry, listed_date, charter_capital...

    vnstock API đổi khá nhiều giữa các phiên bản — thử nhiều cách."""
    from vnstock import Vnstock  # type: ignore

    # Pick 1 ticker đại diện để init client (vnstock bắt buộc symbol khi stock())
    s = Vnstock().stock(symbol="VNM", source="VCI")

    df: pd.DataFrame | None = None

    # Try method 1: listing.symbols_by_exchange
    for method_name in ("symbols_by_exchange", "all_symbols", "symbols_by_group"):
        if hasattr(s.listing, method_name):
            try:
                raw = getattr(s.listing, method_name)()
                if isinstance(raw, pd.DataFrame) and not raw.empty:
                    df = raw
                    break
            except Exception as e:
                print(f"  [warn] listing.{method_name}() failed: {e}")

    if df is None or df.empty:
        raise RuntimeError("vnstock Listing API trả rỗng. Check vnstock version.")

    # Normalize column names (vnstock dùng khá tuỳ tiện)
    cols_lower = {c.lower(): c for c in df.columns}

    def pick(*candidates: str) -> str | None:
        for c in candidates:
            if c.lower() in cols_lower:
                return cols_lower[c.lower()]
        return None

    col_symbol = pick("symbol", "ticker", "ma_ck")
    col_name = pick("organ_name", "company_name", "company", "ten_cong_ty")
    col_exchange = pick("exchange", "comGroupCode", "san")
    col_industry = pick("icb_name3", "industry", "nganh", "icb_name_lv3", "icb_name2")
    col_industry2 = pick("icb_name1", "sector", "icb_name_lv1", "nhom_nganh")
    col_listed = pick("listing_date", "listed_date", "ngay_niem_yet")
    col_shares = pick("outstanding_share", "outstanding_shares", "cp_luu_hanh")
    col_capital = pick("charter_capital", "von_dieu_le")

    if not col_symbol:
        raise RuntimeError(f"Không tìm thấy cột ticker trong listing. Columns: {list(df.columns)}")

    # Filter theo exchange nếu có cột
    if col_exchange:
        df = df[df[col_exchange].astype(str).str.upper().isin([exchange.upper(), "HOSE", "HSX"])]

    # Keep rows với ticker 3 ký tự (chuẩn HOSE/HNX)
    df = df[df[col_symbol].astype(str).str.len() == 3].copy()
    df["_ticker"] = df[col_symbol].astype(str).str.upper()
    df["_name"] = df[col_name].astype(str) if col_name else df["_ticker"]
    df["_industry"] = df[col_industry].astype(str) if col_industry else "Khác"
    df["_sector"] = df[col_industry2].astype(str) if col_industry2 else None
    df["_listed"] = pd.to_datetime(df[col_listed], errors="coerce").dt.date if col_listed else None
    df["_shares"] = pd.to_numeric(df[col_shares], errors="coerce") if col_shares else None
    df["_capital"] = pd.to_numeric(df[col_capital], errors="coerce") if col_capital else None

    df = df.drop_duplicates(subset=["_ticker"]).reset_index(drop=True)
    return df


def run(conn, cfg: dict) -> tuple[int, int]:
    """Returns (n_industries, n_tickers)."""
    exchange = cfg["tickers"]["exchange"]
    limit = cfg["tickers"].get("limit")
    skip = set(cfg["tickers"].get("skip") or [])
    vn30 = set(cfg.get("vn30") or [])

    print(f"[tickers] Fetching listing from vnstock (exchange={exchange})...")
    df = _fetch_listing(exchange)
    print(f"[tickers] Got {len(df)} raw tickers.")

    # Filter + limit
    df = df[~df["_ticker"].isin(skip)]
    if limit:
        df = df.head(int(limit))
    print(f"[tickers] After filter: {len(df)} tickers.")

    # dim_industry: unique list
    industries = sorted(df["_industry"].dropna().unique().tolist())
    sector_map = (
        df.dropna(subset=["_industry"])
          .drop_duplicates(subset=["_industry"])
          .set_index("_industry")["_sector"]
          .to_dict()
    )

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
    ticker_rows = []
    for _, r in df.iterrows():
        ind_id = industry_id_map.get(r["_industry"])
        listed_date = r["_listed"] if isinstance(r["_listed"], date) else None
        listed_key = date_key(listed_date) if listed_date else None
        ticker_rows.append((
            r["_ticker"],
            (r["_name"] or r["_ticker"])[:200],
            exchange,
            ind_id,
            listed_date,
            listed_key,
            int(r["_shares"]) if pd.notna(r["_shares"]) else None,
            int(r["_capital"]) if pd.notna(r["_capital"]) else None,
            r["_ticker"] in vn30,
            True,
        ))

    with conn.cursor() as cur:
        # dim_ticker FK listed_date_key → dim_date. Nếu listed_date trước dim_date range
        # (VNM niêm yết 2006), FK sẽ fail → set NULL.
        cur.execute("SELECT date_key FROM stock.dim_date")
        valid_date_keys = {k for (k,) in cur.fetchall()}
        ticker_rows = [
            (t[0], t[1], t[2], t[3], t[4],
             t[5] if t[5] in valid_date_keys else None,
             t[6], t[7], t[8], t[9])
            for t in ticker_rows
        ]
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
