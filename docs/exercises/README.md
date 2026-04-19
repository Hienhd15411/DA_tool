# Bộ bài tập SQL — Shopee-like dataset

Ngân hàng ~90 bài tập SQL thực chiến cho học viên DA, tập trung **case study thực tế** thay vì syntax drill. Dataset: [schema.md](../schema.md).

## Nguyên tắc thiết kế

1. **Business-first**: mỗi bài bắt đầu bằng câu hỏi biz, không phải "viết truy vấn dùng JOIN X Y".
2. **Đáp án giàu ngữ cảnh**: giải thích vì sao làm vậy, common mistake, extension nâng cao.
3. **4 level**:
   - **L1** — Basic (SELECT, WHERE, GROUP BY, ORDER, LIMIT)
   - **L2** — Intermediate (JOIN, CASE, ratio, date functions)
   - **L3** — Advanced (window, CTE, subquery, self-join)
   - **L4** — Case study mở (phân tích nhiều chiều, insight + recommendation)

## Mục lục theo chủ đề

| Chủ đề | File | Số bài | Điểm nhấn |
|---|---|---|---|
| A. Revenue / GMV trending | [A-revenue-gmv.md](A-revenue-gmv.md) | 8 | Trend, decomposition, anomaly |
| B. Customer lifecycle | [B-customer-lifecycle.md](B-customer-lifecycle.md) | 9 | RFM, cohort, retention, churn |
| C. Campaign / Sale day | [C-campaign-sale-day.md](C-campaign-sale-day.md) | 10 | 3/3, 4/4, 5/5 Mega Sale |
| D. Voucher & Promotion | [D-voucher-promotion.md](D-voucher-promotion.md) | 7 | Stacking, cannibalization |
| E. Seller performance | [E-seller-performance.md](E-seller-performance.md) | 7 | Pareto, risk audit |
| F. Product & Category (4-level) | [F-product-category.md](F-product-category.md) | 8 | Recursive CTE, slow mover |
| G. Marketing / Ads | [G-marketing-ads.md](G-marketing-ads.md) | 7 | ROAS, funnel, attribution |
| H. Ops / Shipping SLA | [H-operations-shipping.md](H-operations-shipping.md) | 7 | Carrier benchmark, stockout |
| I. Cancellation / Return | [I-cancellation-return.md](I-cancellation-return.md) | 6 | COD abuse, time-to-cancel |
| J. Customer service | [J-customer-service.md](J-customer-service.md) | 5 | Ticket volume, SLA |
| K. Geographic | [K-geographic.md](K-geographic.md) | 5 | Province trend, potential market |
| L. Capstone (open-ended) | [L-capstone.md](L-capstone.md) | 8 | Mini-project, CEO report |

**Total: 87 bài.**

## Cấu trúc mỗi bài

```
### X.N — Tên bài

Level:    L1/L2/L3/L4
Skill:    (tags SQL)
Est:      thời gian dự kiến

🎯 Business context       — tại sao phải trả lời câu hỏi này
🧭 Approach               — tư duy từng bước trước khi viết SQL
💡 SQL solution           — truy vấn mẫu (PostgreSQL 15+)
✅ Expected result        — shape + sample rows
🗣️ Cách giải thích        — script giảng cho học viên nghe là hiểu
⚠️ Common mistakes        — lỗi phổ biến, cách tránh
🚀 Extension              — biến thể khó hơn cho học viên giỏi
```

## Tips cho giảng viên

- **Dạy theo chủ đề** không phải theo level. Lấy 1 bài L1 + 1 L2 + 1 L3 + 1 L4 cùng chủ đề C (campaign) cho học viên thấy tiến trình từ đơn giản → insight thật.
- **Kèm dữ liệu thật hiển thị**: chạy query mẫu trước, in kết quả lên slide, rồi mới chỉ SQL. Học viên DA cần thấy "ra cái gì" trước khi hiểu "viết ra sao".
- **L4 case study**: cho học viên làm cặp đôi, present insight 5 phút — rèn kỹ năng kể chuyện data.
- **Common mistakes** là vàng: so sánh query lỗi vs đúng thường dạy hiệu quả hơn giảng lý thuyết.

## Liên kết

- Schema: [../schema.md](../schema.md)
- Thứ tự đề xuất dạy: A → F → B → C → D → G → E → H → I → J → K → L
