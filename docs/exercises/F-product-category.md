# Chủ đề F — Product & Category (4-level hierarchy)

Tận dụng cây category 4 tầng (`cat1 → cat2 → cat3 → cat4`). Dạy drill-down, recursive CTE, slow-mover analysis.

---

## F1 — GMV theo từng cấp cat1, cat2, cat3, cat4

**Level:** L1 | **Skill:** drill-down GROUP BY | **Est:** 10 phút

### 💡 SQL
```sql
-- cấp 1
SELECT p.cat1_name, SUM(i.line_total) AS gmv
FROM shopee.fact_order_items i
JOIN shopee.fact_orders o  ON o.order_id = i.order_id
JOIN shopee.dim_product p  ON p.product_id = i.product_id
WHERE o.payment_status='paid'
GROUP BY p.cat1_name ORDER BY gmv DESC;
```

Lặp tương tự cho `cat2`, `cat3`, `cat4`. Hoặc dùng `ROLLUP`:

```sql
SELECT
  p.cat1_name, p.cat2_name, p.cat3_name,
  SUM(i.line_total) AS gmv
FROM shopee.fact_order_items i
JOIN shopee.fact_orders  o ON o.order_id = i.order_id
JOIN shopee.dim_product  p ON p.product_id = i.product_id
WHERE o.payment_status='paid'
GROUP BY ROLLUP (p.cat1_name, p.cat2_name, p.cat3_name)
ORDER BY p.cat1_name NULLS LAST, p.cat2_name NULLS LAST, p.cat3_name NULLS LAST;
```

### 🗣️ Cách giải thích
> "`ROLLUP(a,b,c)` tự sinh các tổ hợp subtotal: `(a,b,c)`, `(a,b)`, `(a)`, `()`. NULL trong kết quả = dòng subtotal. Rất gọn thay vì 4 query riêng. Dành cho người đã quen — với học viên mới hãy dạy từng cấp trước."

### 🚀 Extension
Thử `GROUPING SETS` để chọn combination chính xác.

---

## F2 — Top 10 cat4 bán chạy nhất mỗi cat1

**Level:** L3 | **Skill:** `ROW_NUMBER() PARTITION BY` | **Est:** 20 phút

### 🎯 Business context
Category team cần xác định "star SKU family" mỗi ngành → làm featured trong Shopee Mall.

### 💡 SQL
```sql
WITH cat4_gmv AS (
  SELECT p.cat1_name, p.cat4_name, SUM(i.line_total) AS gmv
  FROM shopee.fact_order_items i
  JOIN shopee.fact_orders  o ON o.order_id = i.order_id
  JOIN shopee.dim_product  p ON p.product_id = i.product_id
  WHERE o.payment_status='paid'
  GROUP BY p.cat1_name, p.cat4_name
),
ranked AS (
  SELECT *,
    ROW_NUMBER() OVER (PARTITION BY cat1_name ORDER BY gmv DESC) AS rn
  FROM cat4_gmv
)
SELECT cat1_name, cat4_name, gmv, rn
FROM ranked
WHERE rn <= 10
ORDER BY cat1_name, rn;
```

### 🗣️ Cách giải thích
> "Pattern 'top N per group' kinh điển: (1) aggregate per (group, item), (2) `ROW_NUMBER() PARTITION BY group ORDER BY metric DESC`, (3) filter `rn <= N`. `ROW_NUMBER` khác `RANK`/`DENSE_RANK` ở cách xử lý tie — `ROW_NUMBER` luôn cho thứ tự duy nhất, `RANK` skip số khi tie, `DENSE_RANK` không skip."

### ⚠️ Common mistakes
- Dùng `LIMIT 10` thay vì `ROW_NUMBER` — chỉ lấy 10 dòng top toàn cục, không per cat1.
- `ROW_NUMBER()` không có `ORDER BY` → random, không xác định.

### 🚀 Extension
Thêm % share của cat4 trong tổng cat1 (`gmv / SUM(gmv) OVER (PARTITION BY cat1_name)`).

---

## F3 — **Recursive CTE** in cây category

**Level:** L3 | **Skill:** `WITH RECURSIVE` | **Est:** 30 phút

