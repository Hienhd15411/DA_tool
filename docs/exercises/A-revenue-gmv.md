# Chủ đề A — Revenue / GMV trending & decomposition

Dạy học viên đọc số top-line: GMV, AOV, số đơn theo thời gian; phát hiện xu hướng và giải thích.

---

## A1 — GMV theo tuần 3 tháng qua, tuần nào cao/thấp nhất?

**Level:** L1 | **Skill:** `DATE_TRUNC`, `SUM`, `GROUP BY`, `ORDER BY` | **Est:** 10 phút

### 🎯 Business context
GMV (Gross Merchandise Value) là chỉ số top-line của sàn. Theo tuần cho thấy pattern ổn định hơn theo ngày (giảm noise), và đủ chi tiết để thấy spike do campaign. Đây là câu hỏi mở đầu mọi WBR (Weekly Business Review).

### 🧭 Approach
1. "Tuần" = gộp các ngày về thứ Hai đầu tuần → `DATE_TRUNC('week', full_date)`.
2. Chỉ tính GMV trên đơn đã `paid` (chuẩn business).
3. `GROUP BY` tuần, `SUM(total_amount)`.
4. `ORDER BY gmv DESC` để thấy top/bottom.

### 💡 SQL
```sql
SELECT
  DATE_TRUNC('week', d.full_date)::date AS week_start,
  SUM(o.total_amount)                   AS gmv,
  COUNT(*)                              AS order_cnt
FROM shopee.fact_orders o
JOIN shopee.dim_date  d ON d.date_key = o.order_date_key
WHERE o.payment_status = 'paid'
GROUP BY 1
ORDER BY gmv DESC;
```

### ✅ Expected result (shape)
| week_start | gmv | order_cnt |
|---|---|---|
| 2024-04-01 | 3,214,500,000 | 14,230 |
| 2024-03-04 | 2,890,300,000 | 12,980 |
| 2024-02-12 | 1,105,200,000 | 5,430 *(tuần Tết)* |

### 🗣️ Cách giải thích cho học viên
> "Khi muốn nhóm nhiều ngày vào cùng 1 tuần, dùng `DATE_TRUNC('week', ngày)` — nó trả về thứ Hai của tuần đó dưới dạng `DATE`. Sau đó mình `GROUP BY` theo giá trị đã truncate. Điều đặc biệt quan trọng: GMV luôn filter `payment_status = 'paid'`, vì business không đếm đơn chưa thanh toán hay đã huỷ. Nếu quên filter này, báo cáo sẽ bị inflate đáng kể."

### ⚠️ Common mistakes
- Quên `WHERE payment_status = 'paid'` → GMV phồng 15–20%.
- Dùng `EXTRACT(WEEK FROM ...)` trả về số tuần, khó dùng để sort theo thời gian.
- Group theo `created_at` (timestamp) → mỗi mili-giây là 1 group, sai hoàn toàn.

### 🚀 Extension
Thêm cột `gmv_vs_prev_week_pct` dùng `LAG(gmv) OVER (ORDER BY week_start)`.

---

## A2 — Doanh thu tháng này vs tháng trước, tăng/giảm bao nhiêu %?

**Level:** L2 | **Skill:** `LAG`, window, pivot bằng `FILTER` | **Est:** 15 phút

### 🎯 Business context
Month-over-month (MoM) growth là KPI cơ bản báo cho leadership. Biết cách dùng `LAG` là chìa khoá để không phải self-join thủ công.

### 🧭 Approach
1. Aggregate GMV theo tháng.
2. Dùng `LAG(gmv) OVER (ORDER BY month)` để lấy tháng trước trên cùng dòng.
3. Tính `(this - prev) / prev * 100`.

### 💡 SQL
```sql
WITH monthly AS (
  SELECT
    DATE_TRUNC('month', d.full_date)::date AS month,
    SUM(o.total_amount)                    AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date  d ON d.date_key = o.order_date_key
  WHERE o.payment_status = 'paid'
  GROUP BY 1
)
SELECT
  month,
  gmv,
  LAG(gmv) OVER (ORDER BY month)                                          AS gmv_prev,
  ROUND( (gmv - LAG(gmv) OVER (ORDER BY month))
         / LAG(gmv) OVER (ORDER BY month) * 100, 2)                       AS mom_pct
FROM monthly
ORDER BY month;
```

