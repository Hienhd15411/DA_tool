"""Fetch báo cáo tài chính quý → stock.fact_fundamental_quarterly.

vnstock Finance API:
  s.finance.income_statement(period='quarter', lang='en') → doanh thu, LN
  s.finance.balance_sheet(period='quarter', lang='en')    → tổng TS, VCSH, nợ
  s.finance.ratio(period='quarter', lang='en')            → EPS, ROE, ROA, D/E

Trả về DataFrame với MultiIndex columns thường, cần normalize cẩn thận.
"""
from __future__ import annotations
import time
from typing import Any

import pandas as pd

VND_SCALE = 1_000_000_000   # chuyển về tỷ VND để tránh overflow NUMERIC(18,2)


def _safe_num(x) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
        if pd.isna(v):
            return None
        return v
    except (TypeError, ValueError):
        return None


def _scale_vnd(x) -> float | None:
    v = _safe_num(x)
    return v / VND_SCALE if v is not None else None


def _flatten_cols(df: pd.DataFrame) -> pd.DataFrame:
    """vnstock sometimes returns MultiIndex columns — flatten."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [
            " ".join(str(x).strip() for x in c if x and str(x) != "nan").strip()
            for c in df.columns
        ]
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _pick_col(df_cols: list[str], *candidates: str) -> str | None:
    """Case-insensitive partial match."""
    lo = [c.lower() for c in df_cols]
    for cand in candidates:
        cl = cand.lower()
        for i, c in enumerate(lo):
            if cl in c:
                return df_cols[i]
    return None


def _fetch_one(ticker: str, source: str, period: str, lang: str,
               max_retries: int) -> dict | None:
    """Trả về dict {period_label: {metric: value}} hoặc None."""
    from vnstock import Vnstock  # type: ignore

    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            s = Vnstock().stock(symbol=ticker, source=source)
            inc = _flatten_cols(s.finance.income_statement(period=period, lang=lang))
            bs = _flatten_cols(s.finance.balance_sheet(period=period, lang=lang))
            ratio = _flatten_cols(s.finance.ratio(period=period, lang=lang))
            return {"income": inc, "balance": bs, "ratio": ratio}
        except Exception as e:
            last_err = e
            time.sleep(1.5 ** attempt)
    print(f"  [skip] {ticker}: {last_err}")
    return None


def _period_label(row: pd.Series, df: pd.DataFrame) -> tuple[int, int] | None:
    """Trích (year, quarter) từ 1 row BCTC."""
    y_col = _pick_col(list(df.columns), "year", "yearreport", "nam")
    q_col = _pick_col(list(df.columns), "quarter", "lengthreport", "quy")
    if y_col and q_col:
        y = _safe_num(row.get(y_col))
        q = _safe_num(row.get(q_col))
        if y and q and 1 <= q <= 4:
            return int(y), int(q)
    return None


def _extract_rows(ticker: str, data: dict, year_min: int, year_max: int) -> list[tuple[Any, ...]]:
    """Nối income + balance + ratio theo (year, quarter) → list tuples."""
    inc, bs, ratio = data["income"], data["balance"], data["ratio"]

    def to_dict(df: pd.DataFrame) -> dict[tuple[int, int], dict]:
        """Index by (year, quarter)."""
        out: dict[tuple[int, int], dict] = {}
        for _, r in df.iterrows():
            period = _period_label(r, df)
            if period is None:
                continue
            if not (year_min <= period[0] <= year_max):
                continue
            out[period] = r.to_dict()
        return out

    inc_map = to_dict(inc)
    bs_map = to_dict(bs)
    ratio_map = to_dict(ratio)

    all_periods = sorted(set(inc_map) | set(bs_map) | set(ratio_map))

    inc_cols = list(inc.columns)
    bs_cols = list(bs.columns)
    rat_cols = list(ratio.columns)

    col_rev = _pick_col(inc_cols, "Revenue", "Net Sales", "Doanh thu thuần", "Doanh thu")
    col_gp = _pick_col(inc_cols, "Gross Profit", "Lợi nhuận gộp")
    col_op = _pick_col(inc_cols, "Operating Profit", "LN thuần từ HĐKD", "Lợi nhuận hoạt động")
    col_pbt = _pick_col(inc_cols, "Profit before tax", "LN trước thuế")
    col_pat = _pick_col(inc_cols, "Attribute to parent", "Profit after tax",
                       "Net Profit", "LN sau thuế", "LNST")

    col_ta = _pick_col(bs_cols, "Total Assets", "Tổng tài sản")
    col_eq = _pick_col(bs_cols, "Owner's equity", "Shareholders equity",
                      "Equity", "Vốn chủ sở hữu")
    col_debt = _pick_col(bs_cols, "Total Liabilities", "Debt", "Nợ phải trả")

    col_eps = _pick_col(rat_cols, "EPS")
    col_bvps = _pick_col(rat_cols, "BVPS", "Book Value per Share")
    col_roe = _pick_col(rat_cols, "ROE")
    col_roa = _pick_col(rat_cols, "ROA")
    col_de = _pick_col(rat_cols, "Debt/Equity", "D/E", "Debt_Equity")

    rows: list[tuple[Any, ...]] = []
    for year, quarter in all_periods:
        inc_r = inc_map.get((year, quarter), {})
        bs_r = bs_map.get((year, quarter), {})
        rat_r = ratio_map.get((year, quarter), {})

        rows.append((
            ticker,
            f"{year}Q{quarter}",
            year,
            quarter,
            None,                                                   # report_date — vnstock không cung cấp ổn định
            _scale_vnd(inc_r.get(col_rev)) if col_rev else None,
            _scale_vnd(inc_r.get(col_gp)) if col_gp else None,
            _scale_vnd(inc_r.get(col_op)) if col_op else None,
            _scale_vnd(inc_r.get(col_pbt)) if col_pbt else None,
            _scale_vnd(inc_r.get(col_pat)) if col_pat else None,
            _scale_vnd(bs_r.get(col_ta)) if col_ta else None,
            _scale_vnd(bs_r.get(col_eq)) if col_eq else None,
            _scale_vnd(bs_r.get(col_debt)) if col_debt else None,
            _safe_num(rat_r.get(col_eps)) if col_eps else None,
            _safe_num(rat_r.get(col_bvps)) if col_bvps else None,
            _safe_num(rat_r.get(col_roe)) if col_roe else None,
            _safe_num(rat_r.get(col_roa)) if col_roa else None,
            _safe_num(rat_r.get(col_de)) if col_de else None,
        ))
    return rows


def run(conn, cfg: dict) -> int:
    source = cfg["vnstock"]["source"]
    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])
    period = cfg["fundamentals"]["period"]
    lang = cfg["fundamentals"]["lang"]

    # start_year từ config fundamentals.min_year (ưu tiên) hoặc từ dates.start
    cfg_fund_year = cfg["fundamentals"].get("min_year")
    start_year = int(cfg_fund_year) if cfg_fund_year else int(cfg["dates"]["start"][:4])
    end_year = int(cfg["dates"]["end"][:4])

    with conn.cursor() as cur:
        cur.execute("SELECT ticker FROM stock.dim_ticker WHERE is_active ORDER BY ticker")
        tickers = [t for (t,) in cur.fetchall()]

    print(f"[fund] Fetching fundamentals ({period}, {start_year}-{end_year}) "
          f"for {len(tickers)} tickers (throttle={throttle}s)...")

    total_rows = 0
    total_ok = 0
    skip_fetch = 0
    skip_empty = 0
    for i, ticker in enumerate(tickers, 1):
        data = _fetch_one(ticker, source, period, lang, max_retries)
        if data is None:
            skip_fetch += 1
            time.sleep(throttle)
            continue

        rows = _extract_rows(ticker, data, start_year, end_year)
        if not rows:
            skip_empty += 1
            time.sleep(throttle)
            continue

        with conn.cursor() as cur:
            from .utils import bulk_insert
            bulk_insert(
                cur, "stock.fact_fundamental_quarterly",
                ["ticker", "period", "year", "quarter", "report_date",
                 "revenue", "gross_profit", "operating_profit",
                 "profit_before_tax", "profit_after_tax",
                 "total_assets", "total_equity", "total_debt",
                 "eps", "bvps", "roe_pct", "roa_pct", "debt_to_equity"],
                rows,
                on_conflict=(
                    "(ticker, period) DO UPDATE SET "
                    "revenue = EXCLUDED.revenue, "
                    "gross_profit = EXCLUDED.gross_profit, "
                    "operating_profit = EXCLUDED.operating_profit, "
                    "profit_before_tax = EXCLUDED.profit_before_tax, "
                    "profit_after_tax = EXCLUDED.profit_after_tax, "
                    "total_assets = EXCLUDED.total_assets, "
                    "total_equity = EXCLUDED.total_equity, "
                    "total_debt = EXCLUDED.total_debt, "
                    "eps = EXCLUDED.eps, bvps = EXCLUDED.bvps, "
                    "roe_pct = EXCLUDED.roe_pct, roa_pct = EXCLUDED.roa_pct, "
                    "debt_to_equity = EXCLUDED.debt_to_equity"
                ),
            )
        conn.commit()
        total_rows += len(rows)
        total_ok += 1

        if i % 20 == 0:
            print(f"  [fund] {i}/{len(tickers)} done — "
                  f"{total_rows:,} rows, {total_ok} OK, "
                  f"{skip_fetch} fetch-fail, {skip_empty} empty")
        time.sleep(throttle)

    print(f"[fund] Finished: {total_ok}/{len(tickers)} tickers OK, {total_rows:,} rows.")
    print(f"  Skips: {skip_fetch} fetch-fail, {skip_empty} empty")
    return total_rows
