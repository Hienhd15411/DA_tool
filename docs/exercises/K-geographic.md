# Chủ đề K — Geographic analysis

Theo tỉnh / thành / miền — giúp chiến lược expansion và logistics.

---

## K1 — Top 10 tỉnh/thành theo GMV

**Level:** L1 | **Skill:** GROUP BY | **Est:** 5 phút

### 💡 SQL
```sql
SELECT
  ship_to_province,
  COUNT(*)                             AS orders,
  SUM(total_amount)                    AS gmv,
  COUNT(DISTINCT customer_id)          AS buyers
FROM shopee.fact_orders
WHERE payment_status='paid'
GROUP BY ship_to_province
ORDER BY gmv DESC
LIMIT 10;
```

### 🗣️ Cách giải thích
> "HCM và HN thường chiếm 40-50% GMV. Biết distribution để plan warehouse, CS lang, KOL geo-targeting."

### 🚀 Extension
Thêm % GMV so tổng bằng `SUM(total_amount) OVER ()`.

---

## K2 — GMV bình quân đầu khách theo tỉnh

**Level:** L2 | **Skill:** Ratio | **Est:** 10 phút

### 💡 SQL
```sql
SELECT
  ship_to_province,
  COUNT(DISTINCT customer_id)                                          AS buyers,
  SUM(total_amount)                                                    AS gmv,
  ROUND(SUM(total_amount)::numeric / COUNT(DISTINCT customer_id), 0)   AS gmv_per_buyer
FROM shopee.fact_orders
WHERE payment_status='paid'
GROUP BY ship_to_province
HAVING COUNT(DISTINCT customer_id) >= 100
ORDER BY gmv_per_buyer DESC
LIMIT 20;
```

### 🗣️ Cách giải thích
> "GMV/buyer đo 'chi tiêu trung bình' mỗi khách ở tỉnh. Tỉnh có gmv_per_buyer cao thường là thành phố lớn (HCM, HN) hoặc tỉnh có tầng lớp trung lưu. Tỉnh buyer nhiều nhưng gmv_per_buyer thấp = khách price-sensitive."

### 🚀 Extension
Tách thêm theo tier khách (gold+platinum) — VIP tập trung ở đâu.

---

## K3 — Tỉnh nào AOV cao nhất

**Level:** L1 | **Skill:** AVG, GROUP BY | **Est:** 5 phút

### 💡 SQL
```sql
SELECT
  ship_to_province,
  COUNT(*)                    AS orders,
  ROUND(AVG(total_amount), 0) AS aov
FROM shopee.fact_orders
WHERE payment_status='paid'
GROUP BY ship_to_province
HAVING COUNT(*) >= 500
ORDER BY aov DESC
LIMIT 10;
```

### 🗣️ Cách giải thích
> "AOV cao ở tỉnh không trùng top GMV — tỉnh nhỏ nhưng AOV cao là tín hiệu nhóm thu nhập cao, premium cat bán được. Shopee Mall / flagship có thể geo-target."

### 🚀 Extension
Breakdown AOV by cat1 trong top 5 tỉnh AOV cao → cat nào driver?

---

## K4 — Route liên vùng (Bắc ↔ Nam) volume & SLA

**Level:** L3 | **Skill:** Multi-dim JOIN dim_location | **Est:** 30 phút

### 💡 SQL
```sql
WITH loc_map AS (
  SELECT city, region
  FROM shopee.dim_location
),
order_region AS (
  SELECT
    o.order_id, o.ship_to_city,
    fr.region AS from_region,
    tr.region AS to_region,
    sh.is_on_time
  FROM shopee.fact_orders o
  JOIN shopee.fact_shipment sh ON sh.order_id = o.order_id
  LEFT JOIN loc_map fr ON fr.city = o.ship_from_city
  LEFT JOIN loc_map tr ON tr.city = o.ship_to_city
  WHERE sh.delivered_at IS NOT NULL
)
SELECT
  from_region, to_region,
  COUNT(*)                                                  AS shipments,
  ROUND(100.0 * COUNT(*) FILTER (WHERE is_on_time)/ COUNT(*), 2) AS on_time_pct
FROM order_region
WHERE from_region IS NOT NULL AND to_region IS NOT NULL
GROUP BY from_region, to_region
ORDER BY from_region, to_region;
```

