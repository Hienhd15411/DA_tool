# Chủ đề J — Customer Service

Ticket CS phản ánh pain point thực. Analyst phải giúp CS team priority và measure SLA.

---

## J1 — Volume ticket CS theo tuần

**Level:** L1 | **Skill:** DATE_TRUNC | **Est:** 8 phút

### 💡 SQL
```sql
SELECT
  DATE_TRUNC('week', created_at)::date AS week_start,
  COUNT(*)                              AS tickets,
  COUNT(*) FILTER (WHERE priority='urgent') AS urgent
FROM shopee.fact_customer_service_ticket
GROUP BY 1
ORDER BY 1;
```

### 🗣️ Cách giải thích
> "Baseline ticket volume để biết 'tuần bình thường' bao nhiêu ticket. Spike cần investigate — có thể trùng campaign, outage, hoặc bug app."

### 🚀 Extension
So với GMV/đơn tuần đó → tính `ticket_per_1000_orders`, chuẩn hoá.

---

## J2 — Top ticket_category

**Level:** L1 | **Skill:** GROUP BY | **Est:** 5 phút

### 💡 SQL
```sql
SELECT
  category,
  COUNT(*)                                            AS tickets,
  ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)  AS pct
FROM shopee.fact_customer_service_ticket
GROUP BY category
ORDER BY tickets DESC;
```

### 🗣️ Cách giải thích
> "Thường 'shipping' và 'refund' chiếm >50%. Biết category giúp invest: shipping issue → push carrier improvement; refund issue → đơn giản hoá flow hoàn tiền."

### 🚀 Extension
Top category theo tháng — có migrate pattern không.

---

## J3 — Resolution time: mean, median, p95

**Level:** L2 | **Skill:** `PERCENTILE_CONT`, date diff | **Est:** 15 phút

### 💡 SQL
```sql
WITH t AS (
  SELECT
    category,
    priority,
    EXTRACT(EPOCH FROM (resolved_at - created_at))/3600 AS hours_to_resolve
  FROM shopee.fact_customer_service_ticket
  WHERE resolved_at IS NOT NULL
)
SELECT
  category, priority,
  COUNT(*)                                                            AS resolved,
  ROUND(AVG(hours_to_resolve)::numeric, 1)                            AS mean_h,
  ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY hours_to_resolve)::numeric, 1) AS median_h,
  ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY hours_to_resolve)::numeric, 1) AS p95_h
FROM t
GROUP BY category, priority
ORDER BY category, priority;
```

### 🗣️ Cách giải thích
> "`PERCENTILE_CONT(0.5)` = median liên tục (interpolate giữa 2 giá trị gần 0.5). `PERCENTILE_DISC(0.5)` = lấy value thực tại vị trí đó. Cho resolution time, `_CONT` thường dùng hơn. `p95` là SLA commitment cho leadership: 'chúng tôi resolve 95% ticket trong X giờ'."

### 🚀 Extension
Breakdown theo agent (nếu có cột assignee) — agent nào nhanh nhất.

---

## J4 — Seller nào có ticket/order ratio cao

**Level:** L3 | **Skill:** Multi-fact ratio | **Est:** 25 phút

### 🎯 Business context
Seller tốt không chỉ là seller bán nhiều. Seller có nhiều ticket/đơn = chất lượng dịch vụ kém, làm khổ CS team.

### 💡 SQL
```sql
WITH seller_tickets AS (
  SELECT seller_id, COUNT(*) AS ticket_cnt
  FROM shopee.fact_customer_service_ticket
  WHERE seller_id IS NOT NULL
  GROUP BY seller_id
),
seller_orders AS (
  SELECT seller_id, COUNT(*) AS order_cnt
  FROM shopee.fact_orders
  WHERE payment_status='paid'
  GROUP BY seller_id
)
SELECT
  s.seller_id, s.shop_name, s.shop_type,
  so.order_cnt, COALESCE(st.ticket_cnt,0) AS ticket_cnt,
  ROUND(1000.0 * COALESCE(st.ticket_cnt,0) / so.order_cnt, 2) AS tickets_per_1000_orders
FROM shopee.dim_seller s
JOIN seller_orders so ON so.seller_id = s.seller_id
LEFT JOIN seller_tickets st ON st.seller_id = s.seller_id
WHERE so.order_cnt >= 100
ORDER BY tickets_per_1000_orders DESC
LIMIT 30;
```

