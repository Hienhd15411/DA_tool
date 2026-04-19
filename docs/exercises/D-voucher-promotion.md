# Chủ đề D — Voucher & Promotion

Voucher là công cụ 2 lưỡi: kéo đơn nhưng ăn margin. Học viên phải biết đo hiệu quả, phát hiện cannibalization.

---

## D1 — % đơn có dùng voucher (platform hoặc shop)

**Level:** L1 | **Skill:** `CASE WHEN > 0`, ratio | **Est:** 8 phút

### 🎯 Business context
Voucher penetration rate. Nếu >70% → quá phụ thuộc voucher, margin mỏng; nếu <20% → voucher strategy chưa phát huy.

### 💡 SQL
```sql
SELECT
  COUNT(*)                                                                       AS total_orders,
  COUNT(*) FILTER (WHERE platform_voucher > 0 OR shop_discount > 0)              AS with_voucher,
  ROUND(100.0 * COUNT(*) FILTER (WHERE platform_voucher > 0 OR shop_discount > 0)
              / COUNT(*), 2)                                                     AS pct_with_voucher,
  COUNT(*) FILTER (WHERE platform_voucher > 0)                                   AS with_platform,
  COUNT(*) FILTER (WHERE shop_discount > 0)                                      AS with_shop,
  COUNT(*) FILTER (WHERE shipping_discount > 0)                                  AS with_shipping
FROM shopee.fact_orders
WHERE payment_status='paid';
```

### 🗣️ Cách giải thích
> "`FILTER (WHERE)` là cách pretty nhất để đếm có điều kiện trong Postgres. 3 loại voucher: shop (seller-funded), platform (Shopee-funded), shipping (free-ship) — đếm riêng để biết Shopee đang tài trợ bao nhiêu vs seller."

### 🚀 Extension
Trend theo tuần: penetration rate có tăng theo thời gian? Dấu hiệu "addict".

---

## D2 — Voucher giảm trung bình bao nhiêu % giá trị đơn

**Level:** L2 | **Skill:** ratio aggregation | **Est:** 12 phút

### 💡 SQL
```sql
SELECT
  ROUND(AVG(
    (shop_discount + platform_voucher + shipping_discount)::numeric
     / NULLIF(subtotal, 0) * 100
  ), 2) AS avg_discount_pct,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (
    ORDER BY (shop_discount + platform_voucher + shipping_discount)::numeric
             / NULLIF(subtotal, 0) * 100
  ), 2) AS median_discount_pct
FROM shopee.fact_orders
WHERE payment_status='paid'
  AND (shop_discount + platform_voucher + shipping_discount) > 0;
```

### 🗣️ Cách giải thích
> "Lưu ý: `AVG(ratio)` (average of ratio) khác `SUM/SUM` (ratio of sum). Ở đây dùng `AVG(ratio)` cho câu hỏi 'trung bình mỗi đơn giảm %'. Nếu muốn '% tổng discount trên tổng subtotal', phải dùng `SUM(disc)/SUM(subtotal)`. Sai lầm này phổ biến và gây báo cáo lệch."

### ⚠️ Common mistakes
- Nhầm `AVG(ratio)` và `SUM/SUM` — kết quả khác nhau vài %.
- Tính cả đơn không voucher → mean kéo xuống gần 0.

### 🚀 Extension
So discount % theo cat1 — ngành nào đang giảm sâu nhất?

---

## D3 — **Voucher stacking**: đơn nào dùng cả 3 loại voucher

**Level:** L2 | **Skill:** Multi-column filter | **Est:** 15 phút

### 🎯 Business context
Stacking (chồng voucher) là lỗ hổng hay bị khai thác. Cần biết quy mô và giá trị discount bị ăn.

### 💡 SQL
```sql
SELECT
  order_id, customer_id,
  subtotal,
  shop_discount, platform_voucher, shipping_discount, coin_used,
  total_amount,
  (shop_discount + platform_voucher + shipping_discount + coin_used) AS total_discount,
  ROUND(
    (shop_discount + platform_voucher + shipping_discount + coin_used)::numeric
    / NULLIF(subtotal,0) * 100, 2
  ) AS discount_pct
FROM shopee.fact_orders
WHERE payment_status='paid'
  AND shop_discount      > 0
  AND platform_voucher   > 0
  AND shipping_discount  > 0
ORDER BY discount_pct DESC
LIMIT 50;
```

