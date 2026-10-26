# TN07 — LightGBM dự báo trend 5 phiên (y_bin ATR) — Biên bản kiểm định

Ngày chạy: 2026-10-26 · Dữ liệu: `panel.parquet` (đến 2026-07-10), `vnindex.parquet` (đến 2026-07-09) · Config: `out/config_final.json`

## 1. Cấu hình (theo ledger)
| Hạng mục | Giá trị | Trạng thái |
|---|---|---|
| Label | `y_bin = 1` nếu `close[t+5]/open[t+1] − 1 > 0.5 × ATR14%_t` | chốt |
| Train / Test | 2025-01-01 → 2026-06-30 (purge còn 2026-06-23) / 2026-07-01 → 2026-07-10 | chốt |
| Universe | cổ phiếu 3 ký tự (loại CW), GTGD khớp TB20 ≥ 5 tỷ, ≥ 200 phiên lịch sử | ngưỡng 5 tỷ CHƯA XÁC NHẬN |
| Lọc value | top 30% `value_score`, `value_mode = technical_proxy` (drawdown 252, dưới EMA200, volat60 thấp, thanh khoản) | không có dữ liệu cơ bản |
| Chọn mã | top 10 `p_up_5`, tối đa 3 mã/ngành | chốt |
| Chi phí | phí 0.15%/chiều (GIẢ ĐỊNH) + thuế bán 0.1% | phí CHƯA XÁC NHẬN |
| Trần/sàn | bỏ lệnh nếu open t+1 kịch trần; kẹt sàn t+5 thì exit close t+6 | sàn suy luận từ biên độ, KHÔNG chính xác |
| Mô hình | LightGBM; baseline logistic (C=0.1), momentum20, random trong pool | |
| Feature | 36 feature: EMA20/50/200, ADX/DI, RSI, MACD, ATR%, volatility, volume, vị trí giá 20/60/252, cấu trúc đỉnh đáy 10 phiên, VNI ret/EMA50, breadth, rank cross-section | |

## 2. Chọn siêu tham số (walk-forward 4 fold, expanding, purge 5 phiên) — mọi config đã thử
IC daily (Spearman `p` vs `fwd_ret_5`, toàn universe):

| Config | F1 Q3/25 | F2 Q4/25 | F3 Q1/26 | F4 Q2/26 | TB |
|---|---|---|---|---|---|
| lgb0 leaves15 lr.03 n300 mcs200 | 0.011 | −0.025 | 0.102 | 0.049 | 0.034 |
| lgb1 leaves31 lr.03 n300 mcs200 | −0.005 | −0.024 | 0.101 | 0.042 | 0.029 |
| **lgb2 leaves15 lr.02 n600 mcs400 (chọn)** | 0.015 | −0.000 | 0.110 | 0.044 | **0.042** |
| lgb3 leaves7 lr.03 n400 mcs300 | 0.012 | −0.004 | 0.086 | 0.050 | 0.036 |
| logreg C=0.1 | 0.023 | −0.010 | −0.004 | 0.054 | 0.016 |

## 3. Kết quả
### 3a. Tập TEST (đúng ledger) — KHÔNG ĐÁNH GIÁ ĐƯỢC
Chỉ 3 ngày có nhãn (01–03/07/2026) do dữ liệu dừng ở 10/07. Không bootstrap được. Số liệu chỉ để tham khảo: LightGBM hit 16.7% vs base pool 7.8%, net −2.34%/5 phiên, excess vs universe −0.38%.

### 3b. Walk-forward OOS 2025-07 → 2026-06 (229 ngày, bằng chứng phụ — đã dùng để chọn config nên lạc quan nhẹ)
| Chiến lược | Hit top10 | Lift vs pool | Net top10/5p | Excess net vs universe [CI95] | IC universe [CI95] | IC trong pool [CI95] | Decile spread [CI95] |
|---|---|---|---|---|---|---|---|
| LightGBM | 32.9% | +0.9 đđ | −0.21% | −0.12% [−0.44; +0.19] | 0.040 [0.008; 0.067] | 0.025 [−0.019; 0.064] | +0.82% [0.28; 1.30] |
| Logistic | 30.7% | −1.2 đđ | −0.49% | −0.40% [−0.66; −0.16] | 0.016 [−0.017; 0.044] | 0.003 | +0.18% |
| Momentum20 | 33.8% | +1.9 đđ | −0.27% | −0.18% [−0.45; +0.18] | −0.043 | −0.003 | −0.35% |
| Random(pool) | 31.2% | −0.7 đđ | −0.37% | −0.28% [−0.50; −0.05] | −0.002 | −0.004 | −0.02% |

Base rate y_bin trong pool: 32.0%. Universe TB fwd_ret_5: −0.09%/5 phiên. Bootstrap block 5 ngày, 2000 lần.

Calibration (OOS): không đơn điệu — p 0.0–0.5 đều ra thực tế ~30%, chỉ nhóm p > 0.6 lên 46.5% (n=2,030).

## 4. Đối chiếu điều kiện mục 6
| Điều kiện | Kết quả |
|---|---|
| excess_ret_5 > 0 sau chi phí trên test | ❌ test 3 ngày; OOS −0.12%, CI chứa 0 |
| IC_daily > 0, CI không chứa 0 | ⚠️ universe: đạt (OOS); trong value pool: CI chứa 0 |
| lift > 0, calibration đơn điệu | ⚠️ lift +0.9 đđ; ❌ calibration không đơn điệu |

**Kết luận: CHƯA ĐỦ BẰNG CHỨNG.** LightGBM có tín hiệu xếp hạng yếu nhưng có thật trên toàn universe (IC 0.04, decile spread +0.8%/5 phiên trước phí), vượt logistic, nhưng không còn ý nghĩa sau khi đi qua lọc value 30% + top10 + chi phí 0.4%. Mọi output hiện tại chỉ ở mức "theo dõi".

## 5. Quan sát
- 4 feature thị trường (breadth, VNI) chiếm gain lớn nhất → mô hình chủ yếu học "ngày nào thị trường tốt", làm p dao động theo ngày mà không phân biệt mã → giải thích calibration kém.
- `value_score` technical_proxy kéo pool về nhóm drawdown/dưới EMA200: ngày 10/07, 21/40 mã pool ở Downtrend, 0 Uptrend → trend và ML mâu thuẫn mang tính cấu trúc.
- Fold 2 (Q4/2025) IC ≈ 0, fold 3 (Q1/2026) IC 0.11 → tín hiệu không ổn định theo giai đoạn.
- Suy luận sàn sai với một số mã (VSC, VIX ra HNX) do giá điều chỉnh → cần danh sách sàn thật.

## 6. Đề xuất TN08 (đăng ký trước, chưa chạy)
1. Cập nhật dữ liệu đến 23/10/2026 → test ~75 ngày, chạy lại đúng config này (không đổi) để có kết luận test thật.
2. Biến thể đăng ký trước: (a) target cross-sectional (y = fwd_ret_5 thuộc top 30% trong ngày) hoặc bỏ feature thị trường; (b) đổi thứ tự: ML trên toàn universe rồi value làm ràng buộc mềm. Đánh giá bằng walk-forward trong train, chọn 1 trước khi mở test.
