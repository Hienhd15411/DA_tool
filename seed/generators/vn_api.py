"""HTTP client cho public API của TCBS + vndirect.

Thay thế vnstock lib (bị quarantine trên PyPI). Gọi trực tiếp các endpoint
public mà vnstock scrape bên trong — không phụ thuộc 3rd party lib fragile.

Endpoints:
  • TCBS bars long-term (OHLCV + index):
      https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term
  • TCBS finance (income/balance/ratio quarterly):
      https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/{ticker}/{report_type}
  • TCBS ticker overview:
      https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/{ticker}/overview
  • vndirect listing (HOSE tickers + metadata):
      https://finfo-api.vndirect.com.vn/v4/stocks?q=type:STOCK~status:LISTED~floor:HOSE
"""
from __future__ import annotations
import time
from datetime import date, datetime, timezone
from typing import Any

import requests

TCBS_BASE = "https://apipubaws.tcbs.com.vn"
VNDIRECT_BASE = "https://finfo-api.vndirect.com.vn/v4"

# Common user-agent để tránh bị block
DEFAULT_UA = (
    "Mozilla/5.0 (Linux; GitHub-Actions) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DEFAULT_TIMEOUT = 30.0


class VnApi:
    """Shared session với retry + throttle."""

    def __init__(self, throttle_sec: float = 0.5, max_retries: int = 5):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
            "Origin": "https://www.tcbs.com.vn",
            "Referer": "https://www.tcbs.com.vn/",
        })
        self.throttle_sec = throttle_sec
        self.max_retries = max_retries

    def _get_json(self, url: str, params: dict | None = None,
                  headers: dict | None = None) -> Any:
        """GET với exponential backoff. Raise sau khi hết retry."""
        last_err: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                r = self.session.get(url, params=params, headers=headers,
                                     timeout=DEFAULT_TIMEOUT)
                if r.status_code == 200:
                    return r.json()
                # 429 / 5xx → retry
                if r.status_code in (429, 500, 502, 503, 504):
                    last_err = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                    time.sleep(1.5 ** attempt)
                    continue
                # Other 4xx — raise ngay
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            except (requests.ConnectionError, requests.Timeout, requests.HTTPError) as e:
                last_err = e
                time.sleep(1.5 ** attempt)
        raise RuntimeError(f"Failed after {self.max_retries} retries: {last_err}")

    def throttle(self) -> None:
        time.sleep(self.throttle_sec)

    # ------------------------------------------------------------------
    # OHLCV + Index (shared endpoint — type=stock|index)
    # ------------------------------------------------------------------
    def get_bars(self, ticker: str, from_date: date, to_date: date,
                 *, kind: str = "stock", resolution: str = "D") -> list[dict]:
        """Lấy OHLCV bars từ TCBS.

        kind: 'stock' | 'index'
        resolution: 'D' | '1' | '5' | '15' | '30' | '60'
        """
        url = f"{TCBS_BASE}/stock-insight/v2/stock/bars-long-term"
        from_ts = int(datetime(from_date.year, from_date.month, from_date.day,
                               tzinfo=timezone.utc).timestamp())
        to_ts = int(datetime(to_date.year, to_date.month, to_date.day,
                             tzinfo=timezone.utc).timestamp()) + 86400  # include end day
        # TCBS trả tối đa ~countBack bars tính ngược từ `to`.
        # 1 ngày × 3 năm ~750 phiên → chọn 2000 cho safe margin.
        params = {
            "ticker": ticker,
            "type": kind,
            "resolution": resolution,
            "to": to_ts,
            "countBack": 2000,
        }
        data = self._get_json(url, params=params)
        if not isinstance(data, dict) or "data" not in data:
            return []
        # Filter theo from_ts nữa (vì countBack lấy nhiều)
        bars = []
        for b in data["data"]:
            # TCBS: tradingDate ISO string hoặc timestamp
            td = b.get("tradingDate") or b.get("time")
            if td is None:
                continue
            if isinstance(td, (int, float)):
                dt_obj = datetime.fromtimestamp(td / 1000 if td > 1e12 else td,
                                                tz=timezone.utc).date()
            else:
                dt_obj = datetime.fromisoformat(str(td).replace("Z", "+00:00")).date()
            if dt_obj < from_date or dt_obj > to_date:
                continue
            bars.append({
                "trade_date": dt_obj,
                "open":  b.get("open"),
                "high":  b.get("high"),
                "low":   b.get("low"),
                "close": b.get("close"),
                "volume": b.get("volume"),
                "value": b.get("value"),
            })
        return bars

    # ------------------------------------------------------------------
    # HOSE ticker listing (vndirect)
    # ------------------------------------------------------------------
    def list_tickers_hose(self) -> list[dict]:
        """Lấy danh sách tất cả mã HOSE đang listed từ vndirect finfo API.

        Trả: list[{symbol, companyName, floor, icbName, listingDate, outstandingShares, ...}]
        """
        url = f"{VNDIRECT_BASE}/stocks"
        params = {
            "q": "type:STOCK~status:LISTED~floor:HOSE",
            "size": 1000,
            "sort": "symbol:asc",
        }
        data = self._get_json(url, params=params)
        if not isinstance(data, dict):
            return []
        return data.get("data") or []

    # ------------------------------------------------------------------
    # TCBS ticker overview (industry, outstanding shares, ...)
    # ------------------------------------------------------------------
    def get_ticker_overview(self, ticker: str) -> dict | None:
        """Metadata chi tiết 1 mã."""
        url = f"{TCBS_BASE}/tcanalysis/v1/ticker/{ticker}/overview"
        try:
            return self._get_json(url)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Fundamental reports (quarterly)
    # ------------------------------------------------------------------
    def get_income_statement(self, ticker: str, yearly: bool = False) -> list[dict]:
        """Báo cáo kết quả kinh doanh. yearly=False → quarterly."""
        url = f"{TCBS_BASE}/tcanalysis/v1/finance/{ticker}/incomestatement"
        params = {"yearly": 1 if yearly else 0, "isAll": "false"}
        data = self._get_json(url, params=params)
        return data if isinstance(data, list) else []

    def get_balance_sheet(self, ticker: str, yearly: bool = False) -> list[dict]:
        url = f"{TCBS_BASE}/tcanalysis/v1/finance/{ticker}/balancesheet"
        params = {"yearly": 1 if yearly else 0, "isAll": "false"}
        data = self._get_json(url, params=params)
        return data if isinstance(data, list) else []

    def get_financial_ratio(self, ticker: str, yearly: bool = False) -> list[dict]:
        url = f"{TCBS_BASE}/tcanalysis/v1/finance/{ticker}/financialratio"
        params = {"yearly": 1 if yearly else 0, "isAll": "false"}
        data = self._get_json(url, params=params)
        return data if isinstance(data, list) else []
