# 03 — Runbook triển khai

Thứ tự: Supabase → seed Storage → GitHub Actions → Netlify → nghiệm thu.

## A. Supabase
1. Tạo project (region gần VN: Singapore `ap-southeast-1`).
2. Áp migration:
   ```bash
   supabase link --project-ref <ref>
   supabase db push            # chạy supabase/migrations/20261026000000_vnq_init.sql
   ```
   Kiểm tra: 6 bảng + 2 view trong `public`; RLS bật; bucket `vnq-data` tồn tại và **private**.
3. Auth:
   - Bật Email provider (magic link). **Tắt "Allow new users to sign up"**, mời email của Hardy (Authentication → Users → Invite).
   - Site URL và Redirect URLs = domain Netlify (thêm `http://localhost:8765` khi dev).
4. Lấy `Project URL`, `anon key`, `service_role key` (Settings → API).

## B. Seed dữ liệu lên Storage (1 lần)
```bash
cd engine && pip install -r requirements.txt
export SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=...
python -m vnq storage bootstrap          # đẩy data/seed/{panel.parquet,vnindex.parquet,industry.csv}
python -m vnq cloud-run --skip-update    # lần chạy đầu: tạo state + publish ngày 10/07/2026
```
Kiểm tra `daily_runs` có 1 dòng 2026-07-10, `signals` 10 dòng, `scores_daily` 130 dòng.

## C. GitHub Actions
1. Push repo (private). Secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.
2. Actions → `vnq-daily` → Run workflow (skip_update = true) để thử. Log và báo cáo được lưu thành artifact 30 ngày.
3. Cron `30 11 * * 1-5` (UTC) = 18:30 giờ VN. Nếu không có file mới trong inbox, job vẫn chạy lại báo cáo cho ngày dữ liệu cuối (idempotent, upsert).

## D. Netlify
1. New site from Git, base = repo root (đọc `netlify.toml`: publish `web`, build `node scripts/write-config.mjs`).
2. Env: `SUPABASE_URL`, `SUPABASE_ANON_KEY` (**anon**, không phải service). Script build sẽ fail nếu 2 key trùng nhau và có biến `SUPABASE_SERVICE_ROLE_KEY` trong env — đừng đặt service key ở Netlify.
3. Deploy → mở site → đăng nhập bằng email đã mời → đối chiếu `05_ACCEPTANCE_TESTS.md`.
4. CSP trong `netlify.toml` cho phép `cdn.jsdelivr.net` (supabase-js) và `*.supabase.co`. Nếu dùng custom domain cho Supabase, sửa `connect-src`.

## E. Nạp dữ liệu hằng ngày (sau khi Hardy chốt nguồn — 04_OPEN_ITEMS #1)
- **Thả file tay:** upload csv vào `vnq-data/inbox/` (Dashboard Supabase → Storage, hoặc trang upload nếu làm thêm).
- **vnstock:** sửa `engine/config.yaml` → `data_source: vnstock`, thêm `vnstock` vào requirements, kiểm tra adapter `vnq/data.py::fetch_vnstock` trên runner thật (chưa test). Chú ý: giá vnstock có điều chỉnh quyền hay không phụ thuộc nguồn — QC lệch giá sẽ tự kéo lại toàn bộ lịch sử mã bị lệch.
- **Dữ liệu cũ:** hiện dữ liệu dừng 10/07/2026. Cần nạp bù 13/07 → hiện tại (một file lớn vào inbox là được) — sau đó tập test có ~75 ngày và gate mới có ý nghĩa.

## F. Vận hành
| Việc | Cách |
|---|---|
| Xem trạng thái | `python -m vnq status` (local, sau `storage pull`) hoặc dashboard |
| Chạy lại 1 ngày | workflow_dispatch skip_update = true |
| Train model mới | local: `python -m vnq train --version tn08 --note "..."` → commit `models/tn08` → sửa `model_version` → PR. Không train đè tn07. |
| Sửa phí đã xác nhận | `config.yaml: costs.fee_per_side`, `fee_confirmed: true` (không cần train lại) |
| Thêm danh sách sàn | upload `data/exchange_map.csv` (cột `ticker,exchange`) lên Storage |
| Sự cố publish | job fail → artifact có `run.log`; state chưa push nên lần sau chạy lại an toàn |

## G. Rollback
Bảng chỉ upsert theo khóa ngày → chạy lại là ghi đè. Storage có `archive/` cho file inbox. Muốn bỏ một ngày: xóa dòng `daily_runs` (cascade `gate_snapshots`) + `signals`/`scores_daily` cùng `data_date`, và dòng tương ứng trong `state/signals_log.csv`.
