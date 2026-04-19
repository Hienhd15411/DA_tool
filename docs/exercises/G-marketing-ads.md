# Chủ đề G — Marketing / Ads (ROAS, Funnel)

Đo hiệu quả ad spend, chuyển đổi funnel, attribution.

---

## G1 — Tổng ad spend 3 tháng theo campaign

**Level:** L1 | **Skill:** GROUP BY | **Est:** 5 phút

### 💡 SQL
```sql
SELECT
  c.campaign_name, c.campaign_type,
  SUM(s.spend_amount) AS total_spend,
  SUM(s.impressions)  AS total_impr,
  SUM(s.clicks)       AS total_clicks
FROM shopee.fact_ad_spend s
JOIN shopee.dim_campaign c ON c.campaign_id = s.campaign_id
GROUP BY c.campaign_name, c.campaign_type
ORDER BY total_spend DESC;
```

### 🗣️ Cách giải thích
> "Luôn bắt đầu bằng câu hỏi 'đã tiêu bao nhiêu' trước khi hỏi 'có hiệu quả không'. Bài này là cơ sở cho các phân tích ROAS sau."

### 🚀 Extension
Trend spend theo tuần để thấy cadence budget.

---

## G2 — CTR, CPC, CPA theo campaign

**Level:** L2 | **Skill:** ratio, JOIN fact_ad_performance_daily | **Est:** 20 phút

### 🎯 Business context
3 chỉ số marketing kinh điển:
- **CTR** = clicks / impressions
- **CPC** = spend / clicks
- **CPA** = spend / orders_attributed

### 💡 SQL
```sql
WITH perf AS (
  SELECT
    campaign_id,
    SUM(impressions)       AS impr,
    SUM(clicks)            AS clicks,
    SUM(orders_attributed) AS orders
  FROM shopee.fact_ad_performance_daily
  GROUP BY campaign_id
),
spend AS (
  SELECT campaign_id, SUM(spend_amount) AS spend
  FROM shopee.fact_ad_spend
  GROUP BY campaign_id
)
SELECT
  c.campaign_name,
  s.spend,
  p.impr, p.clicks, p.orders,
  ROUND(100.0 * p.clicks::numeric / NULLIF(p.impr,0), 2) AS ctr_pct,
  ROUND(s.spend::numeric / NULLIF(p.clicks,0), 0)       AS cpc,
  ROUND(s.spend::numeric / NULLIF(p.orders,0), 0)       AS cpa
FROM shopee.dim_campaign c
LEFT JOIN spend s ON s.campaign_id = c.campaign_id
LEFT JOIN perf  p ON p.campaign_id = c.campaign_id
ORDER BY cpa;
```

### 🗣️ Cách giải thích
> "CTR đánh giá creative (đẹp/có hút click không). CPC đánh giá bidding strategy. CPA cuối cùng mới là tiền thật ra đơn. Xếp theo CPA tăng dần → campaign hiệu quả nhất lên đầu. Benchmark nội bộ: Shopee e-com, CPA ~30-80k/đơn tuỳ cat."

### ⚠️ Common mistakes
- Tính CTR từ spend thay vì clicks/impressions → nhầm khái niệm.
- Nhân nhiều dòng khi JOIN 2 bảng aggregate sai cấp → mỗi aggregate gói trong CTE riêng rồi join.

### 🚀 Extension
Thêm ROAS column và xếp combo 3D CPA/CTR/ROAS để thấy bức tranh.

---

## G3 — **ROAS** ranking

**Level:** L3 | **Skill:** multi-fact join | **Est:** 25 phút

### 💡 SQL
```sql
WITH gmv AS (
  SELECT campaign_id, SUM(gmv_attributed) AS gmv
  FROM shopee.fact_ad_performance_daily
  GROUP BY campaign_id
),
spend AS (
  SELECT campaign_id, SUM(spend_amount) AS spend
  FROM shopee.fact_ad_spend
  GROUP BY campaign_id
)
SELECT
  c.campaign_name, c.campaign_type,
  s.spend, g.gmv,
  ROUND(g.gmv::numeric / NULLIF(s.spend,0), 2) AS roas
FROM shopee.dim_campaign c
JOIN spend s ON s.campaign_id = c.campaign_id
JOIN gmv   g ON g.campaign_id = c.campaign_id
ORDER BY roas DESC;
```