### 🎯 Business context
Khi cây có chiều sâu chưa biết trước (ví dụ cat tree sàn khác có 6 tầng), không thể JOIN tay. Recursive CTE là công cụ chuẩn.

### 💡 SQL
```sql
WITH RECURSIVE tree AS (
  -- base case: các cat cấp 1
  SELECT category_id, category_name, level, parent_id,
         category_name::text AS path
  FROM shopee.dim_category
  WHERE level = 1

  UNION ALL

  -- recursive case: join child với parent đã build
  SELECT c.category_id, c.category_name, c.level, c.parent_id,
         (t.path || ' > ' || c.category_name)::text
  FROM shopee.dim_category c
  JOIN tree t ON c.parent_id = t.category_id
)
SELECT category_id, level, path
FROM tree
ORDER BY path;
```

### ✅ Expected result
| category_id | level | path |
|---|---|---|
| 1 | 1 | Điện Tử |
| 11 | 2 | Điện Tử > Điện Thoại |
| 111 | 3 | Điện Tử > Điện Thoại > Smartphone |
| 1111 | 4 | Điện Tử > Điện Thoại > Smartphone > iPhone |

### 🗣️ Cách giải thích
> "Cú pháp: `WITH RECURSIVE name AS (base_query UNION ALL recursive_query)`. Base = seed (cấp 1), recursive tham chiếu chính `name` để đi xuống. Postgres chạy recursive cho đến khi recursive_query trả 0 row. Quan trọng: phải có điều kiện dừng (ở đây là parent_id không match → recursive trả rỗng). Nếu cat tree có cycle (bug), sẽ vòng lặp vô hạn."

### ⚠️ Common mistakes
- Quên `UNION ALL` (viết `UNION`) → dedup mỗi step, chậm và có thể sai.
- Join sai chiều: `c.category_id = t.parent_id` thay vì `c.parent_id = t.category_id`.

### 🚀 Extension
Cắt một subtree: thay base case bằng `WHERE category_id = <X>` để in con cháu của cat X.

---

## F4 — Slow-mover: SKU chưa bán đơn nào 3 tháng

**Level:** L2 | **Skill:** Anti-join | **Est:** 15 phút

### 🎯 Business context
SKU không bán = tốn slot index, tồn kho. Merchandising phải review/xoá.

### 💡 SQL
```sql
SELECT p.product_id, p.product_name, p.seller_id, p.cat1_name, p.launch_date
FROM shopee.dim_product p
LEFT JOIN shopee.fact_order_items i ON i.product_id = p.product_id
WHERE p.is_active
  AND i.product_id IS NULL
  AND p.launch_date <= DATE '2024-02-01'   -- ít nhất 3 tháng
ORDER BY p.launch_date;
```

Hoặc dùng `NOT EXISTS`:
```sql
SELECT p.product_id, p.product_name
FROM shopee.dim_product p
WHERE p.is_active
  AND NOT EXISTS (
    SELECT 1 FROM shopee.fact_order_items i WHERE i.product_id = p.product_id
  )
  AND p.launch_date <= DATE '2024-02-01';
```

### 🗣️ Cách giải thích
> "Anti-join có 2 cách viết: `LEFT JOIN ... WHERE right.key IS NULL` và `NOT EXISTS`. `NOT EXISTS` thường được optimizer ưu tiên (semi-anti-join plan), code cũng rõ ý đồ hơn — dùng khi có thể. `LEFT JOIN` pattern vẫn phổ biến khi muốn lấy thêm cột từ bảng phải."

### ⚠️ Common mistakes
- `NOT IN` + subquery có NULL → trả rỗng do SQL three-valued logic. Luôn dùng `NOT EXISTS` khi nghi có NULL.

### 🚀 Extension
Phân tách slow-mover theo tuổi: SKU mới (<30d), trung (30–60d), cũ (>60d). SKU mới chưa bán có thể do chưa được promote.

---

## F5 — Top SKU có tỷ lệ return cao nhất

**Level:** L2 | **Skill:** JOIN fact_returns, ratio | **Est:** 15 phút