### 🗣️ Cách giải thích
> "Matrix 3×3 (N/C/S × N/C/S). Route liên miền (N↔S) thường SLA thấp hơn intra-region (HCM→HCM). Data này dùng để calibrate SLA theo route thay vì SLA flat toàn quốc."

### 🚀 Extension
Thêm breakdown theo carrier trong route liên miền — carrier nào mạnh nhất tuyến Bắc-Nam.

---

## K5 — **CASE: Thị trường tiềm năng** — tỉnh nào có growth rate cao nhưng base thấp

**Level:** L4 | **Skill:** Growth matrix | **Est:** 45 phút

### 🎯 Business context
Expansion team muốn chọn 5 tỉnh để invest (set warehouse, KOL, ads geo-target). Tỉnh lớn đã saturate; tỉnh tiềm năng = growth cao + base chưa lớn → room to grow.

### 💡 SQL
```sql
WITH monthly AS (
  SELECT
    o.ship_to_province,
    DATE_TRUNC('month', d.full_date)::date AS mth,
    SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY o.ship_to_province, DATE_TRUNC('month', d.full_date)
),
growth AS (
  SELECT
    ship_to_province,
    SUM(gmv) FILTER (WHERE mth = DATE '2024-02-01') AS gmv_feb,
    SUM(gmv) FILTER (WHERE mth = DATE '2024-04-01') AS gmv_apr,
    ROUND(
      100.0 * (SUM(gmv) FILTER (WHERE mth = DATE '2024-04-01')
               - SUM(gmv) FILTER (WHERE mth = DATE '2024-02-01'))
              / NULLIF(SUM(gmv) FILTER (WHERE mth = DATE '2024-02-01'), 0)
    , 2) AS growth_pct
  FROM monthly
  GROUP BY ship_to_province
),
scored AS (
  SELECT
    ship_to_province, gmv_feb, gmv_apr, growth_pct,
    NTILE(4) OVER (ORDER BY gmv_apr DESC) AS size_quartile,
    NTILE(4) OVER (ORDER BY growth_pct DESC) AS growth_quartile
  FROM growth
  WHERE gmv_feb IS NOT NULL AND gmv_apr IS NOT NULL
)
SELECT *,
  CASE
    WHEN size_quartile <= 2 AND growth_quartile = 1 THEN 'STAR — đầu tư mạnh'
    WHEN size_quartile = 1 AND growth_quartile <= 2 THEN 'CASH COW — giữ'
    WHEN size_quartile >= 3 AND growth_quartile = 1 THEN 'EMERGING — thử nghiệm'
    WHEN size_quartile >= 3 AND growth_quartile = 4 THEN 'DOG — cắt'
    ELSE 'Others'
  END AS segment
FROM scored
WHERE segment IN ('STAR — đầu tư mạnh','EMERGING — thử nghiệm')
ORDER BY growth_pct DESC;
```

### 🗣️ Cách giải thích
> "Boston matrix (BCG) áp dụng cho geographic expansion. 2 chiều: size (quartile theo GMV Apr) × growth (quartile theo growth Feb→Apr). STAR = tỉnh trung bình lớn đang tăng mạnh (nên bơm đầu tư). EMERGING = tỉnh nhỏ đang tăng (thử nghiệm rủi ro thấp). Output là **shortlist cụ thể** mà business có thể cầm đi họp.
>
> **Caveat:** growth % dễ bị inflated khi base nhỏ (tỉnh Feb 10M, Apr 30M = 200% growth, ấn tượng nhưng absolute value nhỏ). Luôn hiển thị cả growth_pct và gmv_apr để PM tự weigh."

### ⚠️ Common mistakes
- Chỉ sort theo growth → chọn tỉnh base tí hon, không scale được.
- Chỉ sort theo size → chọn tỉnh đã bão hoà (HN, HCM).
- Pivot `FILTER` mà quên `GROUP BY province` → tổng toàn sàn.

### 🚀 Extension
Thêm chiều thứ 3: tỉnh có late_ship_pct cao → STAR cần cảnh báo (expand phải kèm logistics plan).
