# 02 — Kiến trúc

## Tổng quan
```
   (nguồn dữ liệu hằng ngày — CHƯA CHỐT, xem 04_OPEN_ITEMS #1)
        │  file csv/parquet → Storage vnq-data/inbox/   hoặc   data_source: vnstock (engine tự kéo)
        ▼
┌──────────────────────────── GitHub Actions (cron 18:30 ICT, T2–T6) ────────────────────────────┐
│ python -m vnq cloud-run                                                                         │
│  1. storage pull   : data/*.parquet, state/* , inbox/*  ← Supabase Storage (service key)        │
│  2. daily          : ingest+QC → features (TN07) → score model đóng băng → gate mục 6 (test)    │
│                      → quyết toán tín hiệu ≥5 phiên → chọn top 10 → báo cáo md/html/csv         │
│  3. publish        : upsert Postgres qua PostgREST (service key)                                │
│  4. storage push   : data/state/reports → Storage; inbox/* → archive/                           │
└────────────────────────────────────────────────────────────────────────────────────────────────┘
        ▼                                                    ▼
 Supabase Postgres (RLS: authenticated SELECT)        Supabase Storage bucket `vnq-data` (private)
        ▼
 Netlify (static web/) — supabase-js, anon key, đăng nhập magic link → dashboard chỉ đọc
```

**Vì sao không dùng Netlify Functions / Supabase Edge Functions cho engine:** engine cần pandas + LightGBM + scikit-learn (Python). Netlify Functions (JS/TS/Go) và Supabase Edge Functions (Deno) không chạy được. GitHub Actions miễn phí cho repo private ở mức vài phút/ngày (1 lần chạy ≈ 1–2 phút).

## Engine — trạng thái giữ ở đâu
Runner GitHub Actions là máy sạch mỗi lần chạy, nên **Storage là nơi giữ trạng thái**:

| Key trong bucket `vnq-data` | Nội dung | Ghi bởi |
|---|---|---|
| `data/panel.parquet` | OHLCV + GTGD cổ phiếu 3 ký tự từ 2022 (giá đã điều chỉnh quyền) | bootstrap, mỗi lần chạy |
| `data/vnindex.parquet` | VNINDEX | như trên |
| `data/industry.csv` | ticker → ngành (22 ngành) | bootstrap / file inbox có cột industry |
| `data/exchange_map.csv` | ticker → HOSE/HNX/UPCOM (**chưa có**) | Hardy cung cấp |
| `state/signals_log.csv` | sổ tín hiệu paper trading (nguồn sự thật cho bảng `signals.status..excess`) | mỗi lần chạy |
| `state/quarantine.json` | mã bị loại do nghi lệch điều chỉnh quyền | mỗi lần chạy |
| `state/gate.json` | snapshot gate gần nhất | mỗi lần chạy |
| `inbox/*.csv|parquet` | dữ liệu mới chờ nạp | Hardy / job kéo dữ liệu |
| `archive/<ts>_<file>` | file inbox đã nạp | engine |
| `reports/signals_<date>.{md,html,csv}` | báo cáo từng ngày | engine |

Model (`engine/models/tn07`) nằm trong git, không trong Storage — để thay đổi model phải qua commit (có review).

## Định dạng file inbox
Cột bắt buộc: `ticker, date, open, high, low, close, volume`; tùy chọn: `gt_khop` (GTGD khớp, VND), `gt_thoathuan`, `kl_khop`, `kl_thoathuan`, `industry`. Giá đơn vị **nghìn đồng**, **đã điều chỉnh quyền**. VNINDEX dùng `ticker = VNINDEX`. Thiếu `gt_khop` → ước tính `close × volume × 1000`.
Upsert theo (ticker, date). Nếu giá close ở ngày chồng lấn lệch > 0,5%: file có ≥ 260 phiên của mã đó → thay toàn bộ lịch sử; ngược lại → mã vào quarantine (loại khỏi chọn) đến khi được gửi lại đủ lịch sử khớp.

## Schema Postgres (`supabase/migrations/20261026000000_vnq_init.sql`)
| Bảng | Khóa | Nội dung |
|---|---|---|
| `model_versions` | version | manifest model (params, features, train range, IC walk-forward) |
| `experiments` | (version, fold, model) | mọi config đã thử trong walk-forward (nguyên tắc 7) |
| `daily_runs` | data_date | header báo cáo: n đủ điều kiện, n pool, regime, QC, cảnh báo, quarantine, gate_pass |
| `gate_snapshots` | data_date | điều kiện gate (mảng `{name, pass}` giữ thứ tự) + metrics test (LightGBM, logistic) |
| `scores_daily` | (data_date, ticker) | điểm toàn universe đủ điều kiện (~130 mã/ngày) — tra cứu mã |
| `signals` | (data_date, ticker) | top 10/ngày + rủi ro + nhận định; cột kết quả cập nhật khi đủ 5 phiên |
| `v_track_record` (view) | — | tổng hợp paper trading theo nhận định |
| `v_track_daily` (view) | — | lãi/lỗ trung bình theo ngày tín hiệu |

Engine ghi bằng service role (bypass RLS). Web đọc với role `authenticated`. `anon` không đọc được (chặn ở cả policy và grant). Có khối "PUBLIC READ" tùy chọn ở cuối migration — chỉ bật nếu Hardy đồng ý.

## Web
`web/` thuần HTML/CSS/JS, không build step (Netlify chỉ chạy `scripts/write-config.mjs` để sinh `config.js` từ env).
Các phần: header (ngày dữ liệu, model, n đủ điều kiện/pool, regime, gate) · cảnh báo · gate mục 6 + metrics · paper trading (tile + biểu đồ lãi/lỗ theo ngày + bảng) · top 10 (bấm để xem rủi ro) · tra cứu mã (diễn biến `p_up_5` 60 ngày) · dòng cảnh báo rủi ro.
`?demo` hoặc không có `SUPABASE_URL` → đọc `demo-data.json` (8 ngày 01–10/07/2026 sinh từ e2e) để xem giao diện mà không cần backend.

## Kiểm thử đã chạy (26/10/2026)
- Tái lập TN07: điểm số tool = điểm TN07 (sai lệch 0), IC walk-forward 0,0421, 50.644 dòng train.
- Mô phỏng 8 phiên 01–10/07/2026 trên Supabase giả lập (`tests/mock_supabase.py` + Postgres 16): mỗi phiên là runner sạch, pull → daily → publish → push. Kết quả DB khớp TN07: 30 tín hiệu quyết toán, hit 16,7%, net −2,34%/5 phiên, excess −0,38%.
- Migration chạy 2 lần liên tiếp không lỗi (idempotent). RLS: authenticated đọc được; anon bị từ chối; authenticated không insert được.
- Dashboard: không lỗi console ở 1280px và 390px (light/dark), không tràn ngang.
- Kịch bản điều chỉnh quyền: file lệch một phần → quarantine; gửi lại đủ lịch sử → gỡ quarantine.
- Chưa test được: Supabase thật, GitHub Actions thật, Netlify thật, adapter `vnstock` (không cài được trong môi trường build).
