# Chủ đề B — Customer lifecycle / Cohort / Retention

Dạy học viên nhìn khách hàng theo chiều thời gian: mới-quay lại-rời bỏ, và cách segment để hành động.

---

## B1 — Bao nhiêu khách mới (first_order) mỗi tháng?

**Level:** L1 | **Skill:** filter + GROUP BY | **Est:** 8 phút

### 🎯 Business context
New buyer count là KPI marketing. Growth team luôn cần biết kênh mới có kéo khách không.

### 🧭 Approach
Filter `is_first_order = TRUE`, GROUP BY tháng.

### 💡 SQL
```sql
SELECT
  DATE_TRUNC('month', d.full_date)::date AS month,
  COUNT(DISTINCT o.customer_id)          AS new_buyers
FROM shopee.fact_orders o
JOIN shopee.dim_date d ON d.date_key = o.order_date_key
WHERE o.is_first_order = TRUE
  AND o.payment_status = 'paid'
GROUP BY 1
ORDER BY 1;
```

### ✅ Expected result
| month | new_buyers |
|---|---|
| 2024-02-01 | 4,200 |
| 2024-03-01 | 5,800 |
| 2024-04-01 | 4,900 |

### 🗣️ Cách giải thích
> "`is_first_order` được pre-compute ở ETL (đánh dấu đơn đầu tiên của customer). Nếu không có cờ này, ta phải tự tính bằng `MIN(created_at) OVER (PARTITION BY customer_id)` — mà cách đó tốn resource. Trong production, data team luôn pre-compute để analyst viết query gọn."

### ⚠️ Common mistakes
- Không dùng `DISTINCT customer_id` — nếu 1 khách có nhiều `is_first_order=TRUE` (bug ETL) thì đếm sai.
- Filter `paid` quan trọng: khách "đặt đơn đầu rồi huỷ" không tính là new buyer thật.

### 🚀 Extension
Thêm breakdown theo `dim_customer.city` — thành phố nào kéo khách mới mạnh nhất.

---

## B2 — Top 10 khách chi tiêu nhiều nhất 3 tháng

**Level:** L1 | **Skill:** GROUP BY, ORDER BY, LIMIT | **Est:** 5 phút

### 🎯 Business context
VIP list cho CRM team (gửi voucher sinh nhật, tặng gift).

### 💡 SQL
```sql
SELECT
  c.customer_id,
  c.customer_name,
  c.tier,
  COUNT(*)            AS orders,
  SUM(o.total_amount) AS total_spent
FROM shopee.fact_orders o
JOIN shopee.dim_customer c ON c.customer_id = o.customer_id
WHERE o.payment_status='paid'
GROUP BY c.customer_id, c.customer_name, c.tier
ORDER BY total_spent DESC
LIMIT 10;
```

### 🗣️ Cách giải thích
> "Bài đơn giản nhưng common mistake: quên put `customer_name` vào `GROUP BY`. Postgres bắt buộc mọi non-aggregate column phải có trong GROUP BY (hoặc FK của nó). Có thể dùng `GROUP BY c.customer_id` nếu `customer_id` là primary key — PG cho phép functional dependency."

### ⚠️ Common mistakes
- Dùng `DISTINCT ON` sai — ở đây không cần.
- Quên LIMIT → trả 50k dòng.

### 🚀 Extension
Hiển thị thêm `ngày đặt đơn gần nhất` (`MAX(created_at)`) để CRM biết khách còn active không.

---

## B3 — **RFM segmentation** (Recency / Frequency / Monetary)

**Level:** L3 | **Skill:** `NTILE`, nested CTE, `CASE` | **Est:** 40 phút