### ✅ Expected result
| month | gmv | gmv_prev | mom_pct |
|---|---|---|---|
| 2024-02-01 | 8,900,000,000 | NULL | NULL |
| 2024-03-01 | 12,400,000,000 | 8,900,000,000 | 39.33 |
| 2024-04-01 | 10,800,000,000 | 12,400,000,000 | -12.90 |

### 🗣️ Cách giải thích cho học viên
> "Nếu chưa biết window function, mình sẽ phải self-join bảng monthly với chính nó theo `month = prev_month + 1`. Xấu và dễ sai. `LAG` là cách Postgres bảo: 'nhìn dòng ngay trước đó' — nó phải có `ORDER BY` để biết 'trước' là gì. `LAG(gmv) OVER (ORDER BY month)` nghĩa là: xếp theo month, lấy giá trị gmv của dòng kế trên."

### ⚠️ Common mistakes
- Thiếu `ORDER BY` trong window → kết quả không xác định.
- Chia cho 0 nếu `gmv_prev = 0` → dùng `NULLIF(gmv_prev, 0)` phòng xa.
- Dùng `LAG(gmv, 12)` khi muốn YoY nhưng dataset chỉ 3 tháng → lúc nào cũng NULL.

### 🚀 Extension
Thêm `LAG(gmv, 2)` để so với cách 2 tháng trước; dùng `FIRST_VALUE` tính growth so với tháng đầu tiên.

---

## A3 — **CASE: Tại sao GMV tháng 3 giảm 15% vs tháng 2?**

**Level:** L4 | **Skill:** multi-CTE, decomposition | **Est:** 45–60 phút

### 🎯 Business context
Đây là câu hỏi "tại sao" điển hình mà PM / BOD sẽ hỏi analyst. Phải biết **phân rã** thay vì trả lời một con số. Decomposition tree:

```
GMV = số đơn × AOV
số đơn = số khách × đơn/khách
số khách = khách mới + khách cũ
AOV = f(cat mix, campaign mix, voucher rate)
```

### 🧭 Approach
1. Xác nhận chênh lệch GMV thật sự bao nhiêu.
2. Tách GMV = `orders × AOV`. Số nào drop?
3. Nếu orders drop: `customers × orders_per_customer`. Mất khách hay khách mua ít?
4. Nếu AOV drop: do category shift (khách mua món rẻ hơn) hay discount rate tăng?
5. So theo `cat1` để thấy ngành nào đóng góp nhất.

### 💡 SQL — Bước 1: Decomposition top-level
```sql
WITH m AS (
  SELECT
    d.month,
    COUNT(*)                                AS orders,
    COUNT(DISTINCT o.customer_id)           AS buyers,
    SUM(o.total_amount)                     AS gmv,
    AVG(o.total_amount)                     AS aov,
    SUM(o.shop_discount+o.platform_voucher+o.shipping_discount)
       / NULLIF(SUM(o.subtotal),0) * 100    AS discount_rate_pct
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid' AND d.month IN (2,3)
  GROUP BY d.month
)
SELECT *,
  ROUND(gmv::numeric / LAG(gmv) OVER (ORDER BY month) - 1, 4)*100 AS gmv_chg_pct,
  ROUND(orders::numeric / LAG(orders) OVER (ORDER BY month) - 1,4)*100 AS orders_chg_pct,
  ROUND(aov::numeric / LAG(aov) OVER (ORDER BY month) - 1,4)*100       AS aov_chg_pct
FROM m;
```

### 💡 SQL — Bước 2: Phân rã theo cat1
```sql
SELECT
  p.cat1_name,
  SUM(CASE WHEN d.month=2 THEN i.line_total END) AS gmv_feb,
  SUM(CASE WHEN d.month=3 THEN i.line_total END) AS gmv_mar,
  ROUND( (SUM(CASE WHEN d.month=3 THEN i.line_total END)
          - SUM(CASE WHEN d.month=2 THEN i.line_total END))
         / NULLIF(SUM(CASE WHEN d.month=2 THEN i.line_total END),0) * 100, 2) AS mom_pct,
  SUM(CASE WHEN d.month=3 THEN i.line_total END)
    - SUM(CASE WHEN d.month=2 THEN i.line_total END) AS gmv_delta
FROM shopee.fact_order_items i
JOIN shopee.fact_orders o ON o.order_id = i.order_id
JOIN shopee.dim_product  p ON p.product_id = i.product_id
JOIN shopee.dim_date     d ON d.date_key = o.order_date_key
WHERE o.payment_status='paid' AND d.month IN (2,3)
GROUP BY p.cat1_name
ORDER BY gmv_delta;   -- âm nhất lên đầu = ngành đóng góp giảm nhiều nhất
```

