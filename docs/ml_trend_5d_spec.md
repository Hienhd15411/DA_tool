# Spec: Metrics + ML dự báo trend 5 ngày cho cổ phiếu VN (daily)

## 0. Mục tiêu

Mỗi ngày sau khi đóng cửa, hệ thống:
1. Tính bộ metrics core cho toàn bộ universe.
2. Lọc và chấm điểm theo tiêu chí **value** để chọn ra **10 mã**.
3. Dùng ML để dự báo xác suất trend **UP trong 5 ngày tới** cho từng mã.
4. Xếp hạng 10 mã theo xác suất và xuất danh sách kèm metric giải thích.

Thành công được đo bằng: lợi suất 5 ngày của rổ 10 mã có vượt benchmark (VN-Index, và trung bình universe) trên tập test không, sau chi phí.

---

## 1. Dữ liệu đầu vào

### 1.1 Bảng giá daily (bắt buộc)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| `symbol` | string | Mã cổ phiếu, ví dụ `VNM` |
| `date` | date | Ngày giao dịch |
| `open`, `high`, `low`, `close` | float | **Đã điều chỉnh quyền** (cổ tức, phát hành thêm) |
| `volume` | float | Khối lượng khớp |
| `value` | float | Giá trị giao dịch (VND). Nếu không có, tính `close × volume` |
| `ceiling`, `floor` | float | Giá trần/sàn ngày đó (nếu có) |

Nếu không có `ceiling`/`floor`, suy ra từ `close[t−1]` với biên độ ±7% (HOSE) hoặc ±10% (HNX, UPCoM).

### 1.2 Chỉ số thị trường (bắt buộc)

VN-Index daily: `date`, `open`, `high`, `low`, `close`, `volume`.

### 1.3 Dữ liệu cơ bản (tùy chọn, dùng cho value)

Theo quý, forward-fill sang daily theo **ngày công bố báo cáo**, không theo kỳ báo cáo:

| Cột | Ý nghĩa |
|---|---|
| `pe_ttm`, `pb`, `ev_ebitda` | Định giá |
| `roe`, `roa`, `gross_margin` | Chất lượng |
| `debt_equity` | Đòn bẩy |
| `div_yield` | Lợi suất cổ tức |
| `eps_growth_yoy`, `revenue_growth_yoy` | Tăng trưởng |

> **Quy tắc quan trọng:** dữ liệu báo cáo chỉ được dùng từ ngày công bố trở đi. Dùng ngày kỳ báo cáo là look-ahead bias.

Nếu không có dữ liệu cơ bản, dùng **proxy kỹ thuật cho value** (mục 3.2) và ghi cờ `value_mode = technical_proxy` trong output.

---

## 2. Phạm vi thời gian và tách tập

| Tập | Khoảng ngày | Dùng để |
|---|---|---|
| Warm-up | Trước 2025-01-01 | Tính chỉ báo rolling (EMA200, z-score 250 ngày). Không dùng để train |
| **Train** | 2025-01-01 → 2026-06-30 | Fit mô hình, chọn tham số, chọn trọng số |
| **Test** | 2026-07-01 → ngày mới nhất | Đánh giá một lần, không được chỉnh tham số sau khi thấy kết quả test |

Quy tắc:
- Không dùng dữ liệu test để chọn feature, ngưỡng hay siêu tham số.
- Nếu cần chỉnh, chia train thành các fold theo thời gian (mục 7.2) và chỉ đánh giá lại trên test một lần cuối.
- Test chỉ khoảng 4 tháng, nên kết quả có độ bất định lớn. Báo cáo kèm khoảng tin cậy (bootstrap theo ngày).

---

## 3. Feature engineering

Tất cả tính tại close ngày `t`, chỉ dùng dữ liệu đến `t`.

### 3.1 Nhóm kỹ thuật (trend, momentum, volatility, volume)

