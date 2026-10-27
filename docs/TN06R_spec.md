# TN06-R — Hệ 2 tầng capitulation (bản dựng lại theo spec, đăng ký trước)

Code gốc `pipeline/18_daily_signals.py` không còn. Bản này dựng lại từ mô tả trong `06_EXPERIMENT_HISTORY.md`
(TN05: RSI<30 ≥3 phiên + vol ≥1,5× MA20 + regime; TN06: tầng chế độ thị trường → capitulation).
Mọi lựa chọn dưới đây **chốt trước khi chạy** (commit trước kết quả). Không chỉnh sau khi xem kết quả;
thay đổi = TN06-R2 với spec mới và dữ liệu forward mới.

## 1. Universe (giữ ledger engine)
Mã 3 ký tự, GTGD TB20 ≥ 5 tỷ, ≥ 200 phiên, volume > 0 (cột `eligible` của `vnq/features.py`).

## 2. Tầng 1 — chế độ thị trường (khi nào được mua)
BẬT khi VNINDEX đóng cửa ngày t > EMA200 của VNINDEX (dữ liệu ≤ t). TẮT → không mở vị thế mới.
Lý do: bắt đáy từng mã có kỳ vọng dương khi xu hướng dài hạn của thị trường còn lên; trong thị trường gấu,
"quá bán" thường quá bán thêm.

## 3. Tầng 2 — sự kiện capitulation (mua gì)
Tại ngày t, mã đủ điều kiện nếu:
- RSI14 (Wilder) < 30 ở cả 3 phiên t−2, t−1, t
- volume_t ≥ 1,5 × trung bình volume 20 phiên (`vol_ratio20`, gồm ngày t)
- Mã không có vị thế đang mở, và không phát sinh sự kiện trong 5 phiên trước (chống đếm trùng)

Không vào lệnh nếu open t+1 sát giá trần (không mua được ở giá hợp lý).

## 4. Lệnh và chi phí
Mua open t+1, bán close t+5 (5 phiên, như ledger). Nếu t+5 kẹt sàn → bán close t+6 (`realized()` của engine).
Phí 0,15%/chiều + thuế bán 0,1%.

## 5. Mua bao nhiêu
Danh mục 10 slot, mỗi slot = 10% giá trị danh mục tại ngày vào lệnh, tiền nhàn rỗi lãi 0.
Nếu nhiều sự kiện hơn slot trống: ưu tiên RSI14 thấp nhất, tối đa 3 mã/ngành đang giữ.

## 6. Mốc so sánh (cùng ngày vào, cùng 5 phiên, cùng chi phí)
- **Random**: cùng số mã, bốc ngẫu nhiên từ universe cùng ngày (500 lần)
- **Thị trường**: trung bình mọi mã trong universe (equal-weight)
- **VNINDEX**: close t → close t+5
- **Logic khác**: (L1) chỉ RSI14 < 30 (không cần 3 phiên + volume); (L2) capitulation không có tầng 1
- Danh mục: so với mua & giữ VNINDEX và mua & giữ equal-weight universe trong cùng kỳ

## 7. Giai đoạn
- IS: 2022-10-24 → 2026-06-30 (giai đoạn TN05/06 đã dùng để thiết kế) — chỉ để đối chiếu với số đã công bố
  (TN05 R2: hit 37,2%, +2,03%/sự kiện; TN06 BẬT: hit 39,3%, +3,04%/lệnh — định nghĩa hit/horizon gốc không rõ)
- **OOS: 2026-07-01 → ngày có nhãn cuối** (sau ngày TN06 được chốt 09/07/2026 gần như toàn bộ)

## 8. Tiêu chí GO (paper trading có tiền thật nhỏ)
Trên OOS, tất cả:
1. ≥ 30 lệnh
2. Excess TB/lệnh vs thị trường > 0 và CI95 (block bootstrap theo ngày, block 5) không chứa 0
3. Excess TB/lệnh vs random > 0
4. Thắng L1 (vs thị trường)
Không đạt → NO-GO; không đủ lệnh → "chưa đủ bằng chứng", tiếp tục paper trading forward.

## 9. Sửa đổi R1 (27/10/2026) — chỉ dựa trên IS, commit TRƯỚC khi mở OOS
Bản §2 (BẬT khi VNINDEX > EMA200) không tái lập số đã công bố trên IS (seed, 2022-10→2026-06):
−1,45%/lệnh, hit 40%. So sánh 6 định nghĩa tầng 1 trên IS (sự kiện capitulation, sau phí, 5 phiên):