### 🎯 Business context
RFM là framework kinh điển nhất để segment khách. Output 11 segment (Champion, Loyal, Potential Loyalist, At Risk, Can't Lose, Lost, ...) dùng ngay cho CRM campaign.

### 🧭 Approach
1. Với mỗi khách, tính 3 số: `recency` (ngày từ đơn gần nhất đến "hôm nay"), `frequency` (số đơn), `monetary` (tổng chi).
2. Phân vị hoá bằng `NTILE(5)` — chia đều khách thành 5 nhóm mỗi chiều.
3. Dùng `CASE` map combination (R, F, M) → tên segment.

### 💡 SQL
```sql
WITH base AS (
  SELECT
    o.customer_id,
    MAX(o.created_at)::date                       AS last_order_date,
    COUNT(*)                                      AS freq,
    SUM(o.total_amount)                           AS monetary
  FROM shopee.fact_orders o
  WHERE o.payment_status='paid'
  GROUP BY o.customer_id
),
scored AS (
  SELECT
    customer_id,
    (DATE '2024-04-30' - last_order_date)               AS recency_days,
    freq, monetary,
    NTILE(5) OVER (ORDER BY last_order_date DESC)       AS r_score,  -- gần nhất = 5
    NTILE(5) OVER (ORDER BY freq ASC)                   AS f_score,
    NTILE(5) OVER (ORDER BY monetary ASC)               AS m_score
  FROM base
)
SELECT
  customer_id, recency_days, freq, monetary,
  r_score, f_score, m_score,
  CASE
    WHEN r_score=5 AND f_score>=4 AND m_score>=4 THEN 'Champion'
    WHEN r_score>=4 AND f_score>=3                THEN 'Loyal'
    WHEN r_score=5 AND f_score<=2                 THEN 'New/Potential'
    WHEN r_score<=2 AND f_score>=4 AND m_score>=4 THEN 'Cant Lose'
    WHEN r_score<=2 AND f_score>=3                THEN 'At Risk'
    WHEN r_score<=2 AND f_score<=2                THEN 'Lost'
    ELSE 'Others'
  END AS segment
FROM scored;
```

### ✅ Expected result (distribution)
| segment | cnt | avg_monetary |
|---|---|---|
| Champion | 1,200 | 4.8M |
| Loyal | 3,400 | 2.1M |
| At Risk | 2,100 | 1.9M |
| Lost | 5,800 | 420k |

### 🗣️ Cách giải thích
> "RFM là con dao Thuỵ Sĩ của CRM. Recency = 'khách có còn active không'; Frequency = 'khách có thường xuyên không'; Monetary = 'khách có đáng tiền không'. `NTILE(5)` chia khách ra 5 nhóm bằng nhau theo từng chiều — phân vị hoá kiểu này tốt hơn set threshold cứng (vd freq>5) vì tự adapt với phân phối data. Segment map chỉ là quy ước — đội CRM có thể dùng version 11 segment đầy đủ hoặc đơn giản hoá thành 4 quadrant."

### ⚠️ Common mistakes
- Thứ tự `NTILE` ngược: Recency ngày càng mới càng tốt → `ORDER BY last_order_date DESC`, không phải ASC.
- Lấy "hôm nay" động (`CURRENT_DATE`) trong demo sẽ ra khác lúc chạy lại — fix cứng `DATE '2024-04-30'` cho đúng dataset.
- Chỉ tính khách từng mua — khách chưa bao giờ mua không trong `fact_orders`.

### 🚀 Extension
Tính size + gmv contribution của mỗi segment → Pareto chart để priority targeting.

---

## B4 — **Cohort retention** (ma trận)

**Level:** L3 | **Skill:** cohort, self-join, pivot | **Est:** 50 phút

### 🎯 Business context
Retention là chỉ số sống còn. Cohort = nhóm khách ký sign-up trong cùng tháng. Ma trận retention cho thấy % khách của cohort M0 còn mua ở M1, M2.

### 🧭 Approach
1. Xác định cohort của mỗi khách = tháng đơn đầu tiên.
2. Đếm số tháng khách còn active từ cohort đó (gap = order_month - cohort_month).
3. Pivot: hàng = cohort month, cột = gap (M0, M1, M2), giá trị = distinct customer.

### 💡 SQL
```sql
WITH first_order AS (
  SELECT customer_id, DATE_TRUNC('month', MIN(created_at))::date AS cohort_month
  FROM shopee.fact_orders
  WHERE payment_status='paid'
  GROUP BY customer_id
),
activity AS (
  SELECT
    f.cohort_month,
    DATE_TRUNC('month', o.created_at)::date AS order_month,
    o.customer_id
  FROM shopee.fact_orders o
  JOIN first_order f ON f.customer_id = o.customer_id
  WHERE o.payment_status='paid'
),
cohort_matrix AS (
  SELECT
    cohort_month,
    EXTRACT(MONTH FROM AGE(order_month, cohort_month))::int AS gap_month,
    COUNT(DISTINCT customer_id) AS buyers
  FROM activity
  GROUP BY cohort_month, gap_month
)
SELECT
  cohort_month,
  MAX(buyers) FILTER (WHERE gap_month=0) AS m0,
  MAX(buyers) FILTER (WHERE gap_month=1) AS m1,
  MAX(buyers) FILTER (WHERE gap_month=2) AS m2,
  ROUND(100.0 * MAX(buyers) FILTER (WHERE gap_month=1)
               / NULLIF(MAX(buyers) FILTER (WHERE gap_month=0),0), 1) AS m1_ret_pct,
  ROUND(100.0 * MAX(buyers) FILTER (WHERE gap_month=2)
               / NULLIF(MAX(buyers) FILTER (WHERE gap_month=0),0), 1) AS m2_ret_pct
FROM cohort_matrix
GROUP BY cohort_month
ORDER BY cohort_month;
```

### ✅ Expected result
| cohort_month | m0 | m1 | m2 | m1_ret_pct | m2_ret_pct |
|---|---|---|---|---|---|
| 2024-02-01 | 4,200 | 1,300 | 820 | 31.0 | 19.5 |
| 2024-03-01 | 5,800 | 1,600 | NULL | 27.6 | NULL |
| 2024-04-01 | 4,900 | NULL | NULL | NULL | NULL |

### 🗣️ Cách giải thích
> "`AGE(order_month, cohort_month)` trả về interval, `EXTRACT(MONTH FROM ...)` cho số tháng chênh lệch. `FILTER (WHERE gap=N)` là cú pháp Postgres pivot gọn hơn `CASE WHEN`. Quan sát ma trận theo chiều dọc để thấy pattern: nếu cohort T3 có m1_ret cao hơn T2 → chiến dịch khách mới tháng 3 chất lượng hơn. Nhớ: không có m2 cho cohort T4 vì dataset dừng ở T4 — đây là **right-censoring**, phải chú thích rõ trên báo cáo."

### ⚠️ Common mistakes
- Tính cohort sai: dùng `signup_date` (có trong dim_customer) vs first order — khác nhau. RFM thường dùng first-order cohort.
- Quên `DISTINCT customer_id` → mỗi khách có nhiều đơn → đếm trùng.

### 🚀 Extension
Monthly revenue cohort (tiền thay vì số khách) — cho thấy LTV tiến hoá thế nào.

---

## B5 — Khoảng cách trung bình giữa 2 đơn liên tiếp

**Level:** L2 | **Skill:** `LAG`, date diff | **Est:** 15 phút

### 🎯 Business context
Đo "tần suất mua" trung bình → set re-engagement cadence. Khách hay mua mỗi 14 ngày, ngày 20 chưa mua → bật push.

### 💡 SQL
```sql
WITH lagged AS (
  SELECT
    customer_id,
    created_at,
    LAG(created_at) OVER (PARTITION BY customer_id ORDER BY created_at) AS prev_order
  FROM shopee.fact_orders
  WHERE payment_status='paid'
)
SELECT
  customer_id,
  ROUND(AVG(EXTRACT(EPOCH FROM (created_at - prev_order))/86400)::numeric, 1) AS avg_gap_days,
  COUNT(*)-1 AS n_gaps
FROM lagged
WHERE prev_order IS NOT NULL
GROUP BY customer_id
HAVING COUNT(*)-1 >= 2
ORDER BY avg_gap_days;
```

### 🗣️ Cách giải thích
> "`LAG(created_at) OVER (PARTITION BY customer_id ORDER BY created_at)` — với mỗi khách, lấy timestamp đơn trước của chính khách đó. `PARTITION BY` phân nhóm, `ORDER BY` quyết định 'trước' là gì. `EXTRACT(EPOCH FROM interval)` chuyển interval thành số giây, chia 86400 ra ngày — mẫu chuyển đổi phổ biến."

### ⚠️ Common mistakes
- Thiếu `PARTITION BY` → lag nhảy sang customer khác, sai hoàn toàn.
- Tính trên khách chỉ có 1 đơn → `prev_order` luôn NULL → phải filter.

### 🚀 Extension
So avg gap theo tier (bronze/silver/gold/platinum) — VIP có mua thường xuyên hơn?

---

## B6 — % khách chỉ mua đúng 1 lần (one-time buyer)

**Level:** L2 | **Skill:** `HAVING COUNT=1`, nested aggregate | **Est:** 15 phút

### 🎯 Business context
One-time buyer ratio là thước đo hiệu quả retention. Nếu >70% khách chỉ mua 1 lần → sàn phải review onboarding.

### 💡 SQL
```sql
WITH per_customer AS (
  SELECT customer_id, COUNT(*) AS orders
  FROM shopee.fact_orders
  WHERE payment_status='paid'
  GROUP BY customer_id
)
SELECT
  COUNT(*) FILTER (WHERE orders=1) AS one_time,
  COUNT(*)                          AS total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE orders=1) / COUNT(*), 2) AS one_time_pct
FROM per_customer;
```

### 🗣️ Cách giải thích
> "2 bước: (1) đếm đơn mỗi khách trong CTE, (2) đếm khách có đúng 1 đơn chia tổng. `FILTER (WHERE ...)` là cú pháp Postgres gọn cho aggregate có điều kiện, thay thế cho `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`."

### 🚀 Extension
Breakdown one-time pct theo cohort month và theo kênh đăng ký.

---

## B7 — **CASE: Churn analysis — khách nào 60 ngày chưa quay lại?**

**Level:** L4 | **Skill:** anti-pattern, multi-join, segmentation | **Est:** 45 phút

### 🎯 Business context
Win-back campaign muốn biết: ai lapsed (60+ ngày không mua), họ thường mua ngành gì (để recommend voucher chuẩn).

### 🧭 Approach
1. Tìm khách có `MAX(created_at) < 2024-04-30 - 60 days`.
2. Với mỗi khách, lấy top cat1 họ từng mua nhiều nhất → làm voucher hint.
3. Join dim_customer lấy tier + city.

### 💡 SQL
```sql
WITH last_seen AS (
  SELECT customer_id, MAX(created_at)::date AS last_dt
  FROM shopee.fact_orders
  WHERE payment_status='paid'
  GROUP BY customer_id
),
lapsed AS (
  SELECT customer_id, last_dt
  FROM last_seen
  WHERE last_dt < DATE '2024-04-30' - 60
),
top_cat AS (
  SELECT DISTINCT ON (o.customer_id)
    o.customer_id,
    p.cat1_name AS top_cat1,
    SUM(i.line_total) AS spent_in_cat
  FROM shopee.fact_orders o
  JOIN shopee.fact_order_items i ON i.order_id = o.order_id
  JOIN shopee.dim_product p ON p.product_id = i.product_id
  WHERE o.payment_status='paid'
  GROUP BY o.customer_id, p.cat1_name
  ORDER BY o.customer_id, SUM(i.line_total) DESC
)
SELECT
  l.customer_id, c.customer_name, c.tier, c.city,
  l.last_dt,
  (DATE '2024-04-30' - l.last_dt) AS days_since,
  t.top_cat1
FROM lapsed l
JOIN shopee.dim_customer c ON c.customer_id = l.customer_id
LEFT JOIN top_cat t        ON t.customer_id = l.customer_id
ORDER BY days_since DESC
LIMIT 500;
```

### 🗣️ Cách giải thích
> "`DISTINCT ON (customer_id)` + `ORDER BY customer_id, SUM(...) DESC` là cú pháp Postgres gọn để lấy 'top N per group' — ở đây N=1. Alternative dùng `ROW_NUMBER() PARTITION BY` cũng được nhưng dài hơn. Đây là query thực chiến: output có thể export CSV gửi email marketing kèm voucher cat1 cho từng khách → personalized win-back."

### ⚠️ Common mistakes
- `DISTINCT ON` phải có `ORDER BY` khớp prefix — dễ sai.
- Không filter `payment_status` làm lapsed tính sai (khách đặt rồi huỷ vẫn tính là active).
- Lấy `CURRENT_DATE` thay vì fix `2024-04-30` → số ngày lệch.

### 🚀 Extension
Ghép vào logic voucher: tier × top_cat1 → discount value phù hợp. Build file CSV export.

---

## B8 — LTV 90 ngày trung bình của cohort tháng đầu

**Level:** L3 | **Skill:** cohort + aggregation | **Est:** 25 phút

### 🎯 Business context
LTV90 = tổng chi tiêu của khách mới trong 90 ngày kể từ đơn đầu. Benchmark CAC: nếu LTV90 > 2×CAC → acquisition channel lãi.

### 💡 SQL
```sql
WITH first_order AS (
  SELECT customer_id, MIN(created_at)::date AS first_dt
  FROM shopee.fact_orders
  WHERE payment_status='paid'
  GROUP BY customer_id
),
feb_cohort AS (
  SELECT customer_id, first_dt
  FROM first_order
  WHERE first_dt BETWEEN DATE '2024-02-01' AND DATE '2024-02-29'
),
spending AS (
  SELECT f.customer_id, SUM(o.total_amount) AS spend_90d
  FROM feb_cohort f
  JOIN shopee.fact_orders o ON o.customer_id = f.customer_id
  WHERE o.payment_status='paid'
    AND o.created_at::date BETWEEN f.first_dt AND f.first_dt + 89
  GROUP BY f.customer_id
)
SELECT
  COUNT(*)                            AS cohort_size,
  ROUND(AVG(spend_90d), 0)           AS avg_ltv_90d,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY spend_90d), 0) AS median_ltv
FROM spending;
```

### 🗣️ Cách giải thích
> "Dùng `first_dt + 89` (offset 89 ngày) vì khoảng 90 ngày gồm ngày đầu + 89 ngày sau. Median là thước đo robust hơn mean (có vài VIP spending cao kéo mean lên). Business luôn nhìn cả 2 để hiểu phân phối."

### 🚀 Extension
So LTV90 cohort T2 vs T3, có cải thiện không? Phân rã LTV90 theo acquisition channel (join fact_traffic_session).

---

## B9 — Khách mua trên ≥2 device_type khác nhau (multi-device)

**Level:** L2 | **Skill:** `HAVING COUNT(DISTINCT)` | **Est:** 10 phút

### 🎯 Business context
Multi-device user thường là power user, giá trị cao. Biết % của họ giúp decide investment vào cross-device tracking.

### 💡 SQL
```sql
SELECT
  customer_id,
  COUNT(DISTINCT device_type) AS device_cnt,
  STRING_AGG(DISTINCT device_type, ', ' ORDER BY device_type) AS devices,
  SUM(total_amount) AS total_spent
FROM shopee.fact_orders
WHERE payment_status='paid'
GROUP BY customer_id
HAVING COUNT(DISTINCT device_type) >= 2
ORDER BY total_spent DESC
LIMIT 50;
```

### 🗣️ Cách giải thích
> "`HAVING` lọc sau `GROUP BY`, khác `WHERE` lọc trước. `STRING_AGG(DISTINCT ...)` nối các giá trị unique thành string có sắp xếp — tiện cho báo cáo. So spending trung bình nhóm multi-device vs single-device để thấy chênh lệch."

### 🚀 Extension
Tính tỷ lệ multi-device khách có ≥3 đơn (loại out khách 1 đơn bị noise).
