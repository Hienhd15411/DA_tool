-- 003_fact_tables.sql
-- Fact tables

CREATE TABLE IF NOT EXISTS shopee.fact_orders (
  order_id           BIGINT PRIMARY KEY,
  order_sn           VARCHAR(20) NOT NULL UNIQUE,
  customer_id        INT NOT NULL REFERENCES shopee.dim_customer(customer_id),
  seller_id          INT NOT NULL REFERENCES shopee.dim_seller(seller_id),
  campaign_id        INT REFERENCES shopee.dim_campaign(campaign_id),
  order_date_key     INT NOT NULL REFERENCES shopee.dim_date(date_key),
  order_status       VARCHAR(20) NOT NULL,
  payment_method     VARCHAR(20) NOT NULL,
  payment_status     VARCHAR(15) NOT NULL,
  shipping_provider  VARCHAR(20),
  ship_from_city     VARCHAR(50),
  ship_to_city       VARCHAR(50) NOT NULL,
  ship_to_province   VARCHAR(50) NOT NULL,
  device_type        VARCHAR(10) NOT NULL,
  item_count         SMALLINT NOT NULL,
  subtotal           NUMERIC(12,2) NOT NULL,
  shop_discount      NUMERIC(12,2) NOT NULL DEFAULT 0,
  platform_voucher   NUMERIC(12,2) NOT NULL DEFAULT 0,
  shipping_fee       NUMERIC(10,2) NOT NULL DEFAULT 0,
  shipping_discount  NUMERIC(10,2) NOT NULL DEFAULT 0,
  coin_used          NUMERIC(10,2) NOT NULL DEFAULT 0,
  total_amount       NUMERIC(12,2) NOT NULL,
  is_first_order     BOOLEAN NOT NULL DEFAULT FALSE,
  cancel_reason      VARCHAR(40),
  created_at         TIMESTAMPTZ NOT NULL,
  paid_at            TIMESTAMPTZ,
  shipped_at         TIMESTAMPTZ,
  delivered_at       TIMESTAMPTZ,
  completed_at       TIMESTAMPTZ,
  cancelled_at       TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS shopee.fact_order_items (
  order_item_id  BIGINT PRIMARY KEY,
  order_id       BIGINT NOT NULL REFERENCES shopee.fact_orders(order_id),
  product_id     INT NOT NULL REFERENCES shopee.dim_product(product_id),
  seller_id      INT NOT NULL REFERENCES shopee.dim_seller(seller_id),
  quantity       SMALLINT NOT NULL,
  unit_price     NUMERIC(12,2) NOT NULL,
  item_discount  NUMERIC(12,2) NOT NULL DEFAULT 0,
  line_total     NUMERIC(12,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS shopee.fact_shipment (
  shipment_id         BIGINT PRIMARY KEY,
  order_id            BIGINT NOT NULL REFERENCES shopee.fact_orders(order_id),
  carrier             VARCHAR(20) NOT NULL,
  pickup_at           TIMESTAMPTZ,
  delivered_at        TIMESTAMPTZ,
  sla_committed_hours SMALLINT NOT NULL,
  actual_hours        SMALLINT,
  is_on_time          BOOLEAN,
  weight_kg           NUMERIC(6,2)
);

CREATE TABLE IF NOT EXISTS shopee.fact_returns (
  return_id      BIGINT PRIMARY KEY,
  order_id       BIGINT NOT NULL REFERENCES shopee.fact_orders(order_id),
  order_item_id  BIGINT REFERENCES shopee.fact_order_items(order_item_id),
  return_reason  VARCHAR(40) NOT NULL,
  return_status  VARCHAR(15) NOT NULL,
  refund_amount  NUMERIC(12,2) NOT NULL,
  requested_at   TIMESTAMPTZ NOT NULL,
  completed_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS shopee.fact_ad_spend (
  ad_spend_id    BIGINT PRIMARY KEY,
  date_key       INT NOT NULL REFERENCES shopee.dim_date(date_key),
  campaign_id    INT NOT NULL REFERENCES shopee.dim_campaign(campaign_id),
  channel        VARCHAR(15) NOT NULL,
  spend_amount   NUMERIC(12,2) NOT NULL,
  impressions    INT NOT NULL DEFAULT 0,
  clicks         INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS shopee.fact_ad_performance_daily (
  date_key           INT NOT NULL REFERENCES shopee.dim_date(date_key),
  campaign_id        INT NOT NULL REFERENCES shopee.dim_campaign(campaign_id),
  cat1_id            INT,
  impressions        INT NOT NULL DEFAULT 0,
  clicks             INT NOT NULL DEFAULT 0,
  orders_attributed  INT NOT NULL DEFAULT 0,
  gmv_attributed     NUMERIC(14,2) NOT NULL DEFAULT 0,
  PRIMARY KEY (date_key, campaign_id, cat1_id)
);

CREATE TABLE IF NOT EXISTS shopee.fact_voucher_usage (
  voucher_usage_id  BIGINT PRIMARY KEY,
  order_id          BIGINT NOT NULL REFERENCES shopee.fact_orders(order_id),
  voucher_id        INT NOT NULL REFERENCES shopee.dim_voucher(voucher_id),
  discount_applied  NUMERIC(12,2) NOT NULL,
  used_at           TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS shopee.fact_traffic_session (
  session_id         BIGINT PRIMARY KEY,
  customer_id        INT REFERENCES shopee.dim_customer(customer_id),
  date_key           INT NOT NULL REFERENCES shopee.dim_date(date_key),
  device_type        VARCHAR(10) NOT NULL,
  traffic_source     VARCHAR(15) NOT NULL,
  landing_page_type  VARCHAR(15) NOT NULL,
  pageviews          INT NOT NULL,
  duration_seconds   INT NOT NULL,
  has_order          BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS shopee.fact_inventory_weekly (
  snapshot_date_key  INT NOT NULL REFERENCES shopee.dim_date(date_key),
  product_id         INT NOT NULL REFERENCES shopee.dim_product(product_id),
  seller_id          INT NOT NULL REFERENCES shopee.dim_seller(seller_id),
  stock_qty          INT NOT NULL,
  is_in_stock        BOOLEAN NOT NULL,
  PRIMARY KEY (snapshot_date_key, product_id)
);

CREATE TABLE IF NOT EXISTS shopee.fact_customer_service_ticket (
  ticket_id    BIGINT PRIMARY KEY,
  order_id     BIGINT REFERENCES shopee.fact_orders(order_id),
  customer_id  INT NOT NULL REFERENCES shopee.dim_customer(customer_id),
  seller_id    INT REFERENCES shopee.dim_seller(seller_id),
  category     VARCHAR(20) NOT NULL,
  priority     VARCHAR(10) NOT NULL,
  status       VARCHAR(15) NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL,
  resolved_at  TIMESTAMPTZ
);
