# Chủ đề I — Cancellation / Return

Đơn huỷ và trả hàng là chi phí ẩn. Đo được mới cải thiện được.

---

## I1 — Overall cancel rate

**Level:** L1 | **Skill:** Ratio | **Est:** 5 phút

### 💡 SQL
```sql
SELECT
  COUNT(*)                                                AS total_orders,
  COUNT(*) FILTER (WHERE order_status='cancelled')        AS cancelled,
  ROUND(100.0 * COUNT(*) FILTER (WHERE order_status='cancelled')
              / COUNT(*), 2)                              AS cancel_rate_pct
FROM shopee.fact_orders;
```

### 🗣️ Cách giải thích
> "Cancel rate là health metric. Benchmark Shopee: ~5-10% là bình thường cho marketplace e-com VN, >15% là red flag. Không filter `payment_status` ở đây vì muốn đếm TẤT CẢ đơn."

### 🚀 Extension
Trend cancel rate theo tuần → tìm inflection point.

---

## I2 — Top cancel_reason

**Level:** L1 | **Skill:** GROUP BY, NULL handling | **Est:** 8 phút

### 💡 SQL
```sql
SELECT
  COALESCE(cancel_reason, '(unknown)') AS reason,
  COUNT(*)                             AS cnt,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM shopee.fact_orders
WHERE order_status = 'cancelled'
GROUP BY cancel_reason
ORDER BY cnt DESC;
```

### 🗣️ Cách giải thích
> "`SUM(COUNT(*)) OVER ()` là 'aggregate của aggregate' — tổng sau khi đã GROUP BY, để tính %. Pattern rất hay trong reporting. `COALESCE(null, '(unknown)')` để NULL hiển thị rõ thay vì biến mất khỏi bảng (user không biết có missing data)."

### 🚀 Extension
Top reason theo cat1 — ngành nào có reason đặc thù (vd Điện Tử cancel nhiều do 'out_of_stock').

---

## I3 — Cancel rate theo payment_method (COD có cao hơn?)

**Level:** L2 | **Skill:** Segmented ratio | **Est:** 15 phút

### 🎯 Business context
COD (thu hộ) nổi tiếng là bài toán đau đầu của sàn: khách đặt xong không nhận, driver return — chi phí nặng.

### 💡 SQL
```sql
SELECT
  payment_method,
  COUNT(*)                                                AS total,
  COUNT(*) FILTER (WHERE order_status='cancelled')        AS cancelled,
  ROUND(100.0 * COUNT(*) FILTER (WHERE order_status='cancelled')
              / COUNT(*), 2)                              AS cancel_rate_pct
FROM shopee.fact_orders
GROUP BY payment_method
ORDER BY cancel_rate_pct DESC;
```

### 🗣️ Cách giải thích
> "Expected: COD cancel rate gấp 2-3 lần prepaid. Rút gọn giải: sàn có thể bắt deposit COD, limit COD cho khách mới, hoặc push ShopeePay."

### 🚀 Extension
COD cancel rate theo city (tỉnh có COD xấu?).

---

## I4 — Return rate theo cat1

**Level:** L2 | **Skill:** JOIN fact_returns | **Est:** 15 phút

### 💡 SQL
```sql
WITH item_return AS (
  SELECT
    p.cat1_name,
    COUNT(DISTINCT i.order_item_id) AS sold,
    COUNT(DISTINCT r.return_id) FILTER (
      WHERE r.return_status IN ('approved','completed')
    ) AS returned
  FROM shopee.fact_order_items i
  JOIN shopee.fact_orders o ON o.order_id = i.order_id
  JOIN shopee.dim_product p ON p.product_id = i.product_id
  LEFT JOIN shopee.fact_returns r ON r.order_item_id = i.order_item_id
  WHERE o.payment_status='paid'
  GROUP BY p.cat1_name
)
SELECT
  cat1_name, sold, returned,
  ROUND(100.0 * returned::numeric / sold, 2) AS return_rate_pct
FROM item_return
ORDER BY return_rate_pct DESC;
```

### 🗣️ Cách giải thích
> "Fashion thường có return rate cao nhất (size không vừa, màu không khớp). Electronics trung bình (lỗi kỹ thuật). Food / FMCG thấp nhất (không return được). Hiểu benchmark theo cat giúp đánh giá seller fair hơn."

### 🚀 Extension
Breakdown theo `return_reason` trong mỗi cat1 để thấy lý do dominant.

---

## I5 — **CASE: COD abuse pattern** — khách nào có pattern đặt COD → cancel lặp lại

