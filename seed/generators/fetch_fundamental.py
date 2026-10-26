"""Fetch báo cáo tài chính quý → stock.fact_fundamental_quarterly.

Dùng TCBS public API:
  /tcanalysis/v1/finance/{ticker}/incomestatement
  /tcanalysis/v1/finance/{ticker}/balancesheet
  /tcanalysis/v1/finance/{ticker}/financialratio

Response là list rows, mỗi row 1 kỳ báo cáo với keys như:
  year, quarter, revenue, grossProfit, operationProfit, postTaxProfit,
  totalAssets, totalEquity, totalDebt, eps, bvps, roe, roa, ...
"""
from __future__ import annotations
from typing import Any

from .utils import bulk_insert
from .vn_api import VnApi

VND_SCALE = 1_000_000_000   # chuyển về tỷ VND để tránh overflow NUMERIC(18,2)


def _safe_num(x) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
        if v != v:   # NaN check
            return None
        return v
    except (TypeError, ValueError):
        return None


def _scale_vnd(x) -> float | None:
    v = _safe_num(x)
    return v / VND_SCALE if v is not None else None


def _pick(d: dict, *keys: str) -> Any:
    """Case-sensitive first-match pick."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _period_key(row: dict) -> tuple[int, int] | None:
    y = row.get("year")
    q = row.get("quarter")
    if y is None or q is None:
        return None
    try:
        y, q = int(y), int(q)
    except (TypeError, ValueError):
        return None
    if not (1 <= q <= 4):
        return None
    return (y, q)


def _extract_rows(ticker: str, income: list[dict], balance: list[dict],
                  ratio: list[dict], year_min: int, year_max: int) -> list[tuple[Any, ...]]:
    """Nối 3 report list theo (year, quarter) → list tuples."""
    def to_map(items: list[dict]) -> dict[tuple[int, int], dict]:
        out: dict[tuple[int, int], dict] = {}
        for r in items:
            k = _period_key(r)
            if k is None:
                continue
            if not (year_min <= k[0] <= year_max):
                continue
            out[k] = r
        return out

    inc_map = to_map(income)
    bs_map = to_map(balance)
    rat_map = to_map(ratio)

    all_periods = sorted(set(inc_map) | set(bs_map) | set(rat_map))

    rows: list[tuple[Any, ...]] = []
    for (y, q) in all_periods:
        inc_r = inc_map.get((y, q), {})
        bs_r = bs_map.get((y, q), {})
        rat_r = rat_map.get((y, q), {})

        rows.append((
            ticker,
            f"{y}Q{q}",
            y,
            q,
            None,                                                 # report_date — TCBS không trả
            _scale_vnd(_pick(inc_r, "revenue", "netSales")),
            _scale_vnd(_pick(inc_r, "grossProfit")),
            _scale_vnd(_pick(inc_r, "operationProfit", "operatingProfit")),
            _scale_vnd(_pick(inc_r, "preTaxProfit", "profitBeforeTax")),
            _scale_vnd(_pick(inc_r, "postTaxProfit", "netIncome", "profitAfterTax")),
            _scale_vnd(_pick(bs_r, "totalAssets")),
            _scale_vnd(_pick(bs_r, "equity", "ownersEquity", "totalEquity")),
            _scale_vnd(_pick(bs_r, "totalDebt", "liability", "totalLiabilities")),
            _safe_num(_pick(rat_r, "earningPerShare", "eps")),
            _safe_num(_pick(rat_r, "bookValuePerShare", "bvps")),
            _safe_num(_pick(rat_r, "roe", "returnOnEquity")),
            _safe_num(_pick(rat_r, "roa", "returnOnAssets")),
            _safe_num(_pick(rat_r, "debtOnEquity", "debtEquity", "d/e")),
        ))
    return rows


def run(conn, cfg: dict) -> int:
    throttle = float(cfg["vnstock"]["throttle_sec"])
    max_retries = int(cfg["vnstock"]["max_retries"])
    api = VnApi(throttle_sec=throttle, max_retries=max_retries)

    cfg_fund_year = cfg["fundamentals"].get("min_year")
    start_year = int(cfg_fund_year) if cfg_fund_year else int(cfg["dates"]["start"][:4])
    end_year = int(cfg["dates"]["end"][:4])

    with conn.cursor() as cur:
        cur.execute("SELECT ticker FROM stock.dim_ticker WHERE is_active ORDER BY ticker")
        tickers = [t for (t,) in cur.fetchall()]

    print(f"[fund] Fetching fundamentals (quarter, {start_year}-{end_year}) "
          f"for {len(tickers)} tickers (throttle={throttle}s)...")

    total_rows = 0
    total_ok = 0
    skip_fetch = 0
    skip_empty = 0
    for i, ticker in enumerate(tickers, 1):
        try:
            income = api.get_income_statement(ticker, yearly=False)
            api.throttle()
            balance = api.get_balance_sheet(ticker, yearly=False)
            api.throttle()
            ratio = api.get_financial_ratio(ticker, yearly=False)
        except Exception as e:
            print(f"  [skip] {ticker}: fetch err {type(e).__name__}: {str(e)[:120]}")
            skip_fetch += 1
            api.throttle()
            continue

        rows = _extract_rows(ticker, income, balance, ratio, start_year, end_year)
        if not rows:
            skip_empty += 1
            api.throttle()
            continue

        with conn.cursor() as cur:
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
        api.throttle()

    print(f"[fund] Finished: {total_ok}/{len(tickers)} tickers OK, {total_rows:,} rows.")
    print(f"  Skips: {skip_fetch} fetch-fail, {skip_empty} empty")
    return total_rows