### 💡 SQL
```sql
WITH item_stats AS (
  SELECT
    i.product_id,
    COUNT(DISTINCT i.order_item_id) AS sold,
    COUNT(DISTINCT r.return_id)     AS returned
  FROM shopee.fact_order_items i
  LEFT JOIN shopee.fact_returns r ON r.order_item_id = i.order_item_id
                                  AND r.return_status IN ('approved','completed')
  GROUP BY i.product_id
  HAVING COUNT(DISTINCT i.order_item_id) >= 30
)
SELECT
  p.product_id, p.product_name, p.cat1_name, p.cat4_name,
  s.sold, s.returned,
  ROUND(100.0 * s.returned / s.sold, 2) AS return_rate_pct
FROM item_stats s
JOIN shopee.dim_product p ON p.product_id = s.product_id
ORDER BY return_rate_pct DESC
LIMIT 20;
```

### 🗣️ Cách giải thích
> "Lại pattern `HAVING COUNT >= N` để tránh noise. Với SKU bán chỉ 2 cái, 1 cái bị trả → return rate 50%, không đủ evidence. Ngưỡng 30 là lựa chọn thực dụng. Return rate cao liên tục = vấn đề chất lượng hoặc mô tả lừa đảo."

### 🚀 Extension
Breakdown `return_reason` cho từng SKU — do chất lượng, sai mô tả, hay giao hỏng?

---

## F6 — **CASE: Ngành hàng đang suy giảm** — cat1 nào MoM giảm 3 tháng liên tiếp?

**Level:** L4 | **Skill:** LAG sequence, trend detection | **Est:** 40 phút

### 🎯 Business context
Category team cần biết "ngành nào đang rơi" để can thiệp sớm: họp seller, thay merchandising plan, cắt promotion không hiệu quả.

### 💡 SQL
```sql
WITH monthly AS (
  SELECT
    p.cat1_name,
    DATE_TRUNC('month', d.full_date)::date AS mth,
    SUM(i.line_total) AS gmv
  FROM shopee.fact_order_items i
  JOIN shopee.fact_orders  o ON o.order_id = i.order_id
  JOIN shopee.dim_date     d ON d.date_key = o.order_date_key
  JOIN shopee.dim_product  p ON p.product_id = i.product_id
  WHERE o.payment_status='paid'
  GROUP BY p.cat1_name, DATE_TRUNC('month', d.full_date)
),
with_lag AS (
  SELECT
    cat1_name, mth, gmv,
    LAG(gmv, 1) OVER (PARTITION BY cat1_name ORDER BY mth) AS gmv_m1,
    LAG(gmv, 2) OVER (PARTITION BY cat1_name ORDER BY mth) AS gmv_m2
  FROM monthly
)
SELECT
  cat1_name, mth, gmv, gmv_m1, gmv_m2,
  CASE
    WHEN gmv < gmv_m1 AND gmv_m1 < gmv_m2 THEN 'DOWN 3 months'
    WHEN gmv > gmv_m1 AND gmv_m1 > gmv_m2 THEN 'UP 3 months'
    ELSE 'mixed'
  END AS trend
FROM with_lag
WHERE mth = (SELECT MAX(mth) FROM monthly)   -- chỉ nhìn tháng mới nhất
  AND gmv_m2 IS NOT NULL
ORDER BY
  CASE WHEN gmv < gmv_m1 AND gmv_m1 < gmv_m2 THEN 1 ELSE 2 END,
  (gmv_m2 - gmv) DESC;
```

### 🗣️ Cách giải thích
> "Dùng `LAG(gmv, 1)` và `LAG(gmv, 2)` trên cùng partition để lấy tháng trước và tháng trước nữa. Filter `mth = max` chỉ show snapshot hiện tại. Pattern 3 tháng liên tục là: `m0 < m-1 < m-2`. Sort theo size drop (`gmv_m2 - gmv`) để priority hoá.
>
> **Action:** với list 'DOWN 3 months' kèm size drop, category manager biết nên interview seller nào, xem lại pricing/traffic/voucher cho cat đó."

### ⚠️ Common mistakes
- Dataset chỉ 3 tháng nên tháng đầu có `gmv_m2 IS NULL` — filter kỹ.
- Dùng tháng dương lịch mà quên tháng Tết ngắn hoặc data bắt đầu giữa tháng → lệch.

### 🚀 Extension
Xuống cat2: trong cat1 'DOWN', cat2 nào là nguyên nhân chính.

---