### 💡 SQL — Bước 3: New vs returning
```sql
SELECT d.month,
  SUM(CASE WHEN o.is_first_order THEN o.total_amount END) AS gmv_new,
  SUM(CASE WHEN NOT o.is_first_order THEN o.total_amount END) AS gmv_returning
FROM shopee.fact_orders o
JOIN shopee.dim_date d ON d.date_key = o.order_date_key
WHERE o.payment_status='paid' AND d.month IN (2,3)
GROUP BY d.month;
```

### ✅ Expected insight shape
> Tháng 3 GMV giảm 15%. Phân rã: orders -12%, AOV -3%. Orders giảm chủ yếu do khách returning (-18%, khách mới vẫn tăng 5%). Ngành **Fashion Nữ (-28%)** và **Điện Tử (-22%)** chiếm 70% sụt giảm. Khả năng cao do tháng 2 có Tết + sale cuối Tết đẩy mạnh, tháng 3 rơi vào mùa trũng trước 3/3. Hypothesis tiếp: kiểm tra ad spend tháng 3 có cắt không.

### 🗣️ Cách giải thích cho học viên
> "Đừng trả lời 'GMV giảm 15%' rồi dừng. Senior analyst sẽ **phân rã**: GMV là tích của orders và AOV — cái nào giảm? Orders là tích của buyers và orders/buyer — buyers nào? Làm theo tree này sẽ luôn tìm được gốc. Kỹ thuật SQL: dùng `SUM(CASE WHEN month=2 THEN ...)` để pivot tháng thành cột cạnh nhau — đây là pattern pivot kinh điển khi không có `PIVOT` native."

### ⚠️ Common mistakes
- Chỉ trả lời top-level mà không phân rã — mất điểm với PM.
- Dùng `AVG(total_amount)` để tính AOV theo tháng nhưng quên filter `paid`.
- Nhầm số: khi cat1 có mom_pct giảm nhiều nhất **không đồng nghĩa** đóng góp nhiều nhất về **giá trị tuyệt đối**. Dùng cả `mom_pct` và `gmv_delta`.

### 🚀 Extension
Thêm dim_date.`is_holiday` để loại mùng Tết ra khỏi so sánh. Làm decomposition level 3 tiếp theo cat2.

---

## A4 — Daily GMV + 7-day moving average

**Level:** L2 | **Skill:** window frame `ROWS BETWEEN` | **Est:** 15 phút

### 🎯 Business context
MA7 làm phẳng noise cuối tuần vs ngày thường → nhìn trend thực tế rõ hơn. Luôn xuất hiện trên dashboard.

