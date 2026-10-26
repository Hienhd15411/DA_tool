"""stock_trend — ML pipeline dự báo trend 5 ngày cho cổ phiếu VN.

Modules:
  features/technical.py  — chỉ báo kỹ thuật (EMA, ADX, RSI, MACD, ATR, volume…)
  features/value.py      — value_score_fund + value_score_tech
  features/labels.py     — fwd_ret_5, y_bin với ngưỡng ATR
  dataset.py             — build dataset từ Supabase, kiểm tra NaN + look-ahead
  model.py               — LightGBM train + predict + walk-forward CV
  select.py              — chọn 10 mã (value sàng lọc + ML rank + diversity)
  evaluate.py            — IC_daily, lift, calibration, bootstrap CI
  daily_run.py           — pipeline cuối phiên: fetch → feature → predict → push

Spec chi tiết: docs/ml_trend_5d_spec.md
"""
