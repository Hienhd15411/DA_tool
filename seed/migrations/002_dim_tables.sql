-- 002_dim_tables.sql
-- Dimension tables cho dataset chứng khoán VN

CREATE TABLE IF NOT EXISTS stock.dim_date (
  date_key        INT PRIMARY KEY,          -- YYYYMMDD
  full_date       DATE NOT NULL UNIQUE,
  day             SMALLINT NOT NULL,
  month           SMALLINT NOT NULL,
  year            SMALLINT NOT NULL,
  quarter         SMALLINT NOT NULL,        -- 1..4
  month_name      VARCHAR(10) NOT NULL,     -- January..December
  day_of_week     SMALLINT NOT NULL,        -- 1=Monday..7=Sunday
  day_name        VARCHAR(10) NOT NULL,     -- Monday..Sunday
  week_of_year    SMALLINT NOT NULL,
  is_weekend      BOOLEAN NOT NULL,         -- Sat/Sun
  is_trading_day  BOOLEAN NOT NULL,         -- false nếu weekend hoặc holiday
  is_holiday      BOOLEAN NOT NULL DEFAULT FALSE,
  holiday_name    VARCHAR(60),              -- 'Tết Nguyên đán', '30/4', '2/9'
  fiscal_quarter  VARCHAR(8)                -- '2024Q1'
);

COMMENT ON TABLE stock.dim_date IS 'Calendar: 2024-2025, flag ngày giao dịch vs holiday vs weekend.';

CREATE TABLE IF NOT EXISTS stock.dim_industry (
  industry_id    SERIAL PRIMARY KEY,
  industry_name  VARCHAR(100) NOT NULL UNIQUE,     -- 'Bất động sản', 'Ngân hàng', ...
  sector         VARCHAR(60)                      -- Nhóm ngành lớn hơn
);

COMMENT ON TABLE stock.dim_industry IS 'Danh mục ngành theo chuẩn ICB cấp 2/3.';

CREATE TABLE IF NOT EXISTS stock.dim_ticker (
  ticker              VARCHAR(10) PRIMARY KEY,     -- VNM, VIC, HPG, ACB
  company_name        VARCHAR(200) NOT NULL,
  exchange            VARCHAR(10) NOT NULL,        -- HOSE / HNX / UPCOM
  industry_id         INT REFERENCES stock.dim_industry(industry_id),
  listed_date         DATE,                        -- ngày niêm yết
  listed_date_key     INT REFERENCES stock.dim_date(date_key),
  outstanding_shares  BIGINT,                      -- số CP lưu hành (snapshot)
  charter_capital     BIGINT,                      -- vốn điều lệ (VND)
  is_vn30             BOOLEAN NOT NULL DEFAULT FALSE,
  is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE stock.dim_ticker IS 'Danh sách mã HOSE + metadata công ty.';