| Feature | Công thức |
|---|---|
| `ema_gap_20_50` | (EMA20 − EMA50) / close |
| `ema200_pos` | close / EMA200 − 1 |
| `ema20_slope_5` | (EMA20_t − EMA20_{t−5}) / EMA20_{t−5} |
| `adx14` | ADX Wilder 14 |
| `roc_5`, `roc_10`, `roc_20` | close_t / close_{t−n} − 1 |
| `rsi14` | RSI Wilder 14 |
| `macd_hist` | MACD(12,26,9) histogram / close |
| `atr14_pct` | ATR14 / close (ATR Wilder) |
| `rv_20` | std(log return, 20) × √252 |
| `bb_width_20` | (BB_upper − BB_lower) / BB_mid, độ lệch chuẩn 2 |
| `vol_ratio_20` | volume / mean(volume, 20) |
| `value_ratio_20` | value / mean(value, 20) |
| `obv_slope_10` | hệ số hồi quy OBV trên 10 ngày, chia cho mean(volume, 20) |
| `range_pos_20` | (close − low20) / (high20 − low20) |
| `dist_high_20` | close / high20 − 1 |
| `hh_hl_score_10` | (số swing high tăng + số swing low tăng) − (số giảm), swing N=3, trong 10 ngày |
| `gap_open_pct` | open_t / close_{t−1} − 1 |
| `ret_1d` | close_t / close_{t−1} − 1 |

### 3.2 Nhóm value

**Có dữ liệu cơ bản:**

| Feature | Công thức | Hướng tốt |
|---|---|---|
| `pe_rank` | percentile của `pe_ttm` trong cross-section ngày t | thấp |
| `pb_rank` | percentile của `pb` | thấp |
| `roe_rank` | percentile của `roe` | cao |
| `debt_rank` | percentile của `debt_equity` | thấp |
| `growth_rank` | percentile của `eps_growth_yoy` | cao |
| `div_rank` | percentile của `div_yield` | cao |

Chuyển thành `value_score_fund` = trung bình có trọng số của các rank (chiều đã đổi dấu), trọng số bằng nhau ở phiên bản đầu.

**Không có dữ liệu cơ bản (proxy kỹ thuật):**

| Feature | Công thức | Ý nghĩa |
|---|---|---|
| `dist_from_ema200_rank` | rank của `ema200_pos` (thấp = rẻ) | Giá thấp so với trung bình dài hạn |
| `drawdown_252` | close / max(close, 252) − 1 | Mức giảm từ đỉnh 1 năm |
| `low_vol_rank` | rank của `rv_20` (thấp = tốt) | Biến động thấp |
| `liquidity_rank` | rank của mean(value, 20) | Thanh khoản đủ để giao dịch |

`value_score_tech` = trung bình rank của bốn feature trên, đảo chiều khi cần.

Tất cả rank tính **cross-sectional theo ngày**, không theo toàn bộ lịch sử, để tránh trộn giai đoạn.

### 3.3 Chuẩn hóa

- Rolling z-score 250 ngày cho từng feature kỹ thuật theo mã.
- Winsorize tại percentile 1% và 99% (theo cross-section ngày) để giảm ảnh hưởng ngoại lệ.
- Các feature có thể tính dựa trên giá trị tương lai (ví dụ mean toàn bộ train) **không được dùng**. Mọi scaler fit trên train và áp dụng cho test.

### 3.4 Cờ điều kiện

| Cờ | Điều kiện | Xử lý |
|---|---|---|
| `is_ceiling` | close = ceiling | Đánh dấu. Không loại khỏi feature, nhưng loại khỏi tập train label nếu ngày t+1..t+5 có trần/sàn liên tiếp |
| `is_floor` | close = floor | Như trên |
| `is_illiquid` | mean(value, 20) < ngưỡng (đề xuất 5 tỷ VND/ngày) | Loại khỏi universe ngày đó |
| `is_suspended` | Không có giao dịch | Loại |

---

## 4. Target (label)

Với horizon `h = 5` ngày giao dịch:

- `fwd_ret_5 = adj_close[t+5] / adj_close[t+1] − 1`

Lưu ý: entry giả định là **open ngày t+1**, nên mẫu số nên là `open[t+1]`, không phải `close[t]`. Đây là quy ước chính:

- `fwd_ret_5 = close[t+5] / open[t+1] − 1`

Phân lớp:

- `y_bin = 1` nếu `fwd_ret_5 > thr_t`, ngược lại `0`
- `thr_t = 0.5 × atr14_pct_t` (ngưỡng theo biến động)

Tùy chọn phụ: `y_reg = fwd_ret_5` (dùng để ranking, xem mục 6).

Loại bỏ các mẫu có `t+5` vượt quá ngày dữ liệu mới nhất.

---

## 5. Xây dựng dataset

Mỗi dòng là một cặp `(symbol, date)`.

### 5.1 Lọc universe mỗi ngày

Chỉ giữ dòng nếu:
- Không `is_illiquid`, không `is_suspended`
- Đã có đủ lịch sử cho feature (tối thiểu 252 ngày, hoặc 200 nếu bỏ EMA200)

### 5.2 Ghi file

- Định dạng: Parquet, partition theo `year`
- Tên file: `features_daily_{YYYY}.parquet`
- Các cột: `symbol`, `date`, toàn bộ feature, `y_bin`, `fwd_ret_5`, `value_mode`, cờ điều kiện

### 5.3 Kiểm tra dữ liệu (chạy trước mọi train)

- Số dòng mỗi ngày theo universe (cảnh báo nếu giảm mạnh)
- Tỷ lệ NaN từng feature (cảnh báo nếu > 5%)
- Không có `date` trùng trong cùng `symbol`
- Phân phối `y_bin`: cảnh báo nếu một lớp chiếm > 70%
- Kiểm tra look-ahead: với mỗi feature, xác nhận giá trị tại `t` không đổi khi thêm dữ liệu sau `t`

---

## 6. Mô hình ML

### 6.1 Mô hình

Thứ tự triển khai, từ đơn giản đến phức tạp:

1. **Baseline:** logistic regression có chuẩn hóa. Hiểu được hệ số, dễ debug.
2. **Chính:** LightGBM (classification cho `y_bin`). Mặc định:
   - `num_leaves = 15`, `min_data_in_leaf = 200`, `learning_rate = 0.03`
   - `feature_fraction = 0.7`, `bagging_fraction = 0.7`, `bagging_freq = 1`
   - Số vòng cây chọn bằng early stopping trên fold validation cuối của train
3. **Đối chứng (tùy chọn):** LightGBM hồi quy trên `fwd_ret_5` để xếp hạng.

Không dùng mạng sâu ở phiên bản đầu. Dữ liệu ít và nhiễu, mô hình đơn giản thường ổn định hơn.

### 6.2 Đầu ra

Mỗi ngày, mỗi mã:
- `p_up_5` = xác suất `y_bin = 1`
- `rank_score` = rank cross-section của `p_up_5` trong universe ngày đó

### 6.3 Kết hợp value và ML để chọn 10 mã

Quy trình chọn mỗi ngày:

1. Lọc universe (mục 5.1).
2. Tính `value_score` = `value_score_fund` nếu có, ngược lại `value_score_tech`.
3. Lấy top 30% theo `value_score` (nhóm value). Đây là **bước sàng lọc**, không phải bước xếp hạng.
4. Trong nhóm value, xếp hạng theo `p_up_5` và chọn **top 10**.
5. Ràng buộc đa dạng: không quá 3 mã cùng ngành (nếu có dữ liệu ngành). Nếu vi phạm, lấy mã tiếp theo.
6. Ghi danh sách 10 mã, kèm `p_up_5`, `value_score`, `trend_score`, các cờ.

Lý do chọn quy trình này: value lọc những mã có nền tảng, ML chọn thời điểm trong nhóm đó. Bạn có thể đổi thứ tự nếu muốn ML đi trước.

---

## 7. Đánh giá

### 7.1 Metric chính (trên tập test)

Với mỗi ngày trong test, rổ 10 mã được mua tại open t+1 và giữ 5 ngày:

| Metric | Định nghĩa |
|---|---|
| `basket_ret_5` | trung bình `fwd_ret_5` của 10 mã được chọn |
| `excess_ret_5` | `basket_ret_5` − trung bình `fwd_ret_5` của toàn universe ngày đó |
| `hit_rate_5` | tỷ lệ mã trong rổ có `y_bin = 1` |
| `lift` | `hit_rate_5` − tỷ lệ `y_bin = 1` của universe |
| `IC_daily` | Spearman(`p_up_5`, `fwd_ret_5`) theo cross-section mỗi ngày; báo cáo trung bình và tỷ lệ ngày IC > 0 |
| `decile_spread` | trung bình `fwd_ret_5` nhóm top 10% `p_up_5` − nhóm bottom 10% |
| `calibration` | 5 bucket `p_up_5`, so tỷ lệ `y_bin = 1` thực tế với xác suất dự báo trung bình |
| `max_drawdown` | của đường cộng dồn `basket_ret_5` theo ngày (chồng lấp giữ 5 ngày, tính theo lịch giữ lệnh) |

### 7.2 Walk-forward trong train

Chia train thành 4 fold theo thời gian, mỗi fold: train mở rộng, validation 2 tháng kế tiếp.

- Fold 1: train 2025-01 → 2025-06, val 2025-07 → 2025-08
- Fold 2: train 2025-01 → 2025-08, val 2025-09 → 2025-10
- Fold 3: train 2025-01 → 2025-10, val 2025-11 → 2025-12
- Fold 4: train 2025-01 → 2025-12, val 2026-01 → 2026-02

Mục đích: chọn số vòng cây, threshold `thr_t`, và trọng số value/ML. Không dùng tập test ở bước này.

### 7.3 Đánh giá cuối trên test

- Fit một lần trên toàn bộ train (2025-01 → 2026-06), với tham số đã chốt ở 7.2.
- Áp dụng lên test (2026-07 → mới nhất), không refit.
- Báo cáo kết quả 7.1 kèm bootstrap 1.000 lần theo ngày, lấy khoảng 95% cho `excess_ret_5` và `IC_daily`.

### 7.4 Chi phí

Trừ mỗi lệnh chu kỳ: phí môi giới 2 chiều + thuế bán 0.1%. Mức phí cụ thể cần xác nhận với công ty chứng khoán của bạn. Báo cáo cả kết quả trước và sau chi phí.

### 7.5 Tiêu chí chấp nhận

Chỉ coi là có tín hiệu khi **đồng thời**:
- `excess_ret_5 > 0` sau chi phí trên test
- `IC_daily` trung bình > 0 và khoảng bootstrap không chứa 0
- `lift > 0` và `calibration` đơn điệu (bucket cao hơn có tỷ lệ UP cao hơn)
- `max_drawdown` nằm trong ngưỡng chấp nhận được (ví dụ > −15%, để thảo luận)

Nếu không đạt, không tinh chỉnh trên test. Quay lại train và ghi nhận kết quả thất bại.

---

## 8. Output hằng ngày

File `daily_picks_{YYYY-MM-DD}.csv`:

| Cột | Ý nghĩa |
|---|---|
| `date` | Ngày tính tín hiệu (cuối phiên) |
| `rank` | 1..10 |
| `symbol` | Mã |
| `p_up_5` | Xác suất UP 5 ngày |
| `value_score` | Điểm value |
| `value_mode` | `fund` hoặc `technical_proxy` |
| `trend_score` | Điểm xu hướng kỹ thuật |
| `regime` | Uptrend / Downtrend / Sideways |
| `close` | Giá đóng cửa ngày t |
| `entry_ref` | Giá tham chiếu cho lệnh t+1 (open) |
| `is_ceiling`, `is_floor` | Cờ |
| `warning` | Rỗng hoặc mô tả (ví dụ: trend giảm nhưng p_up cao) |

Kèm một dòng tổng hợp đầu file: số mã đủ điều kiện, số mã vào sàng lọc value, phân phối regime của 10 mã.

Ngày sau đó, điền `fwd_ret_5` thực tế cho các picks đã đủ 5 ngày, để theo dõi metric live.

---

## 9. Cấu trúc code đề xuất

