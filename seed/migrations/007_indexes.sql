-- 007_indexes.sql
-- Indexes cho query patterns phổ biến trên stock schema

-- fact_price_daily: PRIMARY KEY đã cover (ticker, date_key). Thêm index theo ngày để
-- query "giao dịch của tất cả mã trong 1 ngày / 1 tháng" nhanh hơn.
CREATE INDEX IF NOT EXISTS ix_price_date       ON stock.fact_price_daily (date_key);
CREATE INDEX IF NOT EXISTS ix_price_trade_date ON stock.fact_price_daily (trade_date);

-- Query "top volume / top value" theo ngày
CREATE INDEX IF NOT EXISTS ix_price_date_volume
  ON stock.fact_price_daily (date_key, volume DESC);
CREATE INDEX IF NOT EXISTS ix_price_date_value
  ON stock.fact_price_daily (date_key, trade_value DESC);

-- fact_fundamental_quarterly: PK (ticker, period) đã cover. Thêm index theo kỳ.
CREATE INDEX IF NOT EXISTS ix_fund_year_quarter
  ON stock.fact_fundamental_quarterly (year, quarter);
CREATE INDEX IF NOT EXISTS ix_fund_period
  ON stock.fact_fundamental_quarterly (period);

-- dim_ticker: filter theo ngành, VN30
CREATE INDEX IF NOT EXISTS ix_ticker_industry ON stock.dim_ticker (industry_id);
CREATE INDEX IF NOT EXISTS ix_ticker_vn30     ON stock.dim_ticker (is_vn30) WHERE is_vn30;

-- dim_date: filter trading day
CREATE INDEX IF NOT EXISTS ix_date_trading
  ON stock.dim_date (full_date) WHERE is_trading_day;
CREATE INDEX IF NOT EXISTS ix_date_year_month
  ON stock.dim_date (year, month);
