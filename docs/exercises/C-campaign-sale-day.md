# Chủ đề C — Campaign / Sale Day effectiveness

Đây là chủ đề cốt lõi của Shopee: 3/3, 4/4, 5/5 Mega Sale. Dạy học viên đánh giá ROI campaign và so sánh giữa các sale day.

---

## C1 — GMV các ngày sale (3/3, 4/4, 5/5) vs ngày thường cùng tuần

**Level:** L2 | **Skill:** JOIN `is_sale_day`, conditional aggregation | **Est:** 15 phút

### 🎯 Business context
So sale day với baseline ngày thường cùng tuần → thấy được **uplift** của campaign (loại bỏ seasonality).

### 🧭 Approach
1. Lấy các ngày có `is_sale_day = TRUE` trong dim_date.
2. Với mỗi sale day, so GMV với trung bình 6 ngày còn lại cùng tuần.

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date AS dt, d.is_sale_day, d.week_of_year,
         SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date, d.is_sale_day, d.week_of_year
)
SELECT
  week_of_year,
  MAX(gmv) FILTER (WHERE is_sale_day)                               AS gmv_sale_day,
  ROUND(AVG(gmv) FILTER (WHERE NOT is_sale_day), 0)                 AS avg_gmv_normal,
  ROUND(
    MAX(gmv) FILTER (WHERE is_sale_day)
    / NULLIF(AVG(gmv) FILTER (WHERE NOT is_sale_day),0)
  , 2)                                                              AS uplift_ratio
FROM daily
GROUP BY week_of_year
HAVING BOOL_OR(is_sale_day)
ORDER BY week_of_year;
```

### ✅ Expected result
| week_of_year | gmv_sale_day | avg_gmv_normal | uplift_ratio |
|---|---|---|---|
| 10 (có 3/3) | 820M | 280M | 2.93× |
| 14 (có 4/4) | 650M | 310M | 2.10× |
| 18 (có 5/5) | 580M | 325M | 1.78× |

### 🗣️ Cách giải thích
> "Đừng chỉ so 'sale day vs trung bình cả tháng' — bias lớn vì tuần có Tết hoặc mùa mưa sẽ lệch. Luôn chọn baseline **gần nhất về thời gian**: cùng tuần hoặc ±7 ngày. `FILTER` cho phép aggregate có điều kiện — gọn hơn nhiều so với subquery."

### ⚠️ Common mistakes
- Baseline sai: so với trung bình 90 ngày thay vì tuần đó.
- Quên filter `paid` → GMV phồng.

### 🚀 Extension
Thêm breakdown uplift theo cat1 — sale day nào đẩy được ngành hàng gì nhất.

---

## C2 — Campaign nào ROI cao nhất

**Level:** L3 | **Skill:** Multi-fact join, ratio | **Est:** 30 phút

### 🎯 Business context
ROAS (Return On Ad Spend) = GMV attributed / spend. Đây là KPI quyết định nên rót budget vào campaign nào.

### 💡 SQL
```sql
WITH spend AS (
  SELECT campaign_id, SUM(spend_amount) AS total_spend
  FROM shopee.fact_ad_spend
  GROUP BY campaign_id
),
gmv AS (
  SELECT campaign_id, SUM(total_amount) AS gmv
  FROM shopee.fact_orders
  WHERE payment_status='paid' AND campaign_id IS NOT NULL
  GROUP BY campaign_id
)
SELECT
  c.campaign_name, c.campaign_type,
  s.total_spend, g.gmv,
  ROUND(g.gmv / NULLIF(s.total_spend,0), 2) AS roas
