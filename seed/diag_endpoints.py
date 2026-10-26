"""Diag v2: test Yahoo Finance (yfinance) for VN stocks từ GitHub runner."""
from __future__ import annotations
import json
import sys

try:
    import yfinance as yf
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yfinance", "--quiet"])
    import yfinance as yf

print(f"yfinance version: {yf.__version__}")

def test(name: str, symbol: str, start: str, end: str):
    print(f"\n=== {name} ({symbol}) ===")
    try:
        t = yf.Ticker(symbol)
        hist = t.history(start=start, end=end)
        print(f"Rows: {len(hist)}")
        if not hist.empty:
            print(f"Columns: {list(hist.columns)}")
            print(f"First row: {hist.iloc[0].to_dict()}")
            print(f"Last row: {hist.iloc[-1].to_dict()}")
        else:
            print("EMPTY")
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {str(e)[:200]}")


print("Testing VN stocks via yfinance...")
test("VNM (Vinamilk)", "VNM.VN", "2024-01-01", "2024-01-15")
test("VCB (Vietcombank)", "VCB.VN", "2024-01-01", "2024-01-15")
test("FPT", "FPT.VN", "2024-01-01", "2024-01-15")
test("HPG", "HPG.VN", "2024-01-01", "2024-01-15")
test("VN-Index ^VNINDEX", "^VNINDEX", "2024-01-01", "2024-01-15")
test("VN-Index VNINDEX.VN", "VNINDEX.VN", "2024-01-01", "2024-01-15")

# Check ticker info
print("\n=== VNM info sample ===")
try:
    info = yf.Ticker("VNM.VN").info
    picked = {k: info.get(k) for k in [
        "symbol", "longName", "shortName", "exchange", "sector", "industry",
        "sharesOutstanding", "marketCap", "firstTradeDateEpochUtc", "country"
    ]}
    print(json.dumps(picked, indent=2, default=str))
except Exception as e:
    print(f"ERR: {e}")
