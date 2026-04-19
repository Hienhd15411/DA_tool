-- 007_indexes.sql
-- Indexes for query performance on common filter/join columns

-- fact_orders
CREATE INDEX IF NOT EXISTS ix_orders_date         ON shopee.fact_orders (order_date_key);
CREATE INDEX IF NOT EXISTS ix_orders_customer     ON shopee.fact_orders (customer_id);
CREATE INDEX IF NOT EXISTS ix_orders_seller       ON shopee.fact_orders (seller_id);
CREATE INDEX IF NOT EXISTS ix_orders_campaign     ON shopee.fact_orders (campaign_id) WHERE campaign_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_orders_status_date  ON shopee.fact_orders (order_status, order_date_key);
CREATE INDEX IF NOT EXISTS ix_orders_created      ON shopee.fact_orders (created_at);

-- fact_order_items
CREATE INDEX IF NOT EXISTS ix_items_order     ON shopee.fact_order_items (order_id);
CREATE INDEX IF NOT EXISTS ix_items_product   ON shopee.fact_order_items (product_id);
CREATE INDEX IF NOT EXISTS ix_items_seller    ON shopee.fact_order_items (seller_id);

-- fact_shipment
CREATE INDEX IF NOT EXISTS ix_shipment_order   ON shopee.fact_shipment (order_id);
CREATE INDEX IF NOT EXISTS ix_shipment_carrier ON shopee.fact_shipment (carrier);

-- fact_returns
CREATE INDEX IF NOT EXISTS ix_returns_order ON shopee.fact_returns (order_id);
CREATE INDEX IF NOT EXISTS ix_returns_item  ON shopee.fact_returns (order_item_id);

-- fact_ad_spend / performance
CREATE INDEX IF NOT EXISTS ix_adspend_date_campaign ON shopee.fact_ad_spend (date_key, campaign_id);

-- fact_voucher_usage
CREATE INDEX IF NOT EXISTS ix_vusage_order   ON shopee.fact_voucher_usage (order_id);
CREATE INDEX IF NOT EXISTS ix_vusage_voucher ON shopee.fact_voucher_usage (voucher_id);

-- fact_traffic_session
CREATE INDEX IF NOT EXISTS ix_traffic_customer_date ON shopee.fact_traffic_session (customer_id, date_key);
CREATE INDEX IF NOT EXISTS ix_traffic_source       ON shopee.fact_traffic_session (traffic_source);

-- fact_inventory_weekly
CREATE INDEX IF NOT EXISTS ix_inv_product_date ON shopee.fact_inventory_weekly (product_id, snapshot_date_key);

-- fact_customer_service_ticket
CREATE INDEX IF NOT EXISTS ix_ticket_customer ON shopee.fact_customer_service_ticket (customer_id);
CREATE INDEX IF NOT EXISTS ix_ticket_seller   ON shopee.fact_customer_service_ticket (seller_id);
CREATE INDEX IF NOT EXISTS ix_ticket_status   ON shopee.fact_customer_service_ticket (status);

-- dim_product category drill-down
CREATE INDEX IF NOT EXISTS ix_product_cat1 ON shopee.dim_product (cat1_id);
CREATE INDEX IF NOT EXISTS ix_product_cat4 ON shopee.dim_product (cat4_id);