### 🧭 Approach
1. Aggregate GMV ngày.
2. `AVG(gmv) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)`.

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date AS dt, SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date
)
SELECT
  dt, gmv,
  ROUND(AVG(gmv) OVER (ORDER BY dt ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 0) AS ma7
FROM daily
ORDER BY dt;
```

### ✅ Expected result
| dt | gmv | ma7 |
|---|---|---|
| 2024-02-01 | 280M | 280M |
| 2024-02-07 | 320M | 295M |
| 2024-03-03 | 820M | 410M *(Mega Sale spike)* |

### 🗣️ Cách giải thích
> "`ROWS BETWEEN 6 PRECEDING AND CURRENT ROW` = cửa sổ 7 ngày gồm hôm nay + 6 ngày trước. Chú ý 6 ngày đầu của dataset sẽ có MA7 thiếu ngày, nhưng Postgres vẫn tính trung bình trên số ngày có sẵn — không null."

### ⚠️ Common mistakes
- Quên `ORDER BY` → frame không xác định.
- Dùng `RANGE BETWEEN '6 days' PRECEDING` — chạy được nhưng phức tạp hơn `ROWS`.

### 🚀 Extension
Thêm MA28, so sánh MA7 vs MA28 để bắt inflection point.

---

## A5 — Weekday vs weekend: GMV trung bình khác nhau ra sao?

**Level:** L1 | **Skill:** JOIN dim_date, GROUP BY boolean | **Est:** 8 phút

### 🎯 Business context
Dùng để plan stock, CS staffing, campaign timing.

### 🧭 Approach
GROUP BY `is_weekend`, tính GMV/ngày trung bình (chứ không phải tổng — để công bằng vì weekday có 5 ngày/tuần còn weekend có 2).

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date, d.is_weekend, SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date, d.is_weekend
)
SELECT
  is_weekend,
  COUNT(*)          AS n_days,
  AVG(gmv)::bigint  AS avg_gmv_per_day
FROM daily
GROUP BY is_weekend;
```

### ✅ Expected result
| is_weekend | n_days | avg_gmv_per_day |
|---|---|---|
| false | 64 | 285,000,000 |
| true  | 26 | 410,000,000 |

### 🗣️ Cách giải thích
> "Cạm bẫy: nếu chỉ làm `SUM(gmv) GROUP BY is_weekend` thì weekday thắng vì có nhiều ngày hơn — so sánh không công bằng. Luôn chuyển về **GMV/ngày trung bình** khi đếm buckets có size khác nhau."

### ⚠️ Common mistakes
- So tổng thay vì trung bình → sai kết luận.
- Quên trừ holiday ra — holiday rơi vào weekday có thể lệch số.

### 🚀 Extension
Breakdown theo từng thứ trong tuần (`day_name`) để thấy weekend thật sự là ngày nào.

---

## A6 — Giờ nào trong ngày bán chạy nhất?

**Level:** L2 | **Skill:** `EXTRACT(hour)`, timezone conversion | **Est:** 15 phút

### 🎯 Business context
Peak hour quyết định: (1) push notification timing, (2) flash sale window, (3) CS staffing, (4) warehouse picking wave.

### 🧭 Approach
1. Convert `created_at` UTC → `Asia/Ho_Chi_Minh` trước khi lấy giờ.
2. `EXTRACT(hour FROM ...)` lấy 0–23.
3. GROUP BY giờ.

### 💡 SQL
```sql
SELECT
  EXTRACT(hour FROM o.created_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::int AS hour_vn,
  COUNT(*)                        AS orders,
  SUM(o.total_amount)             AS gmv,
  ROUND(AVG(o.total_amount), 0)   AS aov
FROM shopee.fact_orders o
WHERE o.payment_status='paid'
GROUP BY hour_vn
ORDER BY hour_vn;
```

### ✅ Expected result
| hour_vn | orders | gmv | aov |
|---|---|---|---|
| 0 | 420 | 89M | 212k |
| 9 | 1,200 | 280M | 233k |
| 12 | 1,850 | 420M | 227k *(lunch peak)* |
| 21 | 2,900 | 680M | 234k *(prime time)* |

### 🗣️ Cách giải thích
> "Lưu `TIMESTAMPTZ` mặc định là UTC trong Postgres. Nếu không convert về giờ VN, peak hour sẽ bị lệch 7 tiếng — báo cáo sai. `AT TIME ZONE 'Asia/Ho_Chi_Minh'` là cách chuẩn. Lưu ý: nếu cột là `TIMESTAMP` (không có tz), `AT TIME ZONE` lại có ý nghĩa ngược — coi timestamp đó là ở tz đó rồi convert về UTC. Biết kiểu cột rất quan trọng."

### ⚠️ Common mistakes
- Quên convert timezone → peak lệch.
- `EXTRACT(hour)` trên `DATE` sẽ báo lỗi — phải dùng timestamp.

### 🚀 Extension
Heatmap 7×24 (ngày × giờ) — hữu ích cực kỳ cho ops staffing.

---

## A7 — YoY growth từng ngày (so với 3 tháng trước)

**Level:** L3 | **Skill:** self-join theo date offset | **Est:** 25 phút

### 🎯 Business context
Ở dataset 3 tháng không có YoY thực, nhưng bạn có thể thay bằng "so với X ngày trước" — kỹ năng giống hệt.

### 🧭 Approach
1. Aggregate daily GMV.
2. Self-join với offset 84 ngày (12 tuần) để so ngày "cùng thứ".
3. Tính % growth, lấy top 5.

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date AS dt, SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date
)
SELECT
  a.dt                                     AS dt,
  a.gmv                                    AS gmv_now,
  b.gmv                                    AS gmv_84d_ago,
  ROUND((a.gmv - b.gmv) / b.gmv * 100, 2)  AS pct_growth
