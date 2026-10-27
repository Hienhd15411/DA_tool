# 08 — Sổ tay agent vận hành VNQ (chạy tự động mỗi tối thứ 2–6)

Agent là một phiên Claude Code chạy theo lịch (scheduled task) **sau** pipeline tối:
17:00 `vnq-cdc` (lấy giá chốt) → 18:30 `vnq-daily` → `vnq-qc-prod` (tự chạy sau mỗi job dữ liệu).
Mục tiêu: người dùng không phải tự đi kiểm tra. Agent kiểm tra, tự xử lý sự cố có quy trình, rồi gửi **1 thông báo**.

Repo `Hienhd15411/DA_tool`, branch `vnq-deploy`. Không có service key trong phiên agent — mọi thao tác dữ liệu đi qua
GitHub Actions (đẩy file trigger), đọc kết quả bằng log job (GitHub MCP: `actions_list`, `get_job_logs`).

## 1. Kiểm tra (theo thứ tự)
1. **Ngày giao dịch?** Hôm nay (giờ VN) là T7/CN → chỉ báo "nghỉ", dừng. Ngày lễ: nếu `vnq-cdc` báo không có phiên mới → coi là nghỉ.
2. **Các job hôm nay** (`list_workflow_runs` cho `vnq-cdc.yml`, `vnq-daily.yml`, `vnq-qc.yml`, lọc `created_at` hôm nay):
   - thiếu job cron (GitHub có thể trễ/bỏ) hoặc `failure` → xem log (`get_job_logs failed_only`) → mục 2.
3. **QC production** lần gần nhất sau job dữ liệu: `success`? Nếu `failure` → đọc các dòng `❌` cuối log.
4. **Dữ liệu** — chạy `vnq-check` (ghi ngày giờ vào `.github/vnq-check`, commit, push) rồi đọc log `check_live.py`. Kỳ vọng:
   - `daily_runs` ngày mới nhất = phiên hôm nay; không có cảnh báo nến chưa chốt
   - `open rows before …` = 0 (chỉ 5 phiên gần nhất được "chờ")
   - `LATEST`: ngày dự báo mới nhất và số dòng ≈ số mã đủ điều kiện (~120–140); không có ngày sau ngày dữ liệu
   - danh mục mô phỏng: liệt kê lệnh `planned` (vào phiên tới) và `open` có `sessions_left = 1` (bán phiên tới)
   - `HEALTH last20`: IC, top10 − thị trường → đèn theo `docs/07_LIVE_MONITORING.md`

## 2. Được tự xử lý (có quy trình, làm tối đa 1 lần/sự cố/ngày)
| Sự cố | Cách xử lý |
|---|---|
| Job cron không chạy / lỗi mạng tạm thời (timeout, 5xx, VCI không phản hồi) | Chạy lại: `vnq-cdc` → `printf 'cdc <YYYYMMDD-HHMMSS>\n' > .github/vnq-cdc`; `vnq-daily` → `printf 'daily\n# run: <lý do>\n' > .github/vnq-trigger` (dòng 1 phải đúng `daily`). Commit + push, chờ, kiểm tra lại |
| Dữ liệu một ngày bị nạp sai (nến chưa chốt, khối lượng trung vị < 0,5×, ngày lạ) | `printf '<YYYY-MM-DD>\n# <lý do>\n' > .github/vnq-rollback`, push → workflow rút ngày đó + chạy lại daily. Sau 17:00 có thể chạy lại `vnq-cdc` để lấy giá chốt |
| Dự báo cũ > 5 phiên còn "chờ" | Chạy lại `vnq-daily` (publish đẩy cả dòng vừa quyết toán). Còn kẹt → báo |
| Lỗi code rõ ràng ở **hạ tầng** (publish/kiểu dữ liệu/đường dẫn/workflow), sửa nhỏ, cục bộ | Sửa trên `vnq-deploy`, commit message nêu rõ lỗi + bằng chứng log, push, xác nhận QC xanh. Ghi vào báo cáo |

## 3. KHÔNG được làm (báo người dùng thay vì làm)
- Đổi ledger (`engine/config.yaml`), model (`engine/models/*`), feature (`vnq/features.py`), ngưỡng gate, luật TN06-R, tham số danh mục.
- Train model, đổi `model_version`, chỉnh bất cứ thứ gì sau khi nhìn kết quả hiệu quả.
- Xóa dữ liệu ngoài quy trình rollback (rollback luôn backup trước).
- Thêm câu chữ khuyến nghị ("nên mua"…) vào web/báo cáo. Tín hiệu vẫn là "theo dõi" khi gate chưa đạt.
- Sửa lặp lại cùng một lỗi > 1 lần trong ngày, hoặc sửa lớn/không chắc → dừng, báo kèm log.
- Tạo PR, đổi secrets, đổi cấu hình Netlify/Supabase.

