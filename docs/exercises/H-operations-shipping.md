# Chủ đề H — Operations / Shipping / SLA

Phía ops: logistics partner performance, stockout, route. Đây là mảng nặng của Shopee.

---

## H1 — Thời gian trung bình từ `paid_at` → `delivered_at`

**Level:** L1 | **Skill:** Date diff, AVG | **Est:** 10 phút

### 💡 SQL
```sql
SELECT
  ROUND(AVG(EXTRACT(EPOCH FROM (delivered_at - paid_at))/3600)::numeric, 1) AS avg_hours,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (delivered_at - paid_at))/3600
  )::numeric, 1) AS median_hours,
  ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (
    ORDER BY EXTRACT(EPOCH FROM (delivered_at - paid_at))/3600
  )::numeric, 1) AS p95_hours
FROM shopee.fact_orders
WHERE payment_status='paid'
  AND delivered_at IS NOT NULL
  AND paid_at IS NOT NULL;
```

### 🗣️ Cách giải thích
> "Luôn report cả mean, median, p95. Mean dễ bị kéo bởi outlier (đơn giao tỉnh xa 10 ngày). Median robust. P95 cho thấy 5% worst experience — rất quan trọng cho brand perception. Công thức: (EPOCH interval) / 3600 = hours."

### ⚠️ Common mistakes
- `delivered_at - paid_at` trong Postgres trả interval, không trực tiếp thành số. Phải qua EPOCH.
- Không filter NULL → nếu để lọt, calculation trả NULL silent.

### 🚀 Extension
Breakdown theo region (north/central/south) từ `dim_location` để thấy miền nào giao chậm.

---

## H2 — On-time delivery rate theo carrier

**Level:** L2 | **Skill:** Ratio, GROUP BY | **Est:** 15 phút

### 💡 SQL
```sql
SELECT
  carrier,
  COUNT(*)                                               AS shipments,
  COUNT(*) FILTER (WHERE is_on_time)                      AS on_time,
  ROUND(100.0 * COUNT(*) FILTER (WHERE is_on_time)
              / COUNT(*), 2)                              AS on_time_pct,
  ROUND(AVG(actual_hours)::numeric, 1)                    AS avg_actual_hours,
  ROUND(AVG(sla_committed_hours)::numeric, 1)             AS avg_committed_hours
FROM shopee.fact_shipment
WHERE delivered_at IS NOT NULL
GROUP BY carrier
ORDER BY on_time_pct DESC;
```

### 🗣️ Cách giải thích
> "SLA on-time rate là KPI logistics vàng. Shopee thường benchmark >= 92%. Carrier nào < 85% → review/phạt. Luôn kèm `avg_actual_hours` vs `avg_committed_hours` để thấy carrier 'committed chặt hay lỏng'."

### 🚀 Extension
Breakdown theo month — carrier có cải thiện/xuống dốc.

---

## H3 — **CASE: Carrier benchmark theo route**

**Level:** L3 | **Skill:** Multi-dim GROUP BY | **Est:** 25 phút

### 🎯 Business context
Gán carrier mặc định theo route → tối ưu cost + SLA. Không phải carrier nào cũng mạnh mọi route.

### 💡 SQL
```sql
SELECT
  o.ship_from_city,
  o.ship_to_city,
  sh.carrier,
  COUNT(*)                                           AS shipments,
  ROUND(100.0 * COUNT(*) FILTER (WHERE sh.is_on_time)/ COUNT(*), 2) AS on_time_pct,
  ROUND(AVG(sh.actual_hours)::numeric, 1)            AS avg_hours
FROM shopee.fact_shipment sh
JOIN shopee.fact_orders o ON o.order_id = sh.order_id
WHERE sh.delivered_at IS NOT NULL
  AND o.ship_from_city IN ('HCM','Hà Nội')
  AND o.ship_to_city   IN ('HCM','Hà Nội')
GROUP BY o.ship_from_city, o.ship_to_city, sh.carrier
HAVING COUNT(*) >= 100
ORDER BY o.ship_from_city, o.ship_to_city, on_time_pct DESC;
```

