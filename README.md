# VNQ — tín hiệu cổ phiếu VN (trend 5 phiên, model TN07)

Engine Python chạy hằng ngày trên **GitHub Actions** → ghi kết quả vào **Supabase** (Postgres + Storage) → dashboard tĩnh trên **Netlify** (chỉ đọc, đăng nhập magic link).

- Bàn giao cho Claude Code: đọc **`CLAUDE.md`** trước.
- Kiến trúc: `docs/02_ARCHITECTURE.md` · Triển khai: `docs/03_DEPLOY_RUNBOOK.md` · Việc chờ quyết định: `docs/04_OPEN_ITEMS.md` · Nghiệm thu: `docs/05_ACCEPTANCE_TESTS.md`
- Xem nhanh giao diện không cần backend: `VNQ_DEMO=1 node scripts/write-config.mjs && python -m http.server -d web 8765` → http://localhost:8765/?demo

> Trạng thái mô hình: TN07 **chưa đạt** điều kiện mục 6 → mọi tín hiệu ở mức "Theo dõi". Đây là tín hiệu thống kê, không phải khuyến nghị đảm bảo lợi nhuận.
