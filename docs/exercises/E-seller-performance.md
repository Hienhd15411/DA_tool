# Chủ đề E — Seller / Shop performance

Shopee là marketplace: seller sức khoẻ quyết định GMV bền vững. Dạy học viên đo và phát hiện seller rủi ro.

---

## E1 — Top 20 seller theo GMV

**Level:** L1 | **Skill:** GROUP BY | **Est:** 5 phút

### 💡 SQL
```sql
SELECT
  s.seller_id, s.shop_name, s.shop_type,
  COUNT(*)            AS orders,
  SUM(o.total_amount) AS gmv,
  ROUND(AVG(o.total_amount),0) AS aov
FROM shopee.fact_orders o
JOIN shopee.dim_seller s ON s.seller_id = o.seller_id
WHERE o.payment_status='paid'
GROUP BY s.seller_id, s.shop_name, s.shop_type
ORDER BY gmv DESC
LIMIT 20;
```

### 🗣️ Cách giải thích
> "Bài cơ bản, nhưng thực tế: nếu không có index trên `seller_id`, query trên 350k đơn hàng sẽ chậm. Luôn EXPLAIN trước khi chạy trên production."

### 🚀 Extension
Thêm share of GMV (% của seller này trên tổng) dùng window `SUM OVER ()`.

---

## E2 — **Pareto**: bao nhiêu % seller chiếm 80% GMV?

**Level:** L3 | **Skill:** cumulative window `SUM OVER (...)` | **Est:** 30 phút

### 🎯 Business context
Pareto 80/20 kinh điển. Biết concentration giúp:
- Nếu 5% seller cầm 80% → rủi ro khi seller lớn rời sàn.
- Nếu 40% seller cầm 80% → long-tail khoẻ, ổn định.

### 💡 SQL
```sql
WITH seller_gmv AS (
  SELECT seller_id, SUM(total_amount) AS gmv
  FROM shopee.fact_orders
  WHERE payment_status='paid'
  GROUP BY seller_id
),
ranked AS (
  SELECT seller_id, gmv,
    SUM(gmv) OVER (ORDER BY gmv DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cum_gmv,
    SUM(gmv) OVER ()                                                                   AS total_gmv,
    ROW_NUMBER() OVER (ORDER BY gmv DESC)                                              AS rn,
    COUNT(*) OVER ()                                                                   AS total_sellers
  FROM seller_gmv
)
SELECT
  rn                                            AS seller_rank,
  ROUND(100.0 * rn::numeric / total_sellers, 2) AS pct_sellers,
  gmv, cum_gmv,
  ROUND(100.0 * cum_gmv::numeric / total_gmv, 2) AS pct_cum_gmv
FROM ranked
WHERE 100.0 * cum_gmv::numeric / total_gmv <= 80.5   -- dừng ngay sau mốc 80%
ORDER BY rn;
```

### ✅ Expected insight
> "Top 180 seller (3.6% của 5000 seller) chiếm 80% GMV. Concentration cao — cần chính sách giữ chân top seller."

### 🗣️ Cách giải thích
> "3 window trên cùng 1 dòng: (1) `SUM OVER (ORDER BY ... ROWS BETWEEN UNBOUNDED PRECEDING)` = cumulative sum, (2) `SUM OVER ()` = grand total (không partition, không order), (3) `ROW_NUMBER` = thứ tự. Đây là pattern 'running total' kinh điển."

### ⚠️ Common mistakes
- Thiếu `ORDER BY gmv DESC` trong cumulative — running total vô nghĩa.
- Filter `<= 80` cứng có thể miss dòng ngay tại mốc — dùng 80.5 cho an toàn.

### 🚀 Extension
Vẽ Pareto curve (scatter pct_sellers vs pct_cum_gmv) để slide thuyết trình.

---

## E3 — Seller có cancel rate > 20% (red flag)

**Level:** L2 | **Skill:** `AVG(CASE)` ratio, HAVING | **Est:** 15 phút

### 💡 SQL
```sql
SELECT
  s.seller_id, s.shop_name,
  COUNT(*)                                                         AS orders,
  COUNT(*) FILTER (WHERE o.order_status='cancelled')                AS cancelled,
  ROUND(100.0 * COUNT(*) FILTER (WHERE o.order_status='cancelled')
              / COUNT(*), 2)                                        AS cancel_rate_pct
FROM shopee.fact_orders o
JOIN shopee.dim_seller s ON s.seller_id = o.seller_id
GROUP BY s.seller_id, s.shop_name
HAVING COUNT(*) >= 20                                     -- tránh seller ít đơn gây noise
   AND COUNT(*) FILTER (WHERE o.order_status='cancelled') * 5 > COUNT(*)  -- >20%
ORDER BY cancel_rate_pct DESC;
```