### 🗣️ Cách giải thích
> "Matrix (from, to, carrier). Mỗi route chọn carrier on-time top. Vd HCM→HN: SPX dẫn đầu 94%, HN→HCM: GHN 93%. Finding có thể action ngay: ops gán default carrier theo route."

### 🚀 Extension
Thêm cost (nếu có) → tìm carrier optimal: on-time cao mà cost thấp. Pareto frontier.

---

## H4 — % đơn ship chậm hơn SLA committed

**Level:** L2 | **Skill:** Ratio + filter | **Est:** 10 phút

### 💡 SQL
```sql
SELECT
  COUNT(*)                                                   AS total_shipments,
  COUNT(*) FILTER (WHERE actual_hours > sla_committed_hours) AS late,
  ROUND(100.0 * COUNT(*) FILTER (WHERE actual_hours > sla_committed_hours)
              / COUNT(*), 2)                                 AS late_pct,
  ROUND(AVG(actual_hours - sla_committed_hours)
         FILTER (WHERE actual_hours > sla_committed_hours)::numeric, 1) AS avg_overrun_hours
FROM shopee.fact_shipment
WHERE delivered_at IS NOT NULL;
```

### 🗣️ Cách giải thích
> "`is_on_time` đã có sẵn nhưng bài này tính lại từ raw columns để học viên biết nó được derive thế nào. `avg_overrun_hours` cho ngữ cảnh: trễ 2h khác hoàn toàn trễ 2 ngày."

### 🚀 Extension
Top 10 đơn trễ nhiều nhất (overrun lớn nhất) để ops team review root cause.

---

## H5 — Giờ nào đặt đơn bị ship chậm nhất?

**Level:** L3 | **Skill:** Hour extract, capacity analysis | **Est:** 25 phút

### 🎯 Business context
Nếu peak order hour → capacity overload → ship chậm, giải pháp là thêm shift hoặc limit promo theo giờ.

### 💡 SQL
```sql
WITH joined AS (
  SELECT
    EXTRACT(hour FROM o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::int AS hour_vn,
    sh.is_on_time
  FROM shopee.fact_orders o
  JOIN shopee.fact_shipment sh ON sh.order_id = o.order_id
  WHERE o.payment_status='paid' AND sh.delivered_at IS NOT NULL
)
SELECT
  hour_vn,
  COUNT(*)                                          AS shipments,
  ROUND(100.0 * COUNT(*) FILTER (WHERE is_on_time)
              / COUNT(*), 2)                        AS on_time_pct
FROM joined
GROUP BY hour_vn
ORDER BY hour_vn;
```

### 🗣️ Cách giải thích
> "Correlate order volume với on-time rate. Giờ 21-23 thường peak order + on-time thấp → capacity constraint. Ngược lại 2-5 sáng ít đơn mà on-time cũng thấp (?) → điều tra thêm (có thể seller chỉ process giờ hành chính)."

### 🚀 Extension
Thêm heatmap 7×24 (ngày × giờ) giống A6 nhưng metric là on_time_pct.

---

## H6 — Route volume cao nhưng SLA tệ

**Level:** L3 | **Skill:** Multi-dim, HAVING | **Est:** 25 phút

### 💡 SQL
```sql
SELECT
  o.ship_from_city, o.ship_to_province,
  COUNT(*)                                              AS shipments,
  ROUND(100.0 * COUNT(*) FILTER (WHERE sh.is_on_time)
              / COUNT(*), 2)                            AS on_time_pct
FROM shopee.fact_shipment sh
JOIN shopee.fact_orders   o ON o.order_id = sh.order_id
WHERE sh.delivered_at IS NOT NULL
GROUP BY o.ship_from_city, o.ship_to_province
HAVING COUNT(*) >= 200
ORDER BY on_time_pct ASC
LIMIT 10;
```

