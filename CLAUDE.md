# CLAUDE.md — VNQ (tín hiệu cổ phiếu VN, trend 5 phiên)

Bạn (Claude Code) nhận bàn giao để **triển khai** hệ thống này lên **Supabase + Netlify + GitHub Actions**.
Code đã chạy được và đã test e2e trên Supabase giả lập; việc của bạn là dựng hạ tầng thật, nối secrets, kiểm thử trên môi trường thật và hoàn thiện. Đọc theo thứ tự:

1. `docs/01_PROJECT_CONTEXT.md` — vai trò, nguyên tắc bắt buộc, ledger quyết định đã chốt (**nguồn sự thật**)
2. `docs/02_ARCHITECTURE.md` — kiến trúc, luồng dữ liệu, schema
3. `docs/03_DEPLOY_RUNBOOK.md` — các bước triển khai
4. `docs/04_OPEN_ITEMS.md` — việc còn chờ người dùng (Hardy) quyết định
5. `docs/05_ACCEPTANCE_TESTS.md` — tiêu chí nghiệm thu

## Luật không được vi phạm (từ ledger dự án)
- **Không refit / không chỉnh tham số model sau khi xem test.** `engine/models/tn07/` là model đóng băng. Không train đè. Model mới = version mới (`python -m vnq train --version tn08`), mọi config thử ghi vào `experiments`.
- **Không đổi ledger trong `engine/config.yaml`** (train/test dates, label, topk, value_top_pct, max_per_industry, ngưỡng thanh khoản, ticker_regex, min_bars). Engine tự từ chối chạy nếu ledger hash lệch manifest — đừng "sửa" cơ chế này.
- **Gate mục 6 quyết định ngôn ngữ.** Chỉ hiện "Cân nhắc mua" khi `gate_snapshots.strategy_pass = true` VÀ mã không trần/sàn/mâu thuẫn trend/quarantine. Không thêm từ ngữ kiểu "nên mua", "sắp bùng nổ". Mọi màn hình có tín hiệu phải có dòng cảnh báo rủi ro.
- **No look-ahead.** Feature tại t chỉ dùng dữ liệu ≤ t. Entry = open t+1. Chi phí: phí 2 chiều + thuế bán 0,1%.
- **Không bịa số liệu.** Thiếu dữ liệu → hiện cờ (vd `value_mode = technical_proxy`), không điền giả.
- **Bảo mật:** `SUPABASE_SERVICE_ROLE_KEY` chỉ ở GitHub Actions secrets. Web chỉ dùng anon key; dữ liệu bảo vệ bằng RLS (đọc cho `authenticated`). `scripts/write-config.mjs` chặn nếu anon key = service key.
- Dashboard **chỉ đọc**. Không thêm đường ghi từ web vào bảng kết quả.

## Bản đồ repo
```
engine/                 Python engine (pandas, LightGBM 4.7.0, scikit-learn 1.9.1 — pin vì logreg.joblib)
  vnq/cli.py            lệnh: daily | update | status | train | publish | storage pull|push|bootstrap | cloud-run
  vnq/supa.py           REST tới Supabase: Storage (data/state) + PostgREST upsert (publish)
  vnq/features.py       feature/label/universe TN07 (KHÔNG sửa logic — sẽ lệch model)
  vnq/model.py          train walk-forward + Frozen loader + khóa ledger_hash
  vnq/backtest.py       chọn top-K, backtest sau phí, gate mục 6
  vnq/tracker.py        signals_log, quyết toán sau 5 phiên
  vnq/report.py         báo cáo md/html (cũng được upload Storage)
  models/tn07/          model đóng băng + manifest + walkforward_log
  data/seed/            dữ liệu seed (cổ phiếu 3 ký tự từ 2022 → 10/07/2026, VNINDEX, ngành)
  tests/mock_supabase.py, tests/e2e_cloud.sh   Supabase giả lập + test e2e
supabase/migrations/    schema + RLS + bucket vnq-data
web/                    dashboard tĩnh (vanilla JS + supabase-js@2.45.4 qua jsDelivr), demo-data.json
design/uxui-kit/        bộ skill UX/UI (plugin87/ux-ui-agent-skills v3.0.0, MIT): token, taste, a11y, các gate đo — xem VENDORED.md
.claude/skills/         26 skill của bộ kit (redesign, data-dashboard, a11y-audit, design-review, gate…), đường dẫn trỏ về design/uxui-kit
scripts/write-config.mjs  Netlify build: sinh web/config.js từ env
.github/workflows/vnq-daily.yml  cron 18:30 ICT thứ 2–6 → `python -m vnq cloud-run`
research/tn07/          script nghiên cứu gốc + kết quả TN07 (tham chiếu, không deploy)
docs/                   tài liệu bàn giao
```

## Lệnh thường dùng
```bash
cd engine && pip install -r requirements.txt
python -m vnq status
python -m vnq daily --skip-update            # chạy local với dữ liệu trong engine/data
# e2e trên Supabase giả lập (cần Postgres local + migration đã apply):
DSN="host=localhost port=5432 user=postgres" tests/e2e_cloud.sh
# web demo: VNQ_DEMO=1 node scripts/write-config.mjs && python -m http.server -d web 8765 → /?demo
```

## Việc cần làm (xem runbook để biết chi tiết)
- [ ] Tạo Supabase project, `supabase db push` migration, kiểm tra bucket `vnq-data` (private)
- [ ] Bật Auth email (magic link), tắt sign-up công khai, mời email của Hardy; cấu hình Site URL = domain Netlify
- [ ] `python -m vnq storage bootstrap` (đẩy seed) — chạy 1 lần với service key
- [ ] GitHub repo + secrets `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`; chạy tay workflow `vnq-daily` 1 lần
- [ ] Netlify site từ repo, env `SUPABASE_URL`, `SUPABASE_ANON_KEY`; đăng nhập và đối chiếu số với `docs/05_ACCEPTANCE_TESTS.md`
- [ ] Chốt nguồn dữ liệu hằng ngày với Hardy (`docs/04_OPEN_ITEMS.md` #1) — đây là điểm nghẽn duy nhất để chạy tự động thật
- [ ] Cân nhắc: trang upload file vào `inbox/` cho Hardy (Storage policy riêng cho user đã đăng nhập), nếu Hardy chọn cách thả file tay

## Sửa giao diện web/
- Token màu/khoảng cách chỉ khai báo ở đầu `web/styles.css` (light + dark); không viết mã màu trong `app.js`. Màu danh mục thi đấu = `--agent-*`.
- 4 tab (`Phiên tới`, `Thi đấu`, `Model`, `Tra cứu`): mỗi khối khai báo `data-tab` trong `index.html`; giữ nguyên các id mà `tools/qc_prod.py` dùng.
- Kiểm tra trước khi push: `python3 design/uxui-kit/scripts/lint_hardcodes.py web` và các gate trình duyệt (`DS_CHROME_CHANNEL=bundled node design/uxui-kit/scripts/gate.mjs axe_audit.mjs <file>`),
  chạy trên bản DOM đã render của chế độ demo (gate chỉ đọc file://).

## Đừng làm
- Đừng chuyển engine sang JS/Edge Functions (LightGBM + pandas; Netlify/Supabase functions không chạy được Python).
- Đừng commit `.env`, `web/config.js`, service key.
- Đừng xóa cột/đổi tên bảng mà không cập nhật `vnq/supa.py` + `web/app.js` cùng lúc.
- Đừng "làm đẹp" kết quả: TN07 hiện **chưa đạt** gate (xem `docs/TN07_bien_ban_kiem_dinh.md`). Dashboard phải phản ánh đúng.
