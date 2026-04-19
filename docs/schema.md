# Schema reference — Shopee-like dataset

Tham chiếu schema để viết SQL trong toàn bộ bộ bài tập. Tất cả bảng đặt trong schema `shopee`. Dataset ~400 MB, 3 tháng dữ liệu (Feb–Apr).

## Dimension tables

### `dim_date`
Star-schema date dimension. `date_key` = `INT` dạng `YYYYMMDD` (vd `20240315`).

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `date_key` | INT PK | 20240315 |
| `full_date` | DATE | 2024-03-15 |
| `day`, `month`, `year`, `quarter` | SMALLINT | |
| `month_name`, `day_name` | VARCHAR | March, Friday |
| `day_of_week` | SMALLINT | 1=Mon..7=Sun |
| `week_of_year` | SMALLINT | ISO week |
| `is_weekend` | BOOLEAN | |
| `is_holiday` | BOOLEAN | Tết, lễ VN |
| `is_sale_day` | BOOLEAN | 3/3, 4/4, 5/5, payday (25) |

### `dim_customer`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `customer_id` | INT PK | |
| `customer_name` | VARCHAR | |
| `gender` | VARCHAR(6) | male/female/other |
| `birth_year` | SMALLINT | |
| `signup_date_key` | INT | FK dim_date |
| `city`, `province` | VARCHAR | |
| `preferred_device` | VARCHAR | ios/android/web |
| `tier` | VARCHAR | bronze/silver/gold/platinum |

### `dim_seller`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `seller_id` | INT PK | |
| `shop_name` | VARCHAR | |
| `shop_type` | VARCHAR | mall/preferred/normal |
| `seller_city`, `seller_province` | VARCHAR | |
| `join_date_key` | INT | |
| `is_official` | BOOLEAN | |

### `dim_product`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `product_id` | INT PK | |
| `product_name` | VARCHAR | |
| `seller_id` | INT | FK dim_seller |
| `brand` | VARCHAR | |
| `list_price` | NUMERIC(12,2) | Giá niêm yết |
| `launch_date` | DATE | |
| `cat1_id`, `cat1_name` | INT, VARCHAR | Ngành hàng chính |
| `cat2_id`, `cat2_name` | INT, VARCHAR | Sub |
| `cat3_id`, `cat3_name` | INT, VARCHAR | Sub-sub |
| `cat4_id`, `cat4_name` | INT, VARCHAR | Leaf (SKU thuộc cat4) |
| `is_active` | BOOLEAN | |

### `dim_category`
Hierarchy tự tham chiếu.
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `category_id` | INT PK | |
| `category_name` | VARCHAR | |
| `level` | SMALLINT | 1..4 |
| `parent_id` | INT | self-ref |
| `full_path` | VARCHAR | "Điện Tử > Điện Thoại > Smartphone > iPhone" |

### `dim_campaign`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `campaign_id` | INT PK | |
| `campaign_name` | VARCHAR | "3.3 Mega Sale", "4.4 Beauty Fest"... |
| `campaign_type` | VARCHAR | mega_sale/flash_sale/category_sale/voucher_only |
| `start_date_key`, `end_date_key` | INT | |
| `owner_team` | VARCHAR | marketing/category/seller_ops |

### `dim_voucher`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `voucher_id` | INT PK | |
| `voucher_code` | VARCHAR | |
| `voucher_type` | VARCHAR | shop/platform/shipping |
| `discount_type` | VARCHAR | percent/fixed |
| `discount_value` | NUMERIC(12,2) | |
| `min_order_value` | NUMERIC(12,2) | |
| `max_discount` | NUMERIC(12,2) | |
| `valid_from_date_key`, `valid_to_date_key` | INT | |
| `campaign_id` | INT | nullable |

### `dim_location`
| Cột | Kiểu | Ghi chú |
|---|---|---|
| `location_id` | INT PK | |
| `city` | VARCHAR | |
| `province` | VARCHAR | |
| `region` | VARCHAR | north/central/south |
| `is_major_city` | BOOLEAN | HCM, HN, DN, CT, HP |

---

## Fact tables

### `fact_orders` — cấp độ đơn hàng

Cột chính (xem file `exercises/README.md` để thấy design đầy đủ):

- `order_id BIGINT PK`, `order_sn VARCHAR(20) UNIQUE`
- `customer_id`, `seller_id`, `campaign_id` (nullable)
- `order_date_key INT` (FK dim_date) — ngày đặt đơn
- `order_status` — pending / to_ship / shipping / completed / cancelled / returned / refunded
- `payment_method` — cod / shopeepay / credit_card / bank_transfer / installment
- `payment_status` — unpaid / paid / refunded / failed
- `shipping_provider` — spx / ghn / jnt / viettel_post / ninja_van / grab
- `ship_from_city`, `ship_to_city`, `ship_to_province`
- `device_type` — ios / android / web
- `item_count SMALLINT`
- Tiền: `subtotal`, `shop_discount`, `platform_voucher`, `shipping_fee`, `shipping_discount`, `coin_used`, `total_amount` (NUMERIC)
- `is_first_order BOOLEAN`
- `cancel_reason` (nullable)
- Timestamps (TIMESTAMPTZ): `created_at`, `paid_at`, `shipped_at`, `delivered_at`, `completed_at`, `cancelled_at`

