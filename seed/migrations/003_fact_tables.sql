-- 003_fact_tables.sql
-- Fact tables: OHLCV daily + báo cáo tài chính quý

CREATE TABLE IF NOT EXISTS stock.fact_price_daily (
  ticker        VARCHAR(10)  NOT NULL REFERENCES stock.dim_ticker(ticker),
  date_key      INT          NOT NULL REFERENCES stock.dim_date(date_key),
  trade_date    DATE         NOT NULL,
  open_price    NUMERIC(14,2) NOT NULL,            -- Giá mở cửa (VND/CP, đã scale)
  high_price    NUMERIC(14,2) NOT NULL,
  low_price     NUMERIC(14,2) NOT NULL,
  close_price   NUMERIC(14,2) NOT NULL,            -- Giá đóng cửa đã điều chỉnh
  volume        BIGINT        NOT NULL,            -- Khối lượng (số CP khớp lệnh)
  trade_value   BIGINT,                            -- Giá trị giao dịch (VND)
  PRIMARY KEY (ticker, date_key)
);

COMMENT ON TABLE stock.fact_price_daily IS 'OHLCV theo ngày. Giá đã điều chỉnh (adjusted) sau chia tách, cổ tức.';
COMMENT ON COLUMN stock.fact_price_daily.close_price IS 'Giá đóng cửa đã điều chỉnh — dùng để tính return/correlation.';
COMMENT ON COLUMN stock.fact_price_daily.volume IS 'Số lượng CP khớp lệnh (shares).';
COMMENT ON COLUMN stock.fact_price_daily.trade_value IS 'Giá trị giao dịch, đơn vị VND.';

CREATE TABLE IF NOT EXISTS stock.fact_fundamental_quarterly (
  ticker               VARCHAR(10) NOT NULL REFERENCES stock.dim_ticker(ticker),
  period               VARCHAR(8)  NOT NULL,       -- '2024Q1'
  year                 SMALLINT    NOT NULL,
  quarter              SMALLINT    NOT NULL,       -- 1..4
  report_date          DATE,                       -- ngày kỳ báo cáo kết thúc
  -- Income statement (đơn vị tỷ VND để tránh overflow + dễ đọc)
  revenue              NUMERIC(18,2),              -- Doanh thu thuần
  gross_profit         NUMERIC(18,2),              -- Lợi nhuận gộp
  operating_profit     NUMERIC(18,2),              -- LN thuần từ HĐKD
  profit_before_tax    NUMERIC(18,2),              -- LN trước thuế
  profit_after_tax     NUMERIC(18,2),              -- LNST / Net income
  -- Balance sheet snapshots
  total_assets         NUMERIC(18,2),
  total_equity         NUMERIC(18,2),
  total_debt           NUMERIC(18,2),
  -- Per-share + ratios
  eps                  NUMERIC(12,2),              -- Earnings per share (VND/CP)
  bvps                 NUMERIC(12,2),              -- Book value per share
  roe_pct              NUMERIC(8,2),               -- ROE %
  roa_pct              NUMERIC(8,2),               -- ROA %
  debt_to_equity       NUMERIC(8,2),               -- D/E ratio
  PRIMARY KEY (ticker, period)
);

COMMENT ON TABLE stock.fact_fundamental_quarterly IS 'Báo cáo tài chính quý — doanh thu, LNST, EPS, ROE. Đơn vị tỷ VND.';
COMMENT ON COLUMN stock.fact_fundamental_quarterly.revenue IS 'Doanh thu thuần, đơn vị tỷ VND.';
COMMENT ON COLUMN stock.fact_fundamental_quarterly.profit_after_tax IS 'Lợi nhuận sau thuế (LNST / Net income), đơn vị tỷ VND.';
COMMENT ON COLUMN stock.fact_fundamental_quarterly.eps IS 'Earnings per share — LNST / số CP lưu hành bình quân, đơn vị VND/CP.';
COMMENT ON COLUMN stock.fact_fundamental_quarterly.roe_pct IS 'Return on Equity, đơn vị % (VD: 15.50 = 15.5%).';

-- --------------------------------------------------------------------
-- Index benchmarks (VN-Index, HNX-Index, VN30 index)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stock.fact_index_daily (
  index_code    VARCHAR(20)   NOT NULL,            -- VNINDEX / VN30 / HNXINDEX
  date_key      INT           NOT NULL REFERENCES stock.dim_date(date_key),
  trade_date    DATE          NOT NULL,
  open_price    NUMERIC(14,4) NOT NULL,
  high_price    NUMERIC(14,4),
  low_price     NUMERIC(14,4),
  close_price   NUMERIC(14,4) NOT NULL,
  volume        BIGINT,
  trade_value   BIGINT,
  PRIMARY KEY (index_code, date_key)
);

COMMENT ON TABLE stock.fact_index_daily IS 'Chỉ số thị trường daily — VN-Index (benchmark cho ML), VN30, HNX-Index.';
COMMENT ON COLUMN stock.fact_index_daily.close_price IS 'Giá trị đóng cửa chỉ số, đơn vị điểm (dùng NUMERIC(14,4) vì index có nhiều số lẻ).';