FROM daily a
JOIN daily b ON b.dt = a.dt - INTERVAL '84 days'
ORDER BY pct_growth DESC
LIMIT 5;
```

### 🗣️ Cách giải thích
> "Self-join = join một bảng với chính nó qua offset thời gian. Chìa khoá là alias khác nhau (`a`, `b`) và join condition là `b.dt = a.dt - INTERVAL 'N days'`. `INTERVAL` là kiểu Postgres dùng cho date math."

### ⚠️ Common mistakes
- Subtract `date - integer` trả về `date` (OK), nhưng `timestamp - integer` lỗi — phải dùng `INTERVAL`.
- Chia cho 0 khi gmv cũ = 0.

### 🚀 Extension
Dùng `LAG(gmv, 84) OVER (ORDER BY dt)` thay cho self-join — gọn hơn.

---

## A8 — **CASE: Báo cáo GMV đột biến (anomaly detection)**

**Level:** L4 | **Skill:** statistical window, `STDDEV`, `AVG` | **Est:** 40 phút

### 🎯 Business context
Business cần alert sớm khi GMV bất thường (có thể do bug tracking, sale không plan, hoặc outage). Analyst build rule đơn giản: **|GMV - MA7| > 2 × STDDEV7** = spike/dip.

### 🧭 Approach
1. Tính GMV daily.
2. Cửa sổ 7 ngày: `AVG` và `STDDEV`.
3. Flag nếu lệch > 2σ, phân loại spike vs dip.
4. Join với `dim_date` để giải thích (sale day? holiday?).

### 💡 SQL
```sql
WITH daily AS (
  SELECT d.full_date AS dt, d.is_sale_day, d.is_holiday,
         SUM(o.total_amount) AS gmv
  FROM shopee.fact_orders o
  JOIN shopee.dim_date d ON d.date_key = o.order_date_key
  WHERE o.payment_status='paid'
  GROUP BY d.full_date, d.is_sale_day, d.is_holiday
),
stats AS (
  SELECT *,
    AVG(gmv)    OVER w AS ma7,
    STDDEV(gmv) OVER w AS sd7
  FROM daily
  WINDOW w AS (ORDER BY dt ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING)
)
SELECT dt, gmv, ma7::bigint AS ma7, sd7::bigint AS sd7,
  ROUND((gmv - ma7)/NULLIF(sd7,0), 2) AS z_score,
  CASE
    WHEN gmv > ma7 + 2*sd7 THEN 'SPIKE'
    WHEN gmv < ma7 - 2*sd7 THEN 'DIP'
    ELSE 'normal'
  END AS anomaly,
  is_sale_day, is_holiday
FROM stats
WHERE gmv > ma7 + 2*sd7 OR gmv < ma7 - 2*sd7
ORDER BY dt;
```

### ✅ Expected result
| dt | gmv | ma7 | sd7 | z_score | anomaly | is_sale_day | is_holiday |
|---|---|---|---|---|---|---|---|
| 2024-02-10 | 95M | 250M | 22M | -7.05 | DIP | false | true *(Tết)* |
| 2024-03-03 | 820M | 310M | 30M | 17.0 | SPIKE | true | false |

### 🗣️ Cách giải thích
> "Đây là mẫu **control chart** đơn giản mà analyst dùng để bắt anomaly. Lưu ý `WINDOW w AS (...)` trong Postgres cho phép định nghĩa window một lần rồi dùng lại — gọn code. Window dùng 7 ngày *trước* (`1 PRECEDING`) để tránh leak: nếu ngày hôm đó đã spike, đừng để nó kéo mean lên chính nó. Kết quả anomaly luôn phải kèm **giải thích** — nhìn `is_sale_day` / `is_holiday` để giải mã. Nếu không khớp cái nào → dấu hiệu cần investigate sâu."

### ⚠️ Common mistakes
- Window include ngày hiện tại → spike làm tăng mean, giảm độ nhạy detection.
- Dùng `STDDEV` (sample) vs `STDDEV_POP` — trong 7 điểm không khác biệt nhiều, chọn `STDDEV` mặc định.
- 2σ quá rộng với n=7 → thực tế nên dùng 2.5σ hoặc n=14. Đây là trade-off sensitivity vs noise.

### 🚀 Extension
Build view `anomaly_daily` chạy hàng ngày cho ops team. Thêm breakdown theo cat1 để biết anomaly đến từ ngành nào.