### 🗣️ Cách giải thích
> "Luôn có `HAVING COUNT(*) >= N` để loại seller ít đơn — 1 seller có 2 đơn cancel 1 đơn là cancel rate 50%, gây nhiễu report. Ngưỡng N tuỳ business (thường 20–50)."

### ⚠️ Common mistakes
- Quên min orders filter → list dài toàn seller nhỏ xíu.
- Filter `payment_status` ở đây không đúng: đơn cancel thường không paid, nếu filter sẽ loại hết đơn cần đếm.

### 🚀 Extension
So cancel rate theo cat1 của seller — ngành nào vốn cancel cao (vd điện tử thường cao hơn fashion).

---

## E4 — Seller có số SKU active cao nhất

**Level:** L2 | **Skill:** JOIN dim_product, COUNT | **Est:** 10 phút

### 💡 SQL
```sql
SELECT
  s.seller_id, s.shop_name,
  COUNT(DISTINCT p.product_id) FILTER (WHERE p.is_active) AS active_skus,
  COUNT(DISTINCT p.cat1_id)                                AS cat1_count
FROM shopee.dim_seller s
LEFT JOIN shopee.dim_product p ON p.seller_id = s.seller_id
GROUP BY s.seller_id, s.shop_name
ORDER BY active_skus DESC
LIMIT 20;
```

### 🚀 Extension
Tính SKU active nhưng không có đơn nào 3 tháng → "dead SKU".

---

## E5 — Seller mới (launch ≤ 3 tháng) hoạt động tốt không?

**Level:** L3 | **Skill:** date filter + rank | **Est:** 20 phút

### 🎯 Business context
Measure onboarding success: seller mới có đơn trong N ngày đầu không? Quartile đầu tăng trưởng ra sao?

### 💡 SQL
```sql
WITH new_sellers AS (
  SELECT seller_id, shop_name,
    (SELECT full_date FROM shopee.dim_date WHERE date_key = join_date_key) AS join_dt
  FROM shopee.dim_seller
  WHERE join_date_key >= 20240201
),
activity AS (
  SELECT ns.seller_id, ns.shop_name, ns.join_dt,
    COUNT(o.order_id)                AS orders_in_first_30d,
    SUM(o.total_amount)              AS gmv_first_30d
  FROM new_sellers ns
  LEFT JOIN shopee.fact_orders o
    ON o.seller_id = ns.seller_id
   AND o.created_at::date BETWEEN ns.join_dt AND ns.join_dt + 29
   AND o.payment_status='paid'
  GROUP BY ns.seller_id, ns.shop_name, ns.join_dt
)
SELECT *,
  NTILE(4) OVER (ORDER BY gmv_first_30d DESC) AS quartile
FROM activity
ORDER BY gmv_first_30d DESC;
```

### 🗣️ Cách giải thích
> "`NTILE(4)` chia thành 4 quartile bằng nhau — seller top quartile có GMV 30 ngày đầu cao nhất. Có thể profile họ (cat1 nào, join từ kênh nào) để replicate thành công."

### 🚀 Extension
So quartile 1 và 4: seller quartile 4 có 90% rời sàn trước 60 ngày?

---

## E6 — **CASE: Seller risk audit** — seller vừa cancel cao, vừa ship trễ, vừa nhiều CS ticket

**Level:** L4 | **Skill:** multi-fact join | **Est:** 50 phút

### 🎯 Business context
Trust & Safety team cần list seller risk cao để review. 1 indicator có thể noise, 3 indicator cùng cao thì gần chắc chắn có vấn đề.