### `fact_order_items` — cấp độ SKU trong đơn

| Cột | Kiểu |
|---|---|
| `order_item_id` | BIGINT PK |
| `order_id` | BIGINT FK |
| `product_id` | INT FK |
| `seller_id` | INT FK |
| `quantity` | SMALLINT |
| `unit_price` | NUMERIC(12,2) |
| `item_discount` | NUMERIC(12,2) |
| `line_total` | NUMERIC(12,2) |

### `fact_returns`
| Cột | Kiểu |
|---|---|
| `return_id` | BIGINT PK |
| `order_id` | BIGINT FK |
| `order_item_id` | BIGINT FK nullable (null = return cả đơn) |
| `return_reason` | VARCHAR |
| `return_status` | VARCHAR — requested/approved/rejected/completed |
| `refund_amount` | NUMERIC(12,2) |
| `requested_at`, `completed_at` | TIMESTAMPTZ |

### `fact_shipment`
| Cột | Kiểu |
|---|---|
| `shipment_id` | BIGINT PK |
| `order_id` | BIGINT FK |
| `carrier` | VARCHAR (= shipping_provider) |
| `pickup_at`, `delivered_at` | TIMESTAMPTZ |
| `sla_committed_hours` | SMALLINT |
| `actual_hours` | SMALLINT |
| `is_on_time` | BOOLEAN |
| `weight_kg` | NUMERIC(6,2) |

### `fact_ad_spend`
| Cột | Kiểu |
|---|---|
| `ad_spend_id` | BIGINT PK |
| `date_key` | INT |
| `campaign_id` | INT |
| `channel` | VARCHAR — search/display/affiliate/kol |
| `spend_amount` | NUMERIC(12,2) |
| `impressions` | INT |
| `clicks` | INT |

### `fact_ad_performance_daily`
Aggregated daily per campaign + cat1.
| Cột | Kiểu |
|---|---|
| `date_key` | INT |
| `campaign_id` | INT |
| `cat1_id` | INT |
| `impressions`, `clicks`, `orders_attributed` | INT |
| `gmv_attributed` | NUMERIC(14,2) |

### `fact_voucher_usage`
| Cột | Kiểu |
|---|---|
| `voucher_usage_id` | BIGINT PK |
| `order_id` | BIGINT FK |
| `voucher_id` | INT FK |
| `discount_applied` | NUMERIC(12,2) |
| `used_at` | TIMESTAMPTZ |

### `fact_traffic_session` (sampled)
| Cột | Kiểu |
|---|---|
| `session_id` | BIGINT PK |
| `customer_id` | INT nullable (null = guest) |
| `date_key` | INT |
| `device_type` | VARCHAR |
| `traffic_source` | VARCHAR — organic/paid/social/direct/affiliate |
| `landing_page_type` | VARCHAR — home/category/product/search/campaign |
| `pageviews`, `duration_seconds` | INT |
| `has_order` | BOOLEAN |

### `fact_inventory_weekly`
Snapshot thứ Hai hàng tuần.
| Cột | Kiểu |
|---|---|
| `snapshot_date_key` | INT |
| `product_id` | INT |
| `seller_id` | INT |
| `stock_qty` | INT |
| `is_in_stock` | BOOLEAN |

### `fact_customer_service_ticket`
| Cột | Kiểu |
|---|---|
| `ticket_id` | BIGINT PK |
| `order_id` | BIGINT FK nullable |
| `customer_id` | INT FK |
| `seller_id` | INT FK nullable |
| `category` | VARCHAR — shipping/quality/refund/voucher/account/other |
| `priority` | VARCHAR — low/med/high/urgent |
| `status` | VARCHAR — open/in_progress/resolved/closed |
| `created_at`, `resolved_at` | TIMESTAMPTZ |

---

## Quy ước chung

1. **Tất cả tiền** là VND (`NUMERIC(12,2)` hoặc `NUMERIC(14,2)` cho GMV aggregate).
2. **Filter GMV**: mặc định `payment_status = 'paid'` (không đếm đơn unpaid/cancelled/refunded vào GMV top-line). Lưu ý case study có thể override.
3. **Timezone**: tất cả `TIMESTAMPTZ` lưu UTC, convert `AT TIME ZONE 'Asia/Ho_Chi_Minh'` khi cần.
4. **Join ngày**: fact dùng `order_date_key INT` join vào `dim_date.date_key` — đây là chuẩn star schema.
5. **Edge cases có cố ý**: một số đơn `completed` thiếu `delivered_at`, một số `cancelled` vẫn có `paid_at`, vài `order_sn` bị viết hoa/thường lẫn lộn — dùng để dạy data quality.
