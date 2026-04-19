-- 002_dim_tables.sql
-- Dimension tables

CREATE TABLE IF NOT EXISTS shopee.dim_date (
  date_key      INT PRIMARY KEY,
  full_date     DATE NOT NULL UNIQUE,
  day           SMALLINT NOT NULL,
  month         SMALLINT NOT NULL,
  year          SMALLINT NOT NULL,
  quarter       SMALLINT NOT NULL,
  month_name    VARCHAR(10) NOT NULL,
  day_of_week   SMALLINT NOT NULL,
  day_name      VARCHAR(10) NOT NULL,
  week_of_year  SMALLINT NOT NULL,
  is_weekend    BOOLEAN NOT NULL,
  is_holiday    BOOLEAN NOT NULL DEFAULT FALSE,
  is_sale_day   BOOLEAN NOT NULL DEFAULT FALSE,
  fiscal_period VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS shopee.dim_location (
  location_id    INT PRIMARY KEY,
  city           VARCHAR(50) NOT NULL,
  province       VARCHAR(50) NOT NULL,
  region         VARCHAR(10) NOT NULL,
  is_major_city  BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (city, province)
);

CREATE TABLE IF NOT EXISTS shopee.dim_category (
  category_id    INT PRIMARY KEY,
  category_name  VARCHAR(80) NOT NULL,
  level          SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 4),
  parent_id      INT REFERENCES shopee.dim_category(category_id),
  full_path      VARCHAR(300) NOT NULL
);

CREATE TABLE IF NOT EXISTS shopee.dim_customer (
  customer_id       INT PRIMARY KEY,
  customer_name     VARCHAR(100) NOT NULL,
  gender            VARCHAR(6),
  birth_year        SMALLINT,
  signup_date_key   INT REFERENCES shopee.dim_date(date_key),
  city              VARCHAR(50),
  province          VARCHAR(50),
  preferred_device  VARCHAR(10),
  tier              VARCHAR(10) NOT NULL DEFAULT 'bronze'
);

CREATE TABLE IF NOT EXISTS shopee.dim_seller (
  seller_id         INT PRIMARY KEY,
  shop_name         VARCHAR(150) NOT NULL,
  shop_type         VARCHAR(15) NOT NULL,
  seller_city       VARCHAR(50),
  seller_province   VARCHAR(50),
  join_date_key     INT REFERENCES shopee.dim_date(date_key),
  is_official       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS shopee.dim_product (
  product_id   INT PRIMARY KEY,
  product_name VARCHAR(200) NOT NULL,
  seller_id    INT NOT NULL REFERENCES shopee.dim_seller(seller_id),
  brand        VARCHAR(80),
  list_price   NUMERIC(12,2) NOT NULL,
  launch_date  DATE,
  cat1_id      INT, cat1_name VARCHAR(80),
  cat2_id      INT, cat2_name VARCHAR(80),
  cat3_id      INT, cat3_name VARCHAR(80),
  cat4_id      INT NOT NULL, cat4_name VARCHAR(80),
  is_active    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS shopee.dim_campaign (
  campaign_id     INT PRIMARY KEY,
  campaign_name   VARCHAR(100) NOT NULL,
  campaign_type   VARCHAR(20) NOT NULL,
  start_date_key  INT REFERENCES shopee.dim_date(date_key),
  end_date_key    INT REFERENCES shopee.dim_date(date_key),
  owner_team      VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS shopee.dim_voucher (
  voucher_id            INT PRIMARY KEY,
  voucher_code          VARCHAR(30) NOT NULL UNIQUE,
  voucher_type          VARCHAR(15) NOT NULL,
  discount_type         VARCHAR(10) NOT NULL,
  discount_value        NUMERIC(12,2) NOT NULL,
  min_order_value       NUMERIC(12,2) NOT NULL DEFAULT 0,
  max_discount          NUMERIC(12,2),
  valid_from_date_key   INT REFERENCES shopee.dim_date(date_key),
  valid_to_date_key     INT REFERENCES shopee.dim_date(date_key),
  campaign_id           INT REFERENCES shopee.dim_campaign(campaign_id)
);
