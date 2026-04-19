# Chủ đề L — Capstone / Open-ended (Mini-project)

Các bài capstone đòi hỏi học viên **kết hợp nhiều chủ đề**, tự lập dashboard hoặc báo cáo hoàn chỉnh. Mỗi bài là 1 mini-project 2-4 giờ. Không có "đáp án duy nhất" — giảng viên chấm theo rubric.

---

## L1 — **Weekly Business Review cho CEO**

**Level:** L4 | **Est:** 3 giờ | **Deliverable:** 1 query lớn (hoặc Google Sheet) + insight markdown 1 trang

### 🎯 Business context
Mỗi sáng thứ Hai, analyst gửi CEO 1 báo cáo 1 trang tóm tắt sức khoẻ sàn tuần trước. CEO xem 2 phút rồi quyết định focus tuần này.

### Yêu cầu đầu ra
KPI phải có (tuần gần nhất + so với tuần trước + so với trung bình 4 tuần):
1. GMV
2. Số đơn
3. AOV
4. Số khách duy nhất
5. New buyer count
6. Top 3 cat1 theo GMV
7. Cancel rate
8. Top 5 seller theo GMV
9. Voucher penetration %

### 🧭 Approach
1. Xác định week_start của tuần gần nhất (`DATE_TRUNC('week', MAX(order_date))`).
2. Dùng CTE `period` tính các period: current_week, last_week, 4w_avg.
3. Mỗi KPI là 1 subquery hoặc `FILTER`.
4. Cuối cùng pivot ngang — báo cáo thường đọc theo hàng.

### 💡 SQL scaffold (không đầy đủ, gợi ý cấu trúc)
```sql
WITH last_week AS (
  SELECT DATE_TRUNC('week', MAX(d.full_date))::date - 7 AS start
  FROM shopee.dim_date d
  WHERE d.date_key = (SELECT MAX(order_date_key) FROM shopee.fact_orders)
),
period AS (
  SELECT
    start                          AS cw_start,
    start - 7                      AS lw_start,
    start - 28                     AS ma4_start
  FROM last_week
),
base AS (
  SELECT
    CASE
      WHEN d.full_date BETWEEN p.cw_start AND p.cw_start + 6 THEN 'cw'
      WHEN d.full_date BETWEEN p.lw_start AND p.lw_start + 6 THEN 'lw'
      WHEN d.full_date BETWEEN p.ma4_start AND p.cw_start - 1 THEN 'ma4'
    END AS period,
    o.*
  FROM shopee.fact_orders o
  JOIN shopee.dim_date    d ON d.date_key = o.order_date_key
  CROSS JOIN period p
  WHERE d.full_date BETWEEN p.ma4_start AND p.cw_start + 6
    AND o.payment_status='paid'
)
SELECT
  -- GMV
  SUM(total_amount) FILTER (WHERE period='cw')              AS gmv_cw,
  SUM(total_amount) FILTER (WHERE period='lw')              AS gmv_lw,
  ROUND(AVG(total_amount) FILTER (WHERE period='ma4')*7, 0) AS gmv_ma4_week,  -- scale lên 1 tuần
  -- Orders
  COUNT(*) FILTER (WHERE period='cw')                       AS orders_cw,
  -- AOV
  AVG(total_amount) FILTER (WHERE period='cw')              AS aov_cw,
  -- New buyer
  COUNT(DISTINCT customer_id) FILTER (WHERE period='cw' AND is_first_order) AS new_buyers_cw,
  -- v.v. các KPI khác
FROM base;
```

### 📝 Insight template (học viên viết tay sau khi có số)
```markdown
# WBR — Tuần 15 (2024-04-08 → 2024-04-14)

## Headlines
- **GMV**: 3.1B (-8% WoW, +3% MA4). Suy giảm sau campaign 4/4 tuần trước.
- **Orders**: 14,200 (-12% WoW). AOV tăng bù một phần.
- **New buyers**: 1,350 (-5% WoW). Marketing đang chậm lại trước 5/5.
- **Cancel rate**: 8.2% (vs 7.5% MA4) — tăng nhẹ, monitor.

## Top 3 categories (GMV)
1. Fashion Nữ: 780M (-10% WoW)
2. Điện Tử: 520M (-15% WoW) — tập trung điều tra
3. ...

## Recommendation
1. Warm-up 5/5 sớm (D-7), đặc biệt cho cat Điện Tử.
2. Review cancel rate tăng — check carrier SLA tuần này.
```

### 🗣️ Cách giải thích cho học viên
> "WBR là sản phẩm signature của analyst. Không có báo cáo WBR tốt → leadership không tin analytics. Nhớ 3 quy tắc: (1) **headlines trước, detail sau** (CEO đọc 30s đầu quyết định đọc tiếp không), (2) **luôn có 3 số để so: current, prior, benchmark** (1 số đơn lẻ vô nghĩa), (3) **recommendation cụ thể**, không đưa 'review kỹ hơn' chung chung."

### ⚠️ Rubric chấm
| Tiêu chí | 5 điểm |
|---|---|
| SQL chạy đúng, có filter chuẩn | 2 |
| Đủ 9 KPI yêu cầu | 1 |
| Có narrative insight (không chỉ số) | 1 |
| Có recommendation action-able | 1 |

