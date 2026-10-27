# 09 — Thí nghiệm 4 danh mục (paper trading, 100 triệu mỗi danh mục, từ phiên 28/10/2026)

Đăng ký trước 27/10/2026. Tiền **giả định**, không đặt lệnh thật. Mục tiêu: xem agent trader (dùng dữ liệu hệ thống + tin
tức) có hơn luật máy móc, thị trường và bốc thăm hay không. Kết luận chỉ sau ≥ 3 tháng / ≥ 100 lệnh.

## Danh mục
| | Tên | Quyết định |
|---|---|---|
| A | Agent trader | Agent Claude mỗi tối đọc dữ liệu hệ thống (bản tin thị trường, TN07, TN06-R, danh mục) + tin CafeF/VnExpress → ghi sổ lệnh cho phiên sau |
| B | Luật TN06-R | Tín hiệu TN06-R từ ngày dữ liệu 27/10: mua ATO phiên sau 10% NAV, bán ATC sau 5 phiên tính từ tín hiệu, ≤10 mã, ≤3/ngành |
| C | VNINDEX | Mua & giữ chỉ số (như ETF không phí quản lý) từ giá mở cửa 28/10 |
| D | Ngẫu nhiên | Mỗi lệnh mua của A → mua 1 mã **ngẫu nhiên** trong universe cùng số tiền, cùng phiên; A bán mã đó → D bán mã tương ứng cùng phiên, cùng tỷ lệ |

## Luật khớp lệnh (giống nhau cho mọi danh mục)
- Giá theo nến ngày (VCI, đã chốt; không dùng nến chưa đóng). Đơn vị giá nghìn đồng; lô 100 cổ phiếu.
- Loại lệnh: `ATO` (khớp giá mở cửa), `ATC` (khớp giá đóng cửa), `LO` có giá (mua: mở cửa ≤ giá → khớp giá mở cửa, ngược lại thấp nhất ≤ giá → khớp đúng giá; bán ngược lại). Lệnh chỉ có hiệu lực trong phiên.
- **Trần/sàn**: mua không khớp nếu giá khớp ≥ trần − 0,5%; bán không khớp nếu giá khớp ≤ sàn + 0,5% (biên độ HOSE 7%, HNX 10%, UPCOM 15%, suy từ dữ liệu).
- **T+2**: cổ phiếu mua phiên T bán được bằng ATC/LO từ phiên T+2, bằng ATO từ phiên T+3.
- Phí 0,15% mỗi chiều, thuế bán 0,1%. Tiền bán dùng được ngay (giả định ứng trước tiền bán, bỏ qua phí ứng).
- Không margin, không bán khống. Thứ tự trong phiên: bán ATO → mua ATO → LO → bán ATC → mua ATC.
- NAV = tiền mặt + giá trị thanh lý (đóng cửa × số lượng × (1 − phí − thuế)). Lời/lỗ báo theo NAV.

## Ràng buộc riêng cho A (bộ mô phỏng tự chặn, lệnh vi phạm bị từ chối và ghi log)
- Chỉ mã trong universe đủ điều kiện (thanh khoản TB20 ≥ 5 tỷ, ≥ 200 phiên).
- Một mã ≤ 20% NAV sau khi mua; ≤ 3 mã cùng ngành; luôn giữ ≥ 10% NAV tiền mặt (lệnh mua bị cắt bớt cho vừa).
- **Sổ lệnh phải được commit vào `trader/orders/<phiên>.json` trước 09:00 của phiên đó** (giờ commit là bằng chứng không biết trước giá).
  File commit sau 09:00 phiên đó → bị bỏ qua cả file.
- Mỗi lệnh có `reason` (lý do) và `sources` (dữ liệu/tin dùng). Không sửa lệnh đã commit.
- Agent tự đặt quy tắc cắt lỗ/chốt lời của mình nhưng phải ghi trong sổ lệnh và thực hiện bằng lệnh của phiên sau (không có lệnh dừng tự động).

## Kế hoạch giao dịch của A (bắt buộc mỗi tối — đây là phần chính của báo cáo)
- **Mỗi lệnh BUY** có: `limit` (vùng giá vào, LO) hoặc ATO kèm lý do; `stop_loss` (giá cắt lỗ); `take_profit` (giá chốt lời);
  `horizon_sessions` (số phiên dự kiến giữ); `confidence` (`thấp`/`vừa`/`cao`); `reason`; `sources`.
- **Cỡ lệnh theo rủi ro:** `value_vnd ≈ min(20% NAV, 2% NAV ÷ (giá vào − stop_loss)/giá vào)` — chạm cắt lỗ thì mất ≈ 2% NAV.
- **Mỗi mã đang giữ** có một dòng `HOLD` (giữ, kèm `stop_loss`/`take_profit` hiện hành) hoặc `SELL` (bán, kèm lý do).
  Giá đóng cửa ≤ `stop_loss` hoặc ≥ `take_profit` đã cam kết → tối đó phải đặt lệnh SELL (kỷ luật, không dời cắt lỗ xuống).
- **Theo dõi:** dòng `WATCH` cho mã chưa vào, kèm `condition` (điều kiện cụ thể để vào lệnh).
`HOLD`/`WATCH` không phải lệnh, bộ mô phỏng chỉ ghi lại để hiển thị và đối chiếu kỷ luật.

## Định dạng sổ lệnh A
```json
{"for_session": "2026-10-28", "decided_at": "2026-10-27T19:40+07:00",
 "market_view": "…", "risk_plan": "…",
 "orders": [
   {"side": "BUY", "ticker": "FPT", "type": "LO", "limit": 95.0, "value_vnd": 15000000, "stop_loss": 89.5, "take_profit": 105.0,
    "horizon_sessions": 10, "confidence": "vừa", "reason": "…", "sources": ["…"]},
   {"side": "SELL", "ticker": "SBT", "type": "ATC", "qty": "all", "reason": "chạm cắt lỗ 19.8", "sources": ["…"]},
   {"side": "HOLD", "ticker": "HPG", "stop_loss": 25.0, "take_profit": 30.0, "reason": "…"},
   {"side": "WATCH", "ticker": "MWG", "condition": "vượt 68 với khối lượng ≥ 1,5× TB20", "reason": "…"}
 ]}
```
`qty` khi bán: `"all"` hoặc số cổ phiếu. Không có lệnh → `"orders": []` (vẫn commit để ghi nhận quyết định đứng ngoài).

## Báo cáo mỗi tối
NAV, lời/lỗ hôm nay và lũy kế của A/B/C/D; lệnh đã khớp / không khớp và lý do; vị thế đang giữ; sổ lệnh của A cho phiên tới kèm lý do;
tin tức đã đọc. Dashboard mục "Thi đấu 4 danh mục".
