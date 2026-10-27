# 07 — Snapshot dự báo hằng ngày & quy trình điều chỉnh model

## Ghi gì, ở đâu
Mỗi lần `cloud-run` (engine/vnq/snapshot.py):
1. **Snapshot** dự báo của *mọi* mã đủ điều kiện tại ngày t vào `state/predictions_log.parquet`
   (Storage) và bảng `predictions_daily`: TN07 `p_up_5`, `p_lr`, hạng, top 10 được chọn; TN06-R tầng 1 BẬT/TẮT
   và tín hiệu. **Dự báo đã ghi không bao giờ bị sửa** (chạy lại cùng ngày giữ bản đầu).
2. **Quyết toán**: khi có close t+5, điền `real` (open t+1 → close t+5, kẹt sàn → t+6), `net` (sau phí), `y_bin`.
3. **Chấm theo ngày** → `live_eval_daily`: IC, top 10 TN07, random (= TB pool, kỳ vọng của bốc ngẫu nhiên),
   thị trường (TB mọi mã), top/bottom decile, dự báo TB vs hit thực tế, TN06-R.
4. Dashboard: mục "Dự báo vs thực tế" và "TN06-R".

`source = backfill`: ngày từ `test_start` đến trước lần chạy đầu, dựng lại bằng model/luật đã đóng băng.
`source = live`: ghi đúng ngày. **Chỉ số live là bằng chứng sạch**; backfill của TN06-R nằm trong đoạn đã xem khi chọn tầng 1.

## Điều chỉnh model — luật
Snapshot dùng để **phát hiện** model hỏng và **đánh giá** model mới, không dùng để vặn tham số model đang chạy.

| Khi nào xem | Điều kiện | Hành động |
|---|---|---|
| Hằng tuần | — | Đọc mục "Dự báo vs thực tế"; không đổi gì |
| Cuối tháng (≥ 20 ngày live) | IC TB live ≤ 0 **và** TN07 vs thị trường < 0 | Đánh dấu TN07 "suy giảm" trong 04_OPEN_ITEMS, mở đề xuất version mới |
| Đề xuất version mới | Viết spec trước (feature/target/tham số), commit | `python -m vnq train --version tnXX`, walk-forward chỉ trong train (≤ ngày chốt spec) |
| So model mới vs cũ | Chạy song song ≥ 60 ngày live (shadow) trên cùng snapshot | Chỉ đổi `model_version` khi model mới thắng thị trường + random với CI95 > 0 trên đoạn live sau ngày chốt spec |

Không làm: retrain mỗi ngày theo kết quả vừa quyết toán; chỉnh ngưỡng/tham số sau khi nhìn live; xóa ngày xấu.
Mọi thay đổi = version mới + ghi `docs/06_EXPERIMENT_HISTORY.md`.

## Mốc đánh giá TN06-R
Spec chốt 27/10/2026. Paper trading forward từ ngày chạy live đầu tiên; chấm lại theo §8 của `TN06R_spec.md`
khi có ≥ 30 lệnh live đã quyết toán.