---

## L2 — **Post-campaign report** cho 4/4

**Level:** L4 | **Est:** 4 giờ

### 🎯 Business context
Sau mỗi Mega Sale, marketing team làm report "autopsy". Học viên đóng vai analyst marketing, trả lời:
1. So với 3/3, 4/4 tăng/giảm KPI nào?
2. Ngành nào thắng / thua?
3. Voucher nào redeem cao nhất?
4. ROAS theo channel?
5. New buyer từ 4/4 retention ra sao? (có quay lại 2 tuần sau không)
6. 3 recommendation cho 5/5.

### Deliverable
- Markdown 2 trang + 3 biểu đồ (matplotlib / Google Sheet chart screenshot)
- Set 6-8 query SQL kèm

### 🧭 Gợi ý cấu trúc báo cáo
```markdown
# 4/4 Mega Sale Post-mortem

## 1. KPI summary (4/4 vs 3/3)
(bảng)

## 2. Winner / loser by cat1
(bảng top 5 cat tăng / giảm)

## 3. Voucher performance
(top 5 voucher redemption + gmv_per_discount)

## 4. Attribution: paid vs organic
(pie chart GMV share)

## 5. Retention of 4/4 new buyers (14 ngày)
(% quay lại W+1, W+2)

## 6. Recommendation cho 5/5
1. ...
2. ...
3. ...
```

### 🗣️ Cách giải thích
> "Sale autopsy là tài liệu marketing team dùng planning cycle sau. Không được copy-paste template — phải có **3 recommendation cụ thể** dựa trên data. Ví dụ không hợp lệ: 'cải thiện voucher strategy'. Hợp lệ: 'Voucher V123 có redemption 2% (baseline 15%) do min_order 500k quá cao — giảm xuống 300k cho 5/5'."

---

## L3 — **"Tại sao GMV tháng 3 giảm"** — investigation report

**Level:** L4 | **Est:** 3 giờ

### 🎯 Business context
Bạn nhận câu hỏi từ sếp: 'Tháng 3 GMV giảm 15% so với tháng 2, tại sao?' Viết báo cáo điều tra như analyst.

### Yêu cầu
- Phân rã (decomposition tree) ít nhất 3 tầng.
- 3 finding cụ thể với số.
- 2 đề xuất hành động.

### Rubric
| Tiêu chí | Điểm |
|---|---|
| Phân rã logic (không nhảy cóc) | 3 |
| Số chính xác, có thể reproduce | 2 |
| Finding rõ ràng, có bằng chứng | 3 |
| Recommendation actionable | 2 |

### 🗣️ Cách giải thích
> "Đây là bài test signature của ứng viên analyst senior. Người chấm sẽ dò ngược: từ conclusion → finding → data → query. Nếu bất kỳ bước nào nhảy cóc hoặc sai, toàn bộ báo cáo mất giá trị. Đừng cố tìm 'câu chuyện hay' — tìm ra đúng câu chuyện mà **data đang nói**."

---

## L4 — **Seller onboarding success** model

**Level:** L4 | **Est:** 4 giờ

### 🎯 Business context
Seller Ops team muốn biết: **metric nào trong 30 ngày đầu của seller mới predict họ sẽ active sau 90 ngày?**

### Yêu cầu
- List 5-7 candidate metric: # orders first 30d, # SKUs listed, cat1 focus, use ad?, etc.
- Với mỗi metric, so seller "active 90d" vs "inactive 90d".
- Dùng phân tích segment (quartile) hoặc correlation thô.
- Đề xuất 2 metric để thêm vào onboarding program.

### Gợi ý SQL framework
```sql
WITH new_sellers AS (
  SELECT seller_id, join_date_key
  FROM shopee.dim_seller
  WHERE join_date_key BETWEEN 20240201 AND 20240215
),
orders_first_30d AS (
  SELECT ns.seller_id,
    COUNT(o.order_id) AS orders_30d,
    SUM(o.total_amount) AS gmv_30d
  FROM new_sellers ns
  LEFT JOIN shopee.fact_orders o
    ON o.seller_id = ns.seller_id
   AND o.order_date_key BETWEEN ns.join_date_key AND ns.join_date_key + 30
   AND o.payment_status='paid'
  GROUP BY ns.seller_id
),
active_90d AS (
  SELECT ns.seller_id,
    (COUNT(o.order_id) >= 10) AS is_active_90d   -- định nghĩa active
  FROM new_sellers ns
  LEFT JOIN shopee.fact_orders o
    ON o.seller_id = ns.seller_id
   AND o.order_date_key BETWEEN ns.join_date_key + 60 AND ns.join_date_key + 90
   AND o.payment_status='paid'
  GROUP BY ns.seller_id
)
SELECT
  is_active_90d,
  AVG(orders_30d) AS avg_orders_first_30d,
  AVG(gmv_30d)    AS avg_gmv_first_30d,
  COUNT(*)        AS n
FROM orders_first_30d o
JOIN active_90d     a USING (seller_id)
GROUP BY is_active_90d;
```