FROM shopee.dim_campaign c
LEFT JOIN spend s ON s.campaign_id = c.campaign_id
LEFT JOIN gmv   g ON g.campaign_id = c.campaign_id
WHERE s.total_spend IS NOT NULL
ORDER BY roas DESC;
```

### 🗣️ Cách giải thích
> "Dùng 2 CTE riêng rồi join vào dim_campaign — mỗi CTE làm 1 việc, dễ debug. `LEFT JOIN` phòng trường hợp campaign không có spend hoặc không có GMV. `NULLIF` tránh divide-by-zero."

### ⚠️ Common mistakes
- JOIN spend trực tiếp với fact_orders qua campaign_id và quên dùng subquery → nhân đôi row gây tổng spend sai (fan-out).
- Không filter `paid` → GMV có cả đơn huỷ.
- Quy GMV top-line vào campaign attribution — đáng lẽ chỉ attribution 1 phần.

### 🚀 Extension
Tính `incremental GMV` = GMV campaign - baseline GMV (estimate lift thực).

---

## C3 — **CASE: Sale day nào trong tháng tốt nhất?** (3/3 vs 4/4 vs 5/5)

**Level:** L4 | **Skill:** multi-dim comparison, pivot | **Est:** 60 phút

### 🎯 Business context
Đây là câu bạn nhắc đích danh. Category team + marketing cần biết sale day nào "work best" để decide budget + category focus cho 6/6, 7/7...

So sánh 6 chiều: #orders, GMV, AOV, unique buyers, new buyer %, voucher used.

### 💡 SQL
```sql
WITH sale_day_stats AS (
  SELECT
    d.full_date                               AS sale_date,
    EXTRACT(MONTH FROM d.full_date)::int      AS mth,
    COUNT(*)                                  AS orders,
    SUM(o.total_amount)                       AS gmv,
    AVG(o.total_amount)::bigint               AS aov,
    COUNT(DISTINCT o.customer_id)             AS unique_buyers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE o.is_first_order)
                / COUNT(*), 2)                AS new_buyer_pct,
    SUM(o.platform_voucher + o.shop_discount) AS total_voucher_value,
    ROUND(100.0 * COUNT(*) FILTER (WHERE o.platform_voucher > 0)
                / COUNT(*), 2)                AS pct_with_voucher
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
    AND d.is_sale_day
    AND EXTRACT(DAY FROM d.full_date) = EXTRACT(MONTH FROM d.full_date)  -- đúng ngày 3/3, 4/4, 5/5
  GROUP BY d.full_date
)
SELECT * FROM sale_day_stats ORDER BY sale_date;
```

### ✅ Expected result
| sale_date | mth | orders | gmv | aov | unique_buyers | new_buyer_pct | total_voucher_value | pct_with_voucher |
|---|---|---|---|---|---|---|---|---|
| 2024-03-03 | 3 | 18,400 | 820M | 44,565 | 15,200 | 22.3 | 120M | 68.0 |
| 2024-04-04 | 4 | 14,200 | 650M | 45,775 | 12,100 | 18.5 | 95M | 62.3 |
| 2024-05-05 | 5 | 12,800 | 580M | 45,312 | 10,800 | 16.8 | 88M | 60.5 |

### 🗣️ Cách giải thích
> "Câu 'cái nào tốt nhất' luôn mơ hồ — phải define metric. Ở đây mình trả lại 6 metric, để PM tự diễn giải theo mục tiêu: nếu mục tiêu 'GMV' → 3/3 thắng; nếu 'acquisition' → 3/3 có new buyer % cao nhất; nếu 'efficient' → 5/5 có AOV cao mà ít discount.
>
> Insight có thể rút: Mega Sale đang **decay** — 3/3 là cao nhất, đi xuống dần đến 5/5. Giả thuyết: (1) ngân sách chia bớt cho campaign category sale giữa tháng, (2) khách bắt đầu 'nhàm' với format Mega Sale, (3) seasonality tiêu dùng giảm sau Tết. Next step: compare sale day cùng tháng năm ngoái nếu có data."

### ⚠️ Common mistakes
- Lẫn "sale day" với cả ngày khác trong campaign period — phải filter chính xác ngày đôi (3/3, 4/4, ...).
- So GMV tuyệt đối mà không tính vs baseline — tháng 3 GMV tổng vốn đã cao hơn tháng 4.

### 🚀 Extension
Thêm so sánh với non-sale Sunday gần nhất để tính uplift %. Cũng add top 5 cat1 theo sale day để thấy ngành nào đẩy mạnh.

---

## C4 — Campaign MoM growth (4/4 vs 3/3)

**Level:** L3 | **Skill:** pivot với LAG | **Est:** 25 phút

### 🎯 Business context
MoM growth giữa các sale day cùng format. Nếu growth âm → dấu hiệu khó, phải đổi chiến lược.

### 💡 SQL
```sql
WITH per_sale AS (
  SELECT
    c.campaign_name, c.campaign_type,
    DATE_TRUNC('month', d.full_date)::date AS mth,
    SUM(o.total_amount) AS gmv,
    COUNT(*)            AS orders
  FROM shopee.fact_orders o
  JOIN shopee.dim_date     d ON d.date_key = o.order_date_key
  JOIN shopee.dim_campaign c ON c.campaign_id = o.campaign_id
  WHERE o.payment_status='paid' AND d.is_sale_day
    AND c.campaign_type = 'mega_sale'
  GROUP BY c.campaign_name, c.campaign_type, DATE_TRUNC('month', d.full_date)
)
SELECT
  campaign_name, mth, gmv,
  LAG(gmv) OVER (PARTITION BY campaign_type ORDER BY mth) AS prev_gmv,
  ROUND(100.0 * (gmv - LAG(gmv) OVER (PARTITION BY campaign_type ORDER BY mth))
              / NULLIF(LAG(gmv) OVER (PARTITION BY campaign_type ORDER BY mth),0), 2) AS mom_pct