### 🗣️ Cách giải thích
> "ROAS = 1đ tiền ad sinh ra bao nhiêu đ GMV. ROAS > 4 thường là healthy cho e-commerce (GMV / gross margin / ad ratio cân bằng). ROAS < 1 là lỗ trắng. Lưu ý: `gmv_attributed` dựa vào model attribution của platform (last click thường), không phải GMV tuyệt đối."

### 🚀 Extension
ROAS theo channel (search/display/affiliate/kol) — kênh nào hiệu quả nhất.

---

## G4 — Ngày nào spend cao nhưng GMV không tương xứng (overspend alert)

**Level:** L3 | **Skill:** ratio + threshold | **Est:** 25 phút

### 🎯 Business context
Early warning cho marketing manager: rẽ tiền nhiều nhưng không kéo GMV → creative lỗi, bidding lỗi, hoặc market saturated.

### 💡 SQL
```sql
WITH daily AS (
  SELECT s.date_key,
    SUM(s.spend_amount) AS spend,
    SUM(p.gmv_attributed) AS gmv,
    SUM(p.orders_attributed) AS orders
  FROM shopee.fact_ad_spend s
  FULL OUTER JOIN shopee.fact_ad_performance_daily p
    ON p.date_key = s.date_key AND p.campaign_id = s.campaign_id
  GROUP BY s.date_key
),
marked AS (
  SELECT *,
    gmv::numeric / NULLIF(spend,0) AS roas,
    AVG(gmv::numeric / NULLIF(spend,0)) OVER () AS roas_avg
  FROM daily
)
SELECT d.full_date, m.spend, m.gmv, m.orders,
  ROUND(m.roas, 2) AS roas,
  ROUND(m.roas_avg, 2) AS roas_avg,
  CASE WHEN m.roas < m.roas_avg * 0.5 THEN 'OVERSPEND_ALERT' ELSE 'ok' END AS flag
FROM marked m
JOIN shopee.dim_date d ON d.date_key = m.date_key
WHERE m.roas < m.roas_avg * 0.5
ORDER BY d.full_date;
```

### 🗣️ Cách giải thích
> "Alert rule: ngày nào ROAS < 50% trung bình → flag. Ngưỡng 50% là lựa chọn biz, có thể điều chỉnh. `AVG OVER ()` (không partition) = trung bình tất cả dòng, dùng làm baseline."

### 🚀 Extension
Breakdown theo channel để xem kênh nào gây overspend.

---

## G5 — **CASE: Budget reallocation** — chuyển budget từ campaign nào sang campaign nào

**Level:** L4 | **Skill:** marginal ROAS, optimization framing | **Est:** 50 phút

### 🎯 Business context
Câu hỏi CMO: "Tôi có 10 tỷ ad budget tháng tới. Nên cắt ở đâu và bơm vào đâu?"

### 🧭 Approach
1. Tính ROAS mỗi campaign.
2. Xếp campaign thành 4 quadrant: High ROAS × High spend, High × Low, Low × High, Low × Low.
3. Recommend:
   - **Low ROAS × High spend** → cắt mạnh
   - **High ROAS × Low spend** → bơm thêm (nhưng cẩn thận diminishing return)
   - Low × Low → quan sát
   - High × High → giữ nguyên

### 💡 SQL
```sql
WITH c AS (
  SELECT
    c.campaign_id, c.campaign_name, c.campaign_type,
    COALESCE(s.spend,0) AS spend,
    COALESCE(g.gmv,0)   AS gmv,
    COALESCE(g.gmv,0)::numeric / NULLIF(s.spend,0) AS roas
  FROM shopee.dim_campaign c
  LEFT JOIN (SELECT campaign_id, SUM(spend_amount) spend
             FROM shopee.fact_ad_spend GROUP BY campaign_id) s USING (campaign_id)
  LEFT JOIN (SELECT campaign_id, SUM(gmv_attributed) gmv
             FROM shopee.fact_ad_performance_daily GROUP BY campaign_id) g USING (campaign_id)
),
stats AS (
  SELECT *,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY spend) OVER () AS spend_median,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY roas)  OVER () AS roas_median
  FROM c
)
SELECT
  campaign_name, campaign_type,
  spend, gmv, ROUND(roas,2) AS roas,
  CASE
    WHEN roas >= roas_median AND spend >= spend_median THEN 'STAR — giữ nguyên'
    WHEN roas >= roas_median AND spend <  spend_median THEN 'SCALE UP — bơm thêm'
    WHEN roas <  roas_median AND spend >= spend_median THEN 'CUT — cắt mạnh'
    ELSE 'WATCH — quan sát'
  END AS recommendation,
  spend - spend_median AS spend_vs_median
FROM stats
ORDER BY recommendation, roas DESC;
```