## 4. Báo cáo (1 thông báo/ngày, tiếng Việt, ngắn)
Nguồn số liệu: log bước `agent_brief.py` của `vnq-check` (mục MARKET / PLAN / BREAKEVEN) + kết quả kiểm tra ở mục 1.
Chỉ chép số từ log, không tự suy diễn số mới.
```
VNQ <dd/mm> — <🟢 Ổn | 🟡 Có sự cố đã xử lý | 🔴 Cần bạn xử lý>
① Thị trường: VNINDEX <giá> (<1 phiên>, <20 phiên>); <trên/dưới> EMA50; <x> tăng/<y> giảm; <z>% mã trên EMA50; thanh khoản <k>× TB20
② Phiên tới (mô phỏng TN06-R, chưa đạt kiểm định):
   Vào: <mã — số cp ≈ số tiền (10% NAV, vốn 100 tr) — hòa vốn khi ≥ giá> | không
   Thoát: <mã — bán 100% ATC — lãi/lỗ tạm tính> | không
   Đang giữ: <mã — còn n phiên — lãi/lỗ> | không
③ Giữ bao lâu thì hòa vốn: cần +0,40% sau phí; lịch sử <x>% lệnh chạm hòa vốn trong 5 phiên (trung vị phiên thứ <n>);
   kỳ vọng hiện tại <±y>%/lệnh (<dương/âm>)
• Pipeline: cdc ✓/✗ · daily ✓/✗ · QC ✓/✗ · Model TN07: đèn <…>
• Sự cố & xử lý: <không | …> · Cần bạn: <không | việc cụ thể + link>
```
Luôn ghi rõ lệnh là **mô phỏng, chưa đạt kiểm định**; không dùng chữ "nên mua/nên bán".

## 5. Nhiệm vụ trader — 4 agent A1–A4 (docs/09_TRADER_EXPERIMENT.md, trader/agents.json)
Sau phần vận hành, mỗi tối ngày giao dịch:
1. Kích hoạt `vnq-trader` (ghi ngày giờ vào `.github/vnq-trader`, push) → đọc log: **Tin tức**, **Mô phỏng** (NAV, lệnh khớp/không khớp,
   bị từ chối, vị thế của từng agent), **Bản tin thị trường**.
2. Lần lượt **đóng vai từng agent** theo đúng `trader/agents.json` (phong cách, khẩu vị rủi ro, giới hạn, thời gian giữ, mục tiêu,
   **chỉ mã trong phạm vi ngành của agent đó**). Quyết định của mỗi agent độc lập, không phối hợp giữa các agent.
   - Nguồn: bản tin thị trường, tín hiệu TN06-R / TN07 / watchlist, tin tức trong log. Không dùng thông tin sau thời điểm quyết định.
   - Kế hoạch đầy đủ (docs/09 "Kế hoạch giao dịch"): mỗi BUY có vùng giá vào, stop_loss, take_profit, horizon_sessions, confidence;
     **cỡ lệnh = risk_per_trade của agent × NAV ÷ % khoảng cách cắt lỗ**, không vượt max_weight; mỗi mã đang giữ có HOLD/SELL;
     3–5 WATCH kèm điều kiện vào lệnh; market_view + risk_plan riêng theo chân dung.
   - Kỷ luật: vị thế đóng cửa ≤ stop_loss hoặc ≥ take_profit đã cam kết → SELL; không dời cắt lỗ xa hơn. Không có lý do rõ → không mở lệnh mới.
3. Ghi `trader/orders/<A1|A2|A3|A4>/<YYYY-MM-DD phiên kế tiếp>.json` (4 file), **commit + push trước 09:00 phiên đó** (tối nay là tốt nhất).
   Không sửa file đã commit.
4. Báo cáo tối mở đầu bằng **ĐỀ XUẤT PHIÊN TỚI** theo từng agent (mã, giá vào, số tiền ≈ số cp, cắt lỗ, chốt lời, giữ bao lâu, lý do 1 dòng;
   mã đang giữ; theo dõi), rồi **④ Thi đấu**: NAV + lời/lỗ hôm nay và lũy kế của A1–A4, B, C, và mỗi agent vs bốc thăm đối ứng (R1–R4).
Không được: dùng ngôn ngữ khuyến nghị cho người đọc; sửa lịch sử lệnh; tự đổi luật mô phỏng, giới hạn hay phạm vi ngành để có lợi cho agent.