FROM per_sale
ORDER BY mth;
```

### 🗣️ Cách giải thích
> "`PARTITION BY campaign_type` để LAG chỉ so trong cùng loại campaign. Nếu dùng LAG không partition, nó có thể nhảy sang campaign khác loại → so sánh không hợp lý."

### 🚀 Extension
Breakdown MoM theo cat1 — ngành nào bị suy giảm nhanh nhất qua các lần sale.

---

## C5 — Tỷ lệ khách mới trong campaign day vs bình thường

**Level:** L2 | **Skill:** segment filter + ratio | **Est:** 15 phút

### 🎯 Business context
Mega sale có nhiệm vụ kéo khách mới. Nếu new-buyer % không cao hơn bình thường → campaign chỉ đang chuyển khách cũ sang thời điểm khác, không tạo acquisition.

### 💡 SQL
```sql
SELECT
  d.is_sale_day,
  COUNT(*)                                      AS orders,
  COUNT(*) FILTER (WHERE o.is_first_order)      AS new_orders,
  ROUND(100.0 * COUNT(*) FILTER (WHERE o.is_first_order)
              / COUNT(*), 2)                    AS new_pct
FROM shopee.fact_orders o
JOIN shopee.dim_date d ON d.date_key = o.order_date_key
WHERE o.payment_status='paid'
GROUP BY d.is_sale_day;
```

### 🗣️ Cách giải thích
> "2 dòng output — sale day vs non-sale day. Nếu new_pct chênh nhau không nhiều (vd 22% vs 20%) → campaign không tạo acquisition. Nếu chênh lớn (22% vs 12%) → campaign thành công kéo khách mới."

### 🚀 Extension
Breakdown thêm theo campaign_id để thấy campaign nào thực sự acquisition-focused.

---

## C6 — Pre-sale warm-up: 3 ngày trước sale day có tăng?

**Level:** L3 | **Skill:** date offset, rolling compare | **Est:** 30 phút

### 🎯 Business context
Mega Sale thường teaser bằng voucher nhỏ 1–3 ngày trước. Biết được warm-up có effect không giúp plan budget teaser.

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date AS dt, d.is_sale_day,
         SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date, d.is_sale_day
),
marked AS (
  SELECT a.*,
    MIN(CASE WHEN b.is_sale_day AND b.dt > a.dt AND b.dt <= a.dt + 3 THEN b.dt END) AS next_sale
  FROM daily a
  LEFT JOIN daily b ON b.dt BETWEEN a.dt+1 AND a.dt+3
  GROUP BY a.dt, a.is_sale_day, a.gmv
)
SELECT
  CASE
    WHEN is_sale_day THEN 'D-day'
    WHEN next_sale IS NOT NULL THEN 'Warm-up (D-3 to D-1)'
    ELSE 'Other'
  END AS day_type,
  COUNT(*)             AS n_days,
  ROUND(AVG(gmv),0)    AS avg_gmv
FROM marked
GROUP BY 1
ORDER BY 1;
```

