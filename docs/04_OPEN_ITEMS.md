# 04 — Việc chờ Hardy quyết định

| # | Hạng mục | Hiện tại | Ảnh hưởng | Cần |
|---|---|---|---|---|
| 1 | **Nguồn dữ liệu hằng ngày** | Seed dừng 10/07/2026. Có 2 đường: thả file vào `inbox/`, hoặc adapter vnstock (chưa test) | **Chặn chạy tự động thật** | Chọn nguồn; nếu là script riêng của Hardy → cho nó ghi file vào Storage `inbox/` |
| 2 | Phí môi giới | Giả định 0,15%/chiều | Backtest, gate, paper trading | Mức thật → `costs.fee_per_side`, `fee_confirmed: true` |
| 3 | Ngưỡng thanh khoản | 5 tỷ VND/ngày (GTGD khớp TB20) | Universe → **đổi = train version mới** | Xác nhận hoặc đổi trước khi chạy thật |
| 4 | Danh sách sàn | Suy luận từ biên độ, sai VSC/VIX | Kiểm tra trần/sàn | `exchange_map.csv` |
| 5 | Biên độ UPCoM | Engine 15% (thực tế); context ghi 10% | Kiểm tra trần/sàn | Xác nhận |
| 6 | Ngưỡng ngày test tối thiểu cho gate | 60 ngày (đề xuất) | Khi nào được phép "cân nhắc mua" | Xác nhận |
| 7 | Quyền xem dashboard | Chỉ user được mời (magic link) | Bảo mật | Giữ private hay mở public read |
| 8 | Dữ liệu cơ bản | Không có → `technical_proxy` | value_score | Có nguồn PE/PB/ROE + ngày công bố không? |
| 9 | TN06 (hệ 2 tầng capitulation, đang paper trading từ 09/07/2026) | **Không nằm trong engine này** — engine chỉ có TN07 (ML) | Dashboard chỉ thấy TN07 | Có muốn đưa TN06 lên cùng nền tảng? Cần code `pipeline/18_daily_signals.py` gốc |
| 10 | Hướng TN08 | Đã đăng ký trước 2 biến thể (xem biên bản TN07 mục 6) | Cải thiện model | Chỉ chạy sau khi có dữ liệu test đầy đủ cho TN07 |

**Kết quả hiện tại cần nói rõ với người dùng dashboard:** TN07 **chưa đạt** gate mục 6 — walk-forward 2025-07→2026-06: excess −0,12%/5 phiên sau phí (CI chứa 0), IC universe 0,040 [0,008; 0,067], calibration không đơn điệu; test chỉ có 3 ngày. Mọi tín hiệu là "Theo dõi".
