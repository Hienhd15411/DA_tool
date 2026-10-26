# 05 — Nghiệm thu

Số kỳ vọng dưới đây lấy từ e2e trên Supabase giả lập (seed tới 30/06 + nạp từng ngày 01–10/07/2026). Trên môi trường thật, sau khi bootstrap seed **đầy đủ tới 10/07** và chạy `cloud-run --skip-update` một lần, chỉ ngày 10/07 có dữ liệu; các số của ngày 10/07 phải khớp.

## Engine / DB
| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| E1 | `python -m vnq status` sau bootstrap | `last_date = 2026-07-10`, `dups = 0`, `blocking = false` |
| E2 | `daily_runs` ngày 2026-07-10 | `n_eligible = 130`, `n_pool = 40`, `gate_pass = false`, model `tn07` |
| E3 | `signals` ngày 2026-07-10 theo `rank_sel` | DIG, SZC, KDH, VSC, HDG, VNM, KSB, HPG, VIX, DBC; `p_up_5` DIG ≈ 0,355; tất cả `action = 'Theo dõi'` |
| E4 | `scores_daily` 2026-07-10 | 130 dòng; `value_top30 = true` ở 40 dòng |
| E5 | `gate_snapshots.checks` | mảng 6 phần tử theo thứ tự: Đủ ngày test → excess → IC → lift → calibration → baseline |
| E6 | `model_versions` tn07 | `best = lgb2`, `n_train = 50644`, `train_end_effective = 2026-06-23`, `wf_ic.lgb2 ≈ 0.0421` |
| E7 | `experiments` | 20 dòng (4 fold × 5 model) |
| E8 | Chạy `cloud-run` 2 lần liên tiếp | Không nhân đôi dòng (upsert) |
| E9 | Đổi `ledger.topk` trong config rồi chạy | Engine từ chối: "config.yaml (ledger/universe) đã đổi…" |
| E10 | `python -m vnq train --version tn07` | Từ chối: "Model tn07 đã tồn tại và đã đóng băng" |
| E11 | Nạp file inbox ngày mới | file chuyển sang `archive/`, `daily_runs` có ngày mới; sau 5 phiên tín hiệu cũ có `status = settled` |

Nếu nạp lần lượt 01→10/07 như e2e: `v_track_record` "(tất cả)" = 30 tín hiệu / 3 ngày, hit 16,7%, net −2,34%, excess −0,38%.

## Bảo mật
| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| S1 | Gọi REST `/rest/v1/signals` với anon key, không đăng nhập | 0 dòng hoặc 401/permission denied |
| S2 | User đăng nhập insert/update vào `signals` | Bị từ chối |
| S3 | Bucket `vnq-data` | private; anon không tải được `data/panel.parquet` |
| S4 | Mã nguồn web build trên Netlify | Không chứa service key (`grep service_role` trên `config.js` trống) |
| S5 | Sign-up công khai | Tắt; email lạ không tạo được tài khoản |

## Web
| # | Kiểm tra | Kỳ vọng |
|---|---|---|
| W1 | Chưa đăng nhập | Form magic link, không hiện dữ liệu |
| W2 | Đăng nhập | Header: 10/07/2026 · tn07 · 130 · 40 · "✕ CHƯA ĐẠT" |
| W3 | Cảnh báo | Có "Dữ liệu cũ … ngày", phí giả định, thanh khoản chưa xác nhận, sàn suy luận, technical_proxy |
| W4 | Bấm 1 dòng top 10 | Hiện rủi ro + lý do chỉ theo dõi |
| W5 | Tra cứu "HPG" | Bảng điểm + sparkline, không lỗi console |
| W6 | Mobile 390px | Không tràn ngang trang (bảng cuộn trong khung) |
| W7 | Dark mode hệ điều hành | Màu đúng, chữ đọc được |
| W8 | Mọi màn hình có tín hiệu | Có dòng cảnh báo rủi ro cuối trang; không có chữ "nên mua", "chắc chắn" |