### 💡 SQL
```sql
WITH cancel AS (
  SELECT seller_id,
    COUNT(*) AS orders,
    ROUND(100.0 * COUNT(*) FILTER (WHERE order_status='cancelled') / COUNT(*), 2) AS cancel_pct
  FROM shopee.fact_orders
  GROUP BY seller_id
  HAVING COUNT(*) >= 20
),
ship_sla AS (
  SELECT o.seller_id,
    COUNT(*) AS shipments,
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT sh.is_on_time) / COUNT(*), 2) AS late_pct
  FROM shopee.fact_shipment sh
  JOIN shopee.fact_orders o ON o.order_id = sh.order_id
  GROUP BY o.seller_id
  HAVING COUNT(*) >= 20
),
tickets AS (
  SELECT seller_id,
    COUNT(*) AS ticket_cnt
  FROM shopee.fact_customer_service_ticket
  WHERE seller_id IS NOT NULL
  GROUP BY seller_id
),
scored AS (
  SELECT
    s.seller_id, s.shop_name,
    c.cancel_pct, sh.late_pct, COALESCE(t.ticket_cnt,0) AS tickets,
    c.orders,
    NTILE(10) OVER (ORDER BY c.cancel_pct DESC NULLS LAST)      AS cancel_decile,
    NTILE(10) OVER (ORDER BY sh.late_pct DESC NULLS LAST)       AS ship_decile,
    NTILE(10) OVER (ORDER BY COALESCE(t.ticket_cnt,0)::numeric/NULLIF(c.orders,0) DESC NULLS LAST) AS ticket_decile
  FROM shopee.dim_seller s
  LEFT JOIN cancel   c  ON c.seller_id  = s.seller_id
  LEFT JOIN ship_sla sh ON sh.seller_id = s.seller_id
  LEFT JOIN tickets  t  ON t.seller_id  = s.seller_id
  WHERE c.orders IS NOT NULL
)
SELECT * FROM scored
WHERE cancel_decile = 1 AND ship_decile = 1 AND ticket_decile = 1
ORDER BY cancel_pct DESC;
```

### 🗣️ Cách giải thích
> "Mỗi chỉ số chia làm 10 decile (`NTILE(10) ORDER BY ... DESC`) — decile 1 = tệ nhất. Seller rơi vào decile 1 của cả 3 chỉ số cùng lúc = flag đỏ. Pattern này gọi là **composite risk scoring** — rất hay dùng trong fraud / risk analytics. Trả về list seller cụ thể để T&S team review manual."

### ⚠️ Common mistakes
- Dùng `INNER JOIN` ở đầu CTE → loại seller không có ticket → bỏ sót seller nguy hiểm hơn. Phải `LEFT JOIN` để hold đủ.
- Normalize tickets theo số đơn (`tickets/orders`) mới fair — seller nhiều đơn đương nhiên có nhiều ticket hơn.

### 🚀 Extension
Tính composite score = tổng trọng số 3 decile, sort descending → top 50 seller cần audit.

---

## E7 — Seller category concentration

**Level:** L3 | **Skill:** `COUNT DISTINCT`, Herfindahl index | **Est:** 30 phút

### 🎯 Business context
Seller chỉ bán 1 cat1 (đồng nhất) vs seller đa dạng. Đa dạng ổn định hơn khi 1 cat giảm, nhưng khó master.

### 💡 SQL
```sql
WITH seller_cat AS (
  SELECT
    p.seller_id,
    p.cat1_name,
    SUM(i.line_total) AS gmv_cat
  FROM shopee.fact_order_items i
  JOIN shopee.fact_orders o ON o.order_id = i.order_id
  JOIN shopee.dim_product p ON p.product_id = i.product_id
  WHERE o.payment_status='paid'
  GROUP BY p.seller_id, p.cat1_name
),
seller_total AS (
  SELECT seller_id, SUM(gmv_cat) AS gmv_total, COUNT(*) AS cat_count
  FROM seller_cat
  GROUP BY seller_id
)
SELECT
  s.seller_id, s.shop_name,
  st.cat_count,
  st.gmv_total,
  -- Herfindahl index: sum(share^2). 1 = độc quyền 1 cat, 1/N = phân bổ đều
  ROUND(SUM( (sc.gmv_cat::numeric / st.gmv_total)^2 ), 3) AS hhi
FROM seller_cat sc
JOIN seller_total st ON st.seller_id = sc.seller_id
JOIN shopee.dim_seller s ON s.seller_id = sc.seller_id
GROUP BY s.seller_id, s.shop_name, st.cat_count, st.gmv_total
HAVING st.gmv_total > 10000000
ORDER BY hhi DESC
LIMIT 50;
```

### 🗣️ Cách giải thích
> "Herfindahl–Hirschman Index (HHI) đo concentration. HHI = Σ(share²). HHI=1 = 100% 1 cat, HHI=1/N = phân bổ đều N cat. Index này đến từ economics, rất elegant cho bài toán 'đa dạng vs tập trung'. Post-process: segment seller thành 'specialist' (HHI > 0.7), 'balanced' (0.3–0.7), 'generalist' (< 0.3)."

### 🚀 Extension
So performance (GMV growth MoM) giữa specialist vs generalist.