### 🗣️ Cách giải thích
> "Đây là bài 'predictive analytics đơn giản với SQL' — không cần ML. Logic: tính feature trong window X, đo outcome trong window Y (sau X), so giữa outcome=1 và outcome=0. Feature có giá trị phân biệt lớn = predict tốt. Quy tắc dataset: luôn set cut-off rõ ràng (seller join trước ngày N) để đủ 90 ngày observe."

---

## L5 — **Category growth strategy** — pick 1 cat1 to invest

**Level:** L4 | **Est:** 3 giờ

### 🎯 Business context
Bạn là category manager mới nhận brief: chọn **1 cat1** để invest 5 tỷ ngân sách quý sau. Justify bằng data.

### Framework gợi ý
| Chiều | SQL |
|---|---|
| Size (GMV) | SUM per cat1 |
| Growth | MoM % |
| Margin proxy | 1 - AVG(discount_rate) |
| Competition (seller concentration) | HHI |
| Return rate | fact_returns / items_sold |

### Deliverable
- Ma trận 5×5 (cat × chiều).
- Recommendation + reasoning.
- 1 slide PowerPoint (screenshot).

---

## L6 — **Customer win-back** voucher design

**Level:** L4 | **Est:** 3 giờ

### 🎯 Business context
CRM team chuẩn bị chiến dịch win-back. Muốn personalize voucher dựa trên:
- Cat1 khách hay mua
- AOV trung bình
- Thời gian lapse

### Yêu cầu
- Segment khách lapsed (60d+) thành 3 tier theo historical spending.
- Với mỗi tier, đề xuất voucher value (% vs fixed, min_order) có ROI dự kiến.
- Export CSV (customer_id, email_placeholder, suggested_voucher).

### 🗣️ Cách giải thích
> "Voucher win-back cần cân: quá sâu (50% off) → ăn margin; quá nông (10k off 200k) → không kéo được. Historical AOV × tier của khách giúp calibrate. Học viên phải tự set rule và biện minh."

---

## L7 — **Flash sale vs daily deal** sustainability

**Level:** L4 | **Est:** 3 giờ

### 🎯 Business context
Format promo nào bền vững hơn: flash sale (2h, discount sâu) hay daily deal (24h, discount vừa)? Đo bằng (a) GMV trong promo, (b) GMV 7 ngày sau promo (post-halo hay post-dip).

### Yêu cầu
- Filter theo `campaign_type`.
- Tính GMV in-window và 7d-after.
- So 2 format.
- Kết luận.

### 🗣️ Cách giải thích
> "Bài này test logic 'không chỉ đo số trong campaign, đo cả impact sau campaign'. Promo thành công ngắn hạn nhưng làm khách dừng mua sau đó (cannibalize) thì tổng zero-sum. Format nào có post-halo dương = sustainable."

---

## L8 — **Data quality audit** — tìm 10 anomaly

**Level:** L4 | **Est:** 2 giờ

### 🎯 Business context
Trước khi làm report, analyst nên check data quality. Tìm 10 anomaly trong dataset:

### Checklist gợi ý
1. Orphan FK: `fact_orders.customer_id` không tồn tại trong `dim_customer`.
2. Negative amount: `total_amount < 0` hoặc `subtotal < 0`.
3. Timestamp inversion: `paid_at < created_at`.
4. `cancelled` orders mà có `paid_at` NOT NULL.
5. `completed` orders nhưng `delivered_at` NULL.
6. `order_sn` duplicate.
7. `subtotal - shop_discount - platform_voucher + shipping_fee - shipping_discount - coin_used ≠ total_amount` (quá 10đ).
8. Voucher `discount_applied > order.subtotal`.
9. Shipment `actual_hours < 0`.
10. Order có item_count không khớp `COUNT(fact_order_items)`.

### 🧭 Approach
Viết 10 query ngắn, mỗi query 1 check, return 5-10 ví dụ anomaly.

### 💡 SQL mẫu cho check #7
```sql
SELECT
  order_id, order_sn,
  subtotal, shop_discount, platform_voucher,
  shipping_fee, shipping_discount, coin_used, total_amount,
  (subtotal - shop_discount - platform_voucher + shipping_fee - shipping_discount - coin_used - total_amount) AS diff
FROM shopee.fact_orders
WHERE ABS(subtotal - shop_discount - platform_voucher
         + shipping_fee - shipping_discount - coin_used - total_amount) > 10
LIMIT 10;
```

### 🗣️ Cách giải thích
> "Analyst pro luôn audit trước khi báo cáo. 'Rác vào, rác ra' — 1 anomaly ignored có thể làm toàn bộ báo cáo sai. Build routine: mỗi lần có dataset mới, chạy 10 check này đầu tiên. Khi tìm ra anomaly, không nên delete row — escalate lên data team để fix nguồn."

### ⚠️ Rubric
| Tiêu chí | Điểm |
|---|---|
| Tìm được ≥ 7 anomaly types | 4 |
| Mỗi check có SQL đúng | 3 |
| Có diễn giải root cause đoán được | 2 |
| Đề xuất fix (ở nguồn hay ở report) | 1 |