### 🗣️ Cách giải thích
> "Chuẩn hoá theo order: `ticket_cnt / order_cnt × 1000`. Không normalize thì seller lớn luôn nhiều ticket (vì có nhiều đơn), không fair. Benchmark: 5-10 ticket/1000 đơn là bình thường; >30 là vấn đề."

### 🚀 Extension
Thêm category breakdown: seller này bị ticket loại gì (shipping? quality?) nhiều nhất.

---

## J5 — **CASE: Ticket spike có trùng campaign / shipping issue?**

**Level:** L4 | **Skill:** Time-series correlation | **Est:** 45 phút

### 🎯 Business context
CS team hỏi: 'tuần này ticket tăng 40%, do đâu?'. Analyst phải join với các event (campaign, shipping trouble) cùng thời điểm để tìm root cause.

### 💡 SQL
```sql
WITH ticket_daily AS (
  SELECT
    DATE_TRUNC('day', created_at)::date AS dt,
    COUNT(*)                              AS tickets,
    COUNT(*) FILTER (WHERE category='shipping') AS ship_tickets,
    COUNT(*) FILTER (WHERE category='refund')   AS refund_tickets
  FROM shopee.fact_customer_service_ticket
  GROUP BY 1
),
context AS (
  SELECT
    d.full_date AS dt,
    d.is_sale_day,
    d.is_holiday,
    (SELECT COUNT(*) FROM shopee.fact_orders o
       WHERE o.order_date_key = d.date_key AND o.payment_status='paid') AS orders,
    (SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_on_time)/COUNT(*), 2)
       FROM shopee.fact_shipment sh
       JOIN shopee.fact_orders o2 ON o2.order_id = sh.order_id
      WHERE o2.order_date_key = d.date_key
    ) AS late_ship_pct
  FROM shopee.dim_date d
),
joined AS (
  SELECT t.*, c.is_sale_day, c.is_holiday, c.orders, c.late_ship_pct,
         AVG(t.tickets) OVER (ORDER BY t.dt ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS ma7_tickets
  FROM ticket_daily t
  JOIN context c ON c.dt = t.dt
)
SELECT
  dt, tickets, ma7_tickets::bigint,
  ROUND(100.0 * (tickets - ma7_tickets) / NULLIF(ma7_tickets,0), 1) AS pct_vs_ma7,
  ship_tickets, refund_tickets,
  is_sale_day, is_holiday, orders, late_ship_pct
FROM joined
WHERE tickets > ma7_tickets * 1.3    -- spike >30% vs baseline
ORDER BY dt;
```

### 🗣️ Cách giải thích
> "Join 3 nguồn: ticket daily, dim_date (sale/holiday flag), fact_orders/shipment (late ship %). Output là những ngày spike kèm context giải thích. Analyst đọc kết quả rồi viết narrative:
>
> 'Ngày 3/3: tickets tăng 45% — do sale day, volume đơn gấp 3 lần, late_ship_pct lên 18% (normal 8%) → spike ticket shipping chiếm 60%. Root cause: capacity carrier chưa scale kịp cho sale.'
>
> Đây là pattern 'correlate metric anomaly with event log' — analyst DA senior dùng hàng ngày."

### ⚠️ Common mistakes
- Chỉ nhìn số ticket tăng không nhìn context → kết luận sai root cause.
- `ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING` — nếu include ngày hiện tại thì spike tự nâng baseline, giảm sensitivity.

### 🚀 Extension
Tạo view `ticket_anomaly_daily` chạy hàng sáng cho CS manager.