### 🗣️ Cách giải thích
> "3 điều kiện `AND > 0` lọc ra đơn có đủ cả 3 voucher. Quan sát `discount_pct` có đơn nào vượt 50% không — đó là cờ đỏ. Business rule có thể cấm stack >X% → analyst cung cấp data để rule engineer set threshold đúng."

### 🚀 Extension
Segment theo khách: khách nào hay stack nhất (nghi vô tình hay nghi abuse)?

---

## D4 — **CASE: Voucher có làm tăng AOV hay chỉ cannibalize?**

**Level:** L4 | **Skill:** segmented comparison, control | **Est:** 50 phút

### 🎯 Business context
Câu hỏi CMO đau đầu: "Voucher thật sự tăng giá trị đơn, hay khách đằng nào cũng mua rồi dùng voucher để giảm?" Phải so AOV có voucher vs không, **control theo cat1** (cat khác nhau AOV khác nhau — không control sẽ bị Simpson's paradox).

### 💡 SQL
```sql
WITH by_cat AS (
  SELECT
    p.cat1_name,
    CASE WHEN o.platform_voucher>0 OR o.shop_discount>0 THEN 'has_voucher' ELSE 'no_voucher' END AS vc,
    COUNT(DISTINCT o.order_id) AS orders,
    AVG(o.subtotal)            AS avg_subtotal,      -- giá trị giỏ TRƯỚC discount
    AVG(o.total_amount)        AS avg_total_paid
  FROM shopee.fact_orders o
  JOIN shopee.fact_order_items i ON i.order_id = o.order_id
  JOIN shopee.dim_product p       ON p.product_id = i.product_id
  WHERE o.payment_status='paid'
  GROUP BY p.cat1_name, vc
)
SELECT
  cat1_name,
  MAX(avg_subtotal) FILTER (WHERE vc='has_voucher')::bigint AS avg_subtotal_w_voucher,
  MAX(avg_subtotal) FILTER (WHERE vc='no_voucher') ::bigint AS avg_subtotal_no_voucher,
  ROUND(
    (MAX(avg_subtotal) FILTER (WHERE vc='has_voucher')
     - MAX(avg_subtotal) FILTER (WHERE vc='no_voucher'))
    / NULLIF(MAX(avg_subtotal) FILTER (WHERE vc='no_voucher'),0) * 100
  , 2) AS uplift_pct
FROM by_cat
GROUP BY cat1_name
ORDER BY uplift_pct DESC;
```

### ✅ Expected result
| cat1_name | avg_subtotal_w_voucher | avg_subtotal_no_voucher | uplift_pct |
|---|---|---|---|
| Điện Tử | 1,850,000 | 1,620,000 | 14.2 |
| Fashion Nữ | 420,000 | 380,000 | 10.5 |
| Sắc Đẹp | 290,000 | 310,000 | -6.5 *(cannibalize!)* |

### 🗣️ Cách giải thích
> "Dùng `subtotal` (giá giỏ trước discount) không phải `total_amount` — vì câu hỏi là 'voucher có kích thích khách mua thêm' chứ không phải 'voucher giảm bao nhiêu tiền'. Khi uplift âm → khách dùng voucher trên đơn vốn đã nhỏ, không tạo lift → voucher đang ăn margin không hiệu quả. Action: ngành đó nên giảm voucher hoặc đổi mechanic (min order value cao hơn).
>
> **Caveat:** đây là correlation không phải causation. Khách muốn mua nhiều có thể đi kiếm voucher. Muốn causation đúng phải A/B test."

### ⚠️ Common mistakes
- So AOV tổng (không split theo cat) → Simpson: voucher thường rơi vào cat giá cao → làm như có uplift giả.
- So `total_amount` thay vì `subtotal` → luôn thấy âm (vì voucher giảm total mà).

### 🚀 Extension
Thêm control bằng `dim_customer.tier` (VIP vs bronze) — VIP có dùng voucher hiệu quả hơn không?

---

## D5 — Voucher redemption rate theo campaign

**Level:** L3 | **Skill:** JOIN fact_voucher_usage + dim_voucher | **Est:** 25 phút

### 🎯 Business context
Voucher phát ra nhiều nhưng không ai dùng = waste. Phát ít mà dùng hết = under-supply. Redemption rate giúp calibrate.

### 💡 SQL
```sql
WITH campaign_voucher AS (
  SELECT
    c.campaign_id, c.campaign_name,
    COUNT(DISTINCT v.voucher_id) AS vouchers_issued
  FROM shopee.dim_campaign c
  JOIN shopee.dim_voucher  v ON v.campaign_id = c.campaign_id
  GROUP BY c.campaign_id, c.campaign_name
),
used AS (
  SELECT v.campaign_id, COUNT(*) AS vouchers_used, SUM(u.discount_applied) AS value_applied
  FROM shopee.fact_voucher_usage u
  JOIN shopee.dim_voucher v ON v.voucher_id = u.voucher_id
  GROUP BY v.campaign_id
)
SELECT
  cv.campaign_name,
  cv.vouchers_issued,
  COALESCE(u.vouchers_used, 0) AS vouchers_used,
  ROUND(100.0 * COALESCE(u.vouchers_used,0)/NULLIF(cv.vouchers_issued,0), 2) AS redemption_pct,
  COALESCE(u.value_applied, 0) AS total_value_applied
FROM campaign_voucher cv
LEFT JOIN used u ON u.campaign_id = cv.campaign_id
ORDER BY redemption_pct DESC;
```

### 🗣️ Cách giải thích
> "`COALESCE(x, 0)` biến NULL thành 0 khi không có usage. Lưu ý schema: `dim_voucher.voucher_id` = định nghĩa voucher template, `fact_voucher_usage` = event mỗi lần 1 khách dùng. 1 voucher có thể dùng nhiều lần (theo quota). Nếu muốn unique users, dùng `COUNT(DISTINCT customer_id)`."

### 🚀 Extension
Detect voucher "never used" → lãng phí marketing.

---

## D6 — Top 5 voucher có GMV attributed cao nhất

**Level:** L2 | **Skill:** GROUP BY | **Est:** 12 phút

### 💡 SQL
```sql
SELECT
  v.voucher_code, v.voucher_type,
  COUNT(DISTINCT u.order_id)     AS orders_with_voucher,
  SUM(u.discount_applied)        AS discount_cost,
  SUM(o.total_amount)            AS gmv_attributed,
  ROUND(SUM(o.total_amount)::numeric / NULLIF(SUM(u.discount_applied),0), 2) AS gmv_per_discount
FROM shopee.fact_voucher_usage u
JOIN shopee.dim_voucher v  ON v.voucher_id = u.voucher_id
JOIN shopee.fact_orders o  ON o.order_id   = u.order_id
WHERE o.payment_status='paid'
GROUP BY v.voucher_code, v.voucher_type
ORDER BY gmv_attributed DESC
LIMIT 5;
```

### 🗣️ Cách giải thích
> "`gmv_per_discount` = GMV attributed / discount cost. Ratio cao = voucher hiệu quả (1 đồng discount kéo nhiều GMV). Nhớ: GMV attributed ở đây là **full GMV đơn dùng voucher** — không trừ discount. Cách đo này hơi generous nhưng phổ biến ở Shopee."

### 🚀 Extension
Normalize bằng tỷ lệ incremental — cần A/B test thật.

---

## D7 — % đơn có `coin_used > 0` và coin giảm trung bình bao nhiêu

**Level:** L2 | **Skill:** aggregation | **Est:** 10 phút

### 💡 SQL
```sql
SELECT
  COUNT(*)                                              AS total_orders,
  COUNT(*) FILTER (WHERE coin_used > 0)                 AS with_coin,
  ROUND(100.0 * COUNT(*) FILTER (WHERE coin_used > 0)
              / COUNT(*), 2)                            AS pct_with_coin,
  ROUND(AVG(coin_used) FILTER (WHERE coin_used > 0), 0) AS avg_coin_used,
  ROUND(100.0 * AVG(coin_used::numeric / NULLIF(subtotal,0))
              FILTER (WHERE coin_used > 0), 2)          AS avg_coin_pct_of_subtotal
FROM shopee.fact_orders
WHERE payment_status='paid';
```

### 🗣️ Cách giải thích
> "Shopee Xu là cơ chế cashback gamified. Dữ liệu quan trọng: % penetration (khách biết tính năng không) và avg % of subtotal (khách đốt nhiều hay ít). Nếu penetration thấp → cần educate users."

### 🚀 Extension
Coin penetration theo tier khách — VIP dùng nhiều hơn bronze không?