```
stock_trend/
├── config.yaml          # tham số: horizon, thresholds, ngày train/test, phí
├── data/                # dữ liệu gốc (không sửa)
├── features/
│   ├── technical.py     # mục 3.1
│   ├── value.py         # mục 3.2
│   └── labels.py        # mục 4
├── dataset.py           # mục 5, kiểm tra dữ liệu
├── model.py             # mục 6
├── select.py            # mục 6.3, chọn 10 mã
├── evaluate.py          # mục 7
└── daily_run.py         # chạy cuối phiên, xuất output mục 8
```

Mọi tham số đặt trong `config.yaml`, không hardcode. Mỗi lần chạy ghi lại hash của config và phiên bản dữ liệu vào output.

---

## 10. Rủi ro và giới hạn đã biết

- **Lợi thế nhỏ:** dự báo 5 ngày từ dữ liệu công khai thường có lợi thế thấp. Mong đợi kết quả trung tính là bình thường.
- **Test ngắn:** khoảng 4 tháng, dễ bị ảnh hưởng bởi một giai đoạn thị trường đặc biệt. Đọc kết quả cùng với regime thị trường trong test.
- **Chế độ thị trường:** nếu VN-Index đi ngang hoặc giảm mạnh trong test, các tín hiệu trend có thể thất bại đồng loạt. Nên báo cáo kết quả theo regime của VN-Index.
- **Thanh khoản và thao túng:** mã thanh khoản thấp dễ cho tín hiệu giả. Lọc theo `is_illiquid` là bắt buộc.
- **Biên độ và T+2.5:** một số lệnh không thể thoát đúng ngày dự kiến. Mô phỏng hiện tại giả định thoát tại close t+5 nếu không bị trần/sàn chặn. Cần ghi thêm trường hợp bị kẹt.
- **Dữ liệu cơ bản:** dùng ngày công bố, không dùng ngày kỳ báo cáo. Nếu không có ngày công bố, value chỉ dùng proxy kỹ thuật.
- **Overfitting:** mỗi lần thử thêm feature hoặc tham số đều làm tăng nguy cơ. Ghi lại số cấu hình đã thử.

---

## 11. Checklist trước khi chạy

- [ ] Dữ liệu giá đã điều chỉnh quyền
- [ ] Có `value` hoặc đã tính được từ volume × close
- [ ] Có ceiling/floor hoặc đã suy ra
- [ ] Đã xác định nguồn và ngày công bố của dữ liệu cơ bản (nếu dùng)
- [ ] Đã chốt danh sách universe (ví dụ VN30 hay rộng hơn)
- [ ] Đã chốt phí và thuế
- [ ] Test không được dùng để chọn tham số
- [ ] Output có cột `value_mode` và `warning`

---

## 12. Khớp spec với dữ liệu hiện có trong Supabase

Dataset hiện tại (sau pivot vnstock):

| Cần | Có? | Cách xử lý |
|---|---|---|
| OHLCV đã điều chỉnh | ✅ `stock.fact_price_daily` close đã adjusted | Dùng trực tiếp |
| Volume + value | ✅ `volume`, `trade_value` | Dùng trực tiếp |
| VN-Index daily | ❌ Chưa có | Sẽ fetch bổ sung bằng vnstock symbol `VNINDEX` |
| Ceiling/Floor | ❌ vnstock không trả | Suy ra ±7% HOSE từ `close[t-1]` |
| Fundamentals theo quý | ✅ `stock.fact_fundamental_quarterly` | Có revenue, LN, EPS, ROE, D/E |
| **Ngày công bố BCTC** | ❌ vnstock không có report_date đáng tin | **Dùng `value_mode = technical_proxy`** để tránh look-ahead bias. Nếu bổ sung được report_date sau, chuyển sang `fund` |
| P/E, P/B, EV/EBITDA | ❌ Chưa có | Tính từ: `pe_ttm = close / (TTM_EPS)`, `pb = close / BVPS`. Rolling sum 4 quý cho TTM |
| Industry | ✅ `stock.dim_industry` + `dim_ticker.industry_id` | Dùng cho ràng buộc đa dạng mục 6.3 |

**Decision ban đầu**: Chạy phase 1 với `value_mode = technical_proxy` cho an toàn (không có report_date tin cậy). Phase 2 sẽ tính TTM từ fundamentals sau khi verify không có look-ahead.