### 🗣️ Cách giải thích
> "Target 10 route nóng (volume cao + SLA tệ) → nếu fix được 10 route top, impact trên customer experience rất lớn. Prioritization rule: **volume × (1 - on_time_pct) = 'affected orders'**. Đây là cách pick battles có ROI cao."

### 🚀 Extension
Tính `affected_orders = shipments × (100 - on_time_pct)/100` để rank đúng.

---

## H7 — **CASE: Stockout impact** — SKU hết hàng có làm mất đơn?

**Level:** L4 | **Skill:** Multi-fact temporal join | **Est:** 50 phút

### 🎯 Business context
Nếu SKU hết hàng, demand chuyển sang SKU thay thế hoặc mất luôn? Impact phải đo được để inventory team quyết stocking level.

### 🧭 Approach
1. Với mỗi SKU, tìm tuần `is_in_stock = FALSE`.
2. So GMV tuần đó vs tuần có stock.
3. Aggregate lên cat2 để tránh noise per SKU.

### 💡 SQL
```sql
WITH weekly_sku AS (
  SELECT
    i.product_id,
    DATE_TRUNC('week',(SELECT full_date FROM shopee.dim_date WHERE date_key=o.order_date_key))::date AS week_start,
    SUM(i.line_total) AS gmv
  FROM shopee.fact_order_items i
  JOIN shopee.fact_orders o ON o.order_id = i.order_id
  WHERE o.payment_status='paid'
  GROUP BY i.product_id, DATE_TRUNC('week',(SELECT full_date FROM shopee.dim_date WHERE date_key=o.order_date_key))
),
stock AS (
  SELECT
    product_id,
    DATE_TRUNC('week',(SELECT full_date FROM shopee.dim_date WHERE date_key=snapshot_date_key))::date AS week_start,
    BOOL_AND(is_in_stock) AS in_stock_all_week
  FROM shopee.fact_inventory_weekly
  GROUP BY product_id, DATE_TRUNC('week',(SELECT full_date FROM shopee.dim_date WHERE date_key=snapshot_date_key))
),
joined AS (
  SELECT w.product_id, w.week_start, w.gmv, s.in_stock_all_week,
         p.cat2_name
  FROM weekly_sku w
  LEFT JOIN stock s ON s.product_id = w.product_id AND s.week_start = w.week_start
  JOIN shopee.dim_product p ON p.product_id = w.product_id
)
SELECT
  cat2_name,
  ROUND(AVG(gmv) FILTER (WHERE in_stock_all_week), 0)     AS avg_gmv_in_stock,
  ROUND(AVG(gmv) FILTER (WHERE NOT in_stock_all_week), 0) AS avg_gmv_oos,
  ROUND(
    100.0 * (AVG(gmv) FILTER (WHERE NOT in_stock_all_week) - AVG(gmv) FILTER (WHERE in_stock_all_week))
          / NULLIF(AVG(gmv) FILTER (WHERE in_stock_all_week), 0)
  , 2) AS pct_drop_when_oos
FROM joined
GROUP BY cat2_name
HAVING COUNT(*) FILTER (WHERE NOT in_stock_all_week) >= 10
ORDER BY pct_drop_when_oos;
```

### 🗣️ Cách giải thích
> "Đây là 'natural experiment': so chính 1 cat2 khi có stock vs khi OOS. `BOOL_AND(is_in_stock)` = TRUE chỉ khi **tất cả** snapshot trong tuần đều in-stock. OOS thật sự phải kéo dài cả tuần mới tính.
>
> **Expected insight:** cat đặc thù (iPhone) OOS làm sụt 80% vì ít thay thế. Cat commodity (t-shirt basic) OOS chỉ sụt 10% vì substitute nhiều. Inventory team dùng insight này set safety stock khác nhau theo cat."

### ⚠️ Common mistakes
- Không match exactly 'same week' giữa inventory snapshot và order week → so lệch.
- Quên `BOOL_AND` → 1 day OOS trong tuần cũng count, noise lớn.

### 🚀 Extension
Thêm thời gian lead: OOS tuần N có ảnh hưởng GMV tuần N+1 không? (demand carry-over hay mất hẳn).