### 🗣️ Cách giải thích
> "Framework 2×2 quadrant là cách analyst communicate với leadership — 1 bức ảnh đáng nghìn lời. SQL chỉ là tool, quan trọng là **recommendation cụ thể** kèm theo. Lưu ý: khuyến nghị SCALE UP phải kèm caveat 'có thể có diminishing return khi bơm thêm budget quá nhanh' — lời khuyên tốt đi kèm uncertainty."

### 🚀 Extension
Thêm time dimension: so ROAS tuần gần nhất vs trung bình 3 tháng để phát hiện campaign đang xuống.

---

## G6 — Funnel: impression → click → session → order → GMV

**Level:** L3 | **Skill:** multi-stage aggregation, conversion | **Est:** 30 phút

### 🎯 Business context
Funnel analysis chỉ ra chỗ leak lớn nhất để ưu tiên fix.

### 💡 SQL
```sql
WITH stages AS (
  SELECT
    (SELECT SUM(impressions) FROM shopee.fact_ad_spend)                 AS impressions,
    (SELECT SUM(clicks)      FROM shopee.fact_ad_spend)                 AS clicks,
    (SELECT COUNT(*) FROM shopee.fact_traffic_session WHERE traffic_source='paid') AS sessions,
    (SELECT COUNT(*) FROM shopee.fact_traffic_session
        WHERE traffic_source='paid' AND has_order)                      AS ordered_sessions,
    (SELECT SUM(o.total_amount) FROM shopee.fact_orders o
        JOIN shopee.fact_traffic_session t ON t.customer_id = o.customer_id
        WHERE t.traffic_source='paid' AND o.payment_status='paid')      AS gmv
)
SELECT
  impressions, clicks,
  ROUND(100.0*clicks::numeric/impressions, 2)         AS ctr_pct,
  sessions,
  ROUND(100.0*sessions::numeric/clicks, 2)            AS click_to_session_pct,
  ordered_sessions,
  ROUND(100.0*ordered_sessions::numeric/sessions, 2)  AS conversion_pct,
  gmv
FROM stages;
```

### 🗣️ Cách giải thích
> "Dùng nhiều subquery scalar trong một SELECT để pivot horizontal — dùng cho báo cáo 1 dòng. Các conversion rate so từng stage với stage trước → thấy ngay stage nào leak nặng. Thường stage 'session → ordered' là leak to nhất (1-5% conversion là bình thường cho marketplace)."

### ⚠️ Common mistakes
- So theo top of funnel cho mọi stage (vd order/impression) → số bé tí, không actionable.

### 🚀 Extension
Cùng funnel nhưng split theo device_type — mobile vs web có leak khác nhau.

---

## G7 — Attribution: paid vs organic, AOV khác nhau?

**Level:** L3 | **Skill:** JOIN fact_traffic_session, segmentation | **Est:** 25 phút

### 💡 SQL
```sql
WITH ordered_sessions AS (
  SELECT DISTINCT ON (t.customer_id, t.date_key)
    t.customer_id, t.date_key, t.traffic_source
  FROM shopee.fact_traffic_session t
  WHERE t.has_order
  ORDER BY t.customer_id, t.date_key, t.pageviews DESC
)
SELECT
  s.traffic_source,
  COUNT(DISTINCT o.order_id)     AS orders,
  SUM(o.total_amount)            AS gmv,
  ROUND(AVG(o.total_amount), 0)  AS aov
FROM shopee.fact_orders o
JOIN ordered_sessions s
  ON s.customer_id = o.customer_id
 AND s.date_key = (
   SELECT date_key FROM shopee.dim_date
   WHERE full_date = o.created_at::date
 )
WHERE o.payment_status='paid'
GROUP BY s.traffic_source
ORDER BY gmv DESC;
```

### 🗣️ Cách giải thích
> "Attribution thực sự rất phức tạp (multi-touch, view-through...). Ở đây simplifiy: last session cùng ngày đặt đơn = source. `DISTINCT ON` lấy 1 session chính mỗi (customer, date) theo pageviews cao nhất. Cách này đủ cho quick insight."

### 🚀 Extension
Multi-touch attribution model (first-touch, last-touch, U-shape) — bài nâng cao.