## F7 — Price elasticity giả lập

**Level:** L3 | **Skill:** bucketize, aggregate | **Est:** 30 phút

### 🎯 Business context
Không có A/B test thực, nhưng có thể quan sát: trong 1 cat, SKU thuộc bucket giá nào bán được nhiều nhất → hint về điểm giá tối ưu.

### 💡 SQL
```sql
WITH sku_stats AS (
  SELECT
    p.cat1_name, p.product_id, p.list_price,
    NTILE(5) OVER (PARTITION BY p.cat1_name ORDER BY p.list_price) AS price_bucket,
    SUM(i.quantity) AS units_sold,
    SUM(i.line_total) AS gmv
  FROM shopee.dim_product p
  LEFT JOIN shopee.fact_order_items i ON i.product_id = p.product_id
  LEFT JOIN shopee.fact_orders o      ON o.order_id = i.order_id AND o.payment_status='paid'
  GROUP BY p.cat1_name, p.product_id, p.list_price
)
SELECT
  cat1_name, price_bucket,
  COUNT(*)                      AS sku_count,
  ROUND(AVG(list_price),0)      AS avg_price,
  ROUND(AVG(units_sold),1)      AS avg_units_per_sku,
  SUM(gmv)                      AS total_gmv
FROM sku_stats
GROUP BY cat1_name, price_bucket
ORDER BY cat1_name, price_bucket;
```

### 🗣️ Cách giải thích
> "`NTILE(5) PARTITION BY cat1` chia SKU trong mỗi cat1 thành 5 dải giá từ rẻ (bucket 1) đến đắt (bucket 5). Rồi so `avg_units_per_sku` qua 5 bucket — bucket nào bán trung bình được nhiều nhất. Đây KHÔNG phải elasticity chính thống (cần cùng 1 SKU thay đổi giá), nhưng cho hint nhanh. Insight kiểu: 'ngành Fashion Nữ, SKU bucket 2 (giá rẻ-trung) bán trung bình 3× bucket 5 (cao cấp)'."

### 🚀 Extension
Refine bằng loại bỏ SKU launch < 30 ngày (chưa ổn định).

---

## F8 — Category mix shift (tháng này vs tháng trước)

**Level:** L3 | **Skill:** share calculation, diff | **Est:** 25 phút

### 🎯 Business context
Tổng GMV có thể không đổi nhưng cơ cấu ngành thay đổi. Biết được shift giúp merchandising re-plan stock.

### 💡 SQL
```sql
WITH m AS (
  SELECT
    p.cat1_name,
    DATE_TRUNC('month', d.full_date)::date AS mth,
    SUM(i.line_total) AS gmv
  FROM shopee.fact_order_items i
  JOIN shopee.fact_orders  o ON o.order_id = i.order_id
  JOIN shopee.dim_date     d ON d.date_key = o.order_date_key
  JOIN shopee.dim_product  p ON p.product_id = i.product_id
  WHERE o.payment_status='paid'
  GROUP BY p.cat1_name, DATE_TRUNC('month', d.full_date)
),
share AS (
  SELECT cat1_name, mth, gmv,
    gmv::numeric / SUM(gmv) OVER (PARTITION BY mth) * 100 AS share_pct
  FROM m
)
SELECT
  cat1_name,
  MAX(share_pct) FILTER (WHERE mth = DATE '2024-03-01') AS share_mar,
  MAX(share_pct) FILTER (WHERE mth = DATE '2024-04-01') AS share_apr,
  ROUND(
    MAX(share_pct) FILTER (WHERE mth = DATE '2024-04-01')
    - MAX(share_pct) FILTER (WHERE mth = DATE '2024-03-01')
  , 2) AS share_delta_pp
FROM share
GROUP BY cat1_name
ORDER BY share_delta_pp DESC;
```

### 🗣️ Cách giải thích
> "`SUM(gmv) OVER (PARTITION BY mth)` = GMV tổng của tháng đó, dùng làm mẫu số để tính share. Delta `pp` (percentage point) đo change tuyệt đối của share — cat1 tăng 3pp từ 12% → 15% là shift đáng kể trong 1 tháng."

### 🚀 Extension
Cùng pattern nhưng down cat2, hoặc áp dụng cho payment_method / device_type.