### 🗣️ Cách giải thích
> "Bài đòi hỏi nhận biết 'ngày nào là ngày teaser'. Kỹ thuật: cho mỗi ngày, tìm sale day gần nhất trong khoảng D+1 đến D+3 → nếu có, đó là ngày warm-up. Self-join trên cùng CTE `daily` là pattern thường gặp."

### 🚀 Extension
Tách warm-up thành D-3, D-2, D-1 riêng biệt để thấy curve teaser.

---

## C7 — Hậu sale: 7 ngày sau sale day có dip?

**Level:** L3 | **Skill:** rolling window around event | **Est:** 25 phút

### 🎯 Business context
Câu hỏi marketing: sale day có "ăn trộm" GMV của các ngày sau không? Nếu dip lớn → tổng GMV theo tháng không tăng thật.

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date AS dt, d.is_sale_day,
         SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date, d.is_sale_day
),
sale_days AS (
  SELECT dt FROM daily WHERE is_sale_day
),
labeled AS (
  SELECT a.dt, a.gmv,
    MIN(a.dt - s.dt) FILTER (WHERE a.dt >= s.dt AND a.dt < s.dt + 8) AS days_after_sale
  FROM daily a
  LEFT JOIN sale_days s ON a.dt BETWEEN s.dt AND s.dt+7
  GROUP BY a.dt, a.gmv
)
SELECT days_after_sale, ROUND(AVG(gmv),0) AS avg_gmv, COUNT(*) n_days
FROM labeled
WHERE days_after_sale IS NOT NULL
GROUP BY days_after_sale
ORDER BY days_after_sale;
```

### 🗣️ Cách giải thích
> "Đo `days_after_sale` ∈ [0,7]. Day 0 là chính ngày sale (spike). Kỳ vọng: day 1 dip sâu (khách đã mua hôm qua), day 2–3 dần phục hồi, day 4+ quay lại baseline. Nếu GMV cộng dồn day 1–7 thấp hơn baseline 7 ngày → sale đang cannibalize."

### 🚀 Extension
So tổng GMV [D-3, D+7] với 11 ngày baseline thông thường để tính incremental lift.

---

## C8 — Campaign attribution: mỗi đơn trong sale day thuộc campaign nào

**Level:** L1 | **Skill:** JOIN dim_campaign | **Est:** 8 phút

### 💡 SQL
```sql
SELECT
  c.campaign_name,
  COUNT(*)                AS orders,
  SUM(o.total_amount)     AS gmv