**Level:** L4 | **Skill:** Multi-aggregate filter, fraud detection | **Est:** 45 phút

### 🎯 Business context
Có nhóm khách "troll" đặt 10 đơn COD → huỷ hết. Ops phải identify để block hoặc force prepaid.

### 💡 SQL
```sql
WITH cust_stats AS (
  SELECT
    customer_id,
    COUNT(*)                                                                AS total_orders,
    COUNT(*) FILTER (WHERE payment_method='cod')                            AS cod_orders,
    COUNT(*) FILTER (WHERE payment_method='cod' AND order_status='cancelled') AS cod_cancel,
    COUNT(*) FILTER (WHERE order_status='cancelled')                        AS total_cancel
  FROM shopee.fact_orders
  GROUP BY customer_id
)
SELECT
  cs.customer_id, c.customer_name, c.tier, c.city,
  cs.total_orders, cs.cod_orders, cs.cod_cancel,
  ROUND(100.0 * cs.cod_cancel::numeric / NULLIF(cs.cod_orders,0), 2) AS cod_cancel_pct,
  ROUND(100.0 * cs.total_cancel::numeric / cs.total_orders, 2)       AS overall_cancel_pct
FROM cust_stats cs
JOIN shopee.dim_customer c ON c.customer_id = cs.customer_id
WHERE cs.cod_orders >= 5             -- khách có ít nhất 5 đơn COD
  AND cs.cod_cancel >= 3             -- trong đó ≥ 3 cancel
  AND 100.0 * cs.cod_cancel::numeric / cs.cod_orders >= 60   -- >= 60% huỷ
ORDER BY cs.cod_cancel DESC
LIMIT 100;
```

### 🗣️ Cách giải thích
> "Rule định nghĩa 'abuse': (1) ≥5 đơn COD, (2) ≥3 đơn huỷ, (3) tỷ lệ huỷ ≥60%. Đa điều kiện tránh false positive. 2 điều kiện đầu là volume threshold, điều kiện 3 là rate threshold — kết hợp mới đúng.
>
> **Action:** list output gửi Risk team → force customer sang prepaid-only trong N ngày, hoặc require deposit."

### ⚠️ Common mistakes
- Chỉ dùng rate không dùng volume → khách 1 đơn COD huỷ 1 đơn = 100%, không phải abuse thật.
- `NULLIF` khi `cod_orders=0` tránh division error, tuy nhiên với filter >=5 không cần lắm.

### 🚀 Extension
Thêm network analysis: các account cùng IP / cùng địa chỉ giao → phát hiện ring.

---

## I6 — Time-to-cancel distribution

**Level:** L3 | **Skill:** Histogram via CASE buckets | **Est:** 30 phút

### 🎯 Business context
Đa số huỷ trong 1 giờ (khách đổi ý) vs 1 ngày (đợi ship lâu) vs 3 ngày (seller không ship) — mỗi root cause cần giải pháp khác.

### 💡 SQL
```sql
WITH timed AS (
  SELECT
    order_id,
    EXTRACT(EPOCH FROM (cancelled_at - created_at))/3600 AS hours_to_cancel
  FROM shopee.fact_orders
  WHERE order_status='cancelled'
    AND cancelled_at IS NOT NULL
    AND created_at IS NOT NULL
)
SELECT
  CASE
    WHEN hours_to_cancel < 1         THEN '0-1h (impulse)'
    WHEN hours_to_cancel < 6         THEN '1-6h'
    WHEN hours_to_cancel < 24        THEN '6-24h (1 day)'
    WHEN hours_to_cancel < 72        THEN '1-3 days'
    WHEN hours_to_cancel < 168       THEN '3-7 days'
    ELSE '>7 days (stale)'
  END AS bucket,
  COUNT(*)                                                                 AS cnt,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)                       AS pct
FROM timed
GROUP BY bucket
ORDER BY MIN(hours_to_cancel);
```

### 🗣️ Cách giải thích
> "Histogram bằng CASE là cách phổ thông khi Postgres không có hàm histogram built-in nhanh. Order buckets bằng `MIN(hours_to_cancel)` giữ thứ tự thời gian đúng. Insight mẫu: 40% huỷ trong 1h = impulse → UI buyer's remorse (cho phép confirm 2 lần?); 25% huỷ sau 3 ngày = seller không ship → action lên seller SLA."

### 🚀 Extension
Phân tách theo `cancel_reason` — mỗi reason có distribution thời gian khác.