| Tầng 1 BẬT khi | n | lãi/lệnh | hit | vs thị trường [CI95] | vs VNINDEX |
|---|---|---|---|---|---|
| A VNI > EMA200 (bản gốc §2) | 62 | −1,45% | 40% | −0,71% [−2,09; +1,09] | −1,35% |
| B VNI < EMA200 | 148 | +2,40% | 60% | +0,09% [−1,84; +1,76] | +1,00% |
| **C VNI < EMA50** | 162 | +2,68% | 61% | +0,71% [−0,72; +1,94] | +1,51% |
| D VNI giảm ≥10% từ đỉnh 60 phiên | 126 | +3,00% | 63% | +0,37% [−1,92; +2,32] | +1,29% |
| E breadth (tỷ lệ mã > EMA50) < 30% | 160 | +2,84% | 62% | +0,68% [−0,79; +1,96] | +1,53% |
| F không có tầng 1 | 207 | +1,28% | 55% | −0,11% | +0,33% |

B–E khớp số TN05/06 (+2–3%/lệnh, hit cao) ⇒ tầng 1 gốc nhiều khả năng là "thị trường đang điều chỉnh".
**Chọn C** (vs thị trường cao nhất, chỉ dùng VNINDEX). Lưu ý: chọn 1 trong 5 trên IS ⇒ IS lạc quan; chỉ OOS có giá trị kết luận.

Nhận xét: lãi chủ yếu đến từ **thời điểm** (cả thị trường hồi sau bán tháo), phần **chọn mã** (vs thị trường) nhỏ và CI chứa 0.
Vì vậy thêm phép đo **T1 — chỉ canh thời điểm**: mỗi ngày tầng 1 BẬT, mua đều toàn universe, giữ 5 phiên, sau phí.

Kết luận OOS tách 2 phần:
- **Chọn mã (GO TN06-R)**: giữ nguyên 4 tiêu chí §8.
- **Canh thời điểm (GO T1)**: ≥ 20 ngày BẬT, lãi TB/ngày-vào sau phí của T1 > 0 với CI95 không chứa 0, VÀ > lãi TB của mua đều mọi ngày (không canh) trong cùng OOS.

---
# TN06-R2 — thêm chốt lời sớm (đăng ký trước 27/10/2026, commit TRƯỚC khi chạy)
Giữ nguyên toàn bộ TN06-R (tầng 1 VNI < EMA50, sự kiện capitulation, vào open t+1, 10 slot, ≤3/ngành, ưu tiên RSI thấp,
phí 0,15%/chiều + thuế bán 0,1%). **Chỉ thêm luật thoát sớm:**
- Đặt lệnh bán giới hạn (LO) ở giá mục tiêu `P_tp = giá mua × (1 + TP)`.
- **Ràng buộc T+2:** cổ phiếu mua ở phiên t+1 chỉ bán được từ phiên t+3. Chốt lời chỉ được xét ở các phiên t+3, t+4, t+5.
- Khớp trong phiên d: nếu `open_d ≥ P_tp` → bán ở `open_d` (giá mở cửa đã vượt mục tiêu); ngược lại nếu `high_d ≥ P_tp` → bán ở `P_tp`.
- Không chạm mục tiêu → bán ATC t+5 như TN06-R (kẹt sàn t+5 → t+6).
- Lưới TP đăng ký trước: **{2%, 3%, 5%, 8%}**. Không có cắt lỗ (thay đổi khác = version khác).

**Chọn TP chỉ trên IS (2022-10-24 → 2026-06-30)**, luật chọn cố định: TP có lãi TB/lệnh sau phí cao nhất,
và phải cao hơn TN06-R không chốt lời trên IS; không TP nào hơn → TN06-R2 = không đổi, dừng.
**OOS 2026-07-01 → ngày có nhãn cuối** chấm một lần với TP đã chọn, so với: TN06-R gốc, thị trường (EW), random, VNINDEX.
Lưu ý: OOS này đã được dùng để chấm TN06-R (cùng luật vào lệnh), nên chỉ là bằng chứng bổ sung; bằng chứng sạch = paper trading live.
GO cho paper trading thay TN06-R khi trên OOS: ≥ 30 lệnh, lãi TB/lệnh > TN06-R, và vs thị trường > 0.