FROM shopee.fact_orders o
JOIN shopee.dim_date     d ON d.date_key = o.order_date_key
LEFT JOIN shopee.dim_campaign c ON c.campaign_id = o.campaign_id
WHERE o.payment_status='paid' AND d.is_sale_day
GROUP BY c.campaign_name
ORDER BY gmv DESC NULLS LAST;
```

### 🗣️ Cách giải thích
> "`LEFT JOIN` vì có đơn không thuộc campaign nào (`campaign_id NULL`). `NULLS LAST` đẩy NULL xuống cuối khi sort."

### 🚀 Extension
Thêm % đơn có campaign vs không — baseline behavior.

---

## C9 — Top cat1 hưởng lợi nhất từ sale day

**Level:** L2 | **Skill:** GROUP BY cat1 + filter sale day | **Est:** 15 phút

### 💡 SQL
```sql
SELECT
  p.cat1_name,
  SUM(i.line_total) FILTER (WHERE d.is_sale_day) AS gmv_sale,
  SUM(i.line_total) FILTER (WHERE NOT d.is_sale_day) AS gmv_normal,
  ROUND(
    SUM(i.line_total) FILTER (WHERE d.is_sale_day)
    / NULLIF(SUM(i.line_total) FILTER (WHERE NOT d.is_sale_day), 0)
  , 2) AS sale_vs_normal_ratio
FROM shopee.fact_order_items i
JOIN shopee.fact_orders o ON o.order_id = i.order_id
JOIN shopee.dim_date    d ON d.date_key = o.order_date_key
JOIN shopee.dim_product p ON p.product_id = i.product_id
WHERE o.payment_status='paid'
GROUP BY p.cat1_name
ORDER BY sale_vs_normal_ratio DESC;
```

### 🗣️ Cách giải thích
> "Ratio cao = cat1 phụ thuộc sale day; ratio thấp = cat1 có demand ổn định quanh năm. Chiến lược: cat1 ratio thấp → không cần đốt nhiều vào sale, cat1 ratio cao → đầu tư mạnh."

### 🚀 Extension
Xuống cat2 để thấy chi tiết — vd trong Fashion, áo vs quần có ratio khác nhau.

---

## C10 — **CASE: Dự đoán GMV sale day 6/6** từ trend 3/3, 4/4, 5/5

**Level:** L4 | **Skill:** CAGR, projection | **Est:** 35 phút

### 🎯 Business context
Planning team muốn set target cho 6/6. Phương pháp đơn giản: tính growth rate giữa 3 sale day đã có, projection.

### 💡 SQL
```sql
WITH sale_gmv AS (
  SELECT
    EXTRACT(MONTH FROM d.full_date)::int AS mth,
    SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid' AND d.is_sale_day
    AND EXTRACT(DAY FROM d.full_date) = EXTRACT(MONTH FROM d.full_date)
  GROUP BY mth
),
growth AS (
  SELECT mth, gmv,
    LAG(gmv) OVER (ORDER BY mth) AS prev,
    ROUND( (gmv::numeric / LAG(gmv) OVER (ORDER BY mth) - 1) * 100, 2) AS mom_pct
  FROM sale_gmv
)
SELECT * FROM growth
UNION ALL
SELECT
  6 AS mth,
  (SELECT gmv FROM growth WHERE mth=5)
    * (1 + AVG(mom_pct) OVER () / 100)     AS gmv_projected,
  NULL AS prev,
  AVG(mom_pct) OVER () AS mom_pct_avg
FROM growth
WHERE mth >= 4
LIMIT 1;
```

### 🗣️ Cách giải thích
> "Đây là projection đơn giản. Giả định: growth rate tháng tới = trung bình growth 2 tháng trước. Đừng tin tuyệt đối — chỉ là **base case** để team biz challenge. Analyst luôn kèm caveat: 'giả sử xu hướng tiếp diễn, chưa tính yếu tố mùa vụ tháng 6, chưa tính budget thay đổi.'"

### ⚠️ Common mistakes
- Không kèm caveat → PM dùng số thô rồi commit sai.
- Dùng CAGR kiểu geometric mean sẽ tốt hơn khi có ≥3 điểm, arithmetic mean thích hợp khi 2 điểm.

### 🚀 Extension
Cho 3 kịch bản: pessimistic (min growth), base case (avg), optimistic (max growth) — thói quen chuyên nghiệp.
