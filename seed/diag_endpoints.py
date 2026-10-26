"""Quick diagnostic: test various TCBS endpoints from GitHub Actions runner.

Run via workflow với mode=diag để verify endpoints trước khi làm fetch thật.
"""
from __future__ import annotations
import json
import os
import sys
import requests


def test_endpoint(name: str, url: str, headers: dict | None = None):
    print(f"\n=== {name} ===")
    print(f"URL: {url}")
    try:
        r = requests.get(url, headers=headers or {}, timeout=20)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            try:
                data = r.json()
                s = json.dumps(data, ensure_ascii=False)
                print(f"Body (first 500 chars): {s[:500]}")
            except Exception:
                print(f"Body text: {r.text[:300]}")
        else:
            print(f"Body: {r.text[:300]}")
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {str(e)[:200]}")


def main():
    # vnstock-compatible headers
    H = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "vi",
        "Connection": "keep-alive",
        "DNT": "1",
        "Origin": "https://tcinvest.tcbs.com.vn/",
        "Referer": "https://tcinvest.tcbs.com.vn/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
    }

    import time
    now_ts = int(time.time())

    # TCBS bars-long-term — various forms
    test_endpoint("TCBS bars-long-term (vnstock exact order)",
        f"https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term"
        f"?resolution=D&ticker=VNM&type=stock&to={now_ts}&countBack=100",
        H)

    test_endpoint("TCBS bars-long-term (my order)",
        f"https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term"
        f"?ticker=VNM&type=stock&resolution=D&to={now_ts}&countBack=100",
        H)

    # Without headers at all
    test_endpoint("TCBS bars (no headers)",
        f"https://apipubaws.tcbs.com.vn/stock-insight/v2/stock/bars-long-term"
        f"?resolution=D&ticker=VNM&type=stock&to={now_ts}&countBack=100")

    # Try v1
    test_endpoint("TCBS v1 bars-long-term",
        f"https://apipubaws.tcbs.com.vn/stock-insight/v1/stock/bars-long-term"
        f"?resolution=D&ticker=VNM&type=stock&to={now_ts}&countBack=100",
        H)

    # TCBS ticker overview
    test_endpoint("TCBS ticker overview",
        "https://apipubaws.tcbs.com.vn/tcanalysis/v1/ticker/VNM/overview",
        H)

    # TCBS finance
    test_endpoint("TCBS incomestatement",
        "https://apipubaws.tcbs.com.vn/tcanalysis/v1/finance/VNM/incomestatement?yearly=0&isAll=false",
        H)

    # SSI alternative
    test_endpoint("SSI iboard",
        "https://iboard-api.ssi.com.vn/statistics/charts/history?resolution=D&symbol=VNM&from=1700000000&to=1735603200",
        {"Origin": "https://iboard.ssi.com.vn", "Referer": "https://iboard.ssi.com.vn/"})


if __name__ == "__main__":
    main()
