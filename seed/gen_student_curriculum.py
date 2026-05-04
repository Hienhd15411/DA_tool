#!/usr/bin/env python3
"""Generate giáo án học viên (.xlsx + .csv) từ docs/exercises/*.md.

Sheets:
  1. Trang chủ — overview + cách dùng
  2. Lộ trình  — 10 buổi (vắn tắt nội dung, bài tập map theme)
  3. Bài tập   — 87 bài (title, level, skill, est, theme, business context,
                  approach hint, expected shape, common mistakes — KHÔNG có SQL solution)
  4. Schema    — 18 bảng (grain + 1-line description)
  5. Hướng dẫn — login, tool URL, format trả bài

Usage:  python seed/gen_student_curriculum.py
"""
from __future__ import annotations
import re
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).parent.parent
DOCS = ROOT / "docs" / "exercises"
OUT_XLSX = ROOT / "docs" / "giao_an_hoc_vien.xlsx"
OUT_CSV_DIR = ROOT / "docs" / "giao_an_hoc_vien_csv"

# =========================================================================
# 1. PARSE EXERCISES
# =========================================================================

# Bắt header dạng "## A1 — title" hoặc "## A1. title"
HEADER_RE = re.compile(r"^## ([A-L])(\d+)\s*[—\-.:]?\s*(.+?)$", re.MULTILINE)
# Meta line: **Level:** L1 | **Skill:** ... | **Est:** 10 phút
META_RE = re.compile(
    r"\*\*Level:\*\*\s*L?(\d)[^|]*\|\s*\*\*Skill:\*\*\s*(.+?)\s*\|\s*\*\*Est:\*\*\s*([^*\n]+)",
    re.DOTALL,
)

THEME_NAMES = {
    "A": "Revenue / GMV trending",
    "B": "Customer lifecycle",
    "C": "Campaign / Sale day",
    "D": "Voucher / Promotion",
    "E": "Seller performance",
    "F": "Product / Category",
    "G": "Marketing / Ads",
    "H": "Operations / Shipping",
    "I": "Cancellation / Return",
    "J": "Customer Service",
    "K": "Geographic",
    "L": "Capstone (tổng hợp)",
}


def extract_section(body: str, heading_emoji_keyword: str) -> str:
    """Trích nội dung từ '### emoji keyword' đến '### ' kế hoặc EOF.
    Trả raw markdown (bỏ heading line)."""
    # Match heading line bắt đầu bằng ### + chứa keyword
    pattern = re.compile(
        rf"^### .*{re.escape(heading_emoji_keyword)}.*$\n([\s\S]*?)(?=^### |\Z)",
        re.MULTILINE,
    )
    m = pattern.search(body)
    if not m:
        return ""
    return m.group(1).strip()


def md_to_plain(md: str, max_chars: int = 800) -> str:
    """Đơn giản hoá markdown → plain (giữ \n giữa block, bỏ formatting)."""
    text = md
    text = re.sub(r"```sql.*?```", "", text, flags=re.DOTALL)  # bỏ SQL block
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)               # bold
    text = re.sub(r"`(.*?)`", r"\1", text)                     # inline code
    text = re.sub(r"\[(.*?)\]\(.*?\)", r"\1", text)            # links
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars - 1].rstrip() + "…"
    return text


def parse_file(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    matches = list(HEADER_RE.finditer(raw))
    out = []
    for i, m in enumerate(matches):
        theme, num, title = m.group(1), m.group(2), m.group(3).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[start:end]

        meta = META_RE.search(body[:600])
        level = int(meta.group(1)) if meta else 2
        skill = meta.group(2).strip() if meta else ""
        est   = meta.group(3).strip() if meta else ""

        biz_ctx  = md_to_plain(extract_section(body, "Business context"), 400)
        approach = md_to_plain(extract_section(body, "Approach"), 500)
        expected = md_to_plain(extract_section(body, "Expected result"), 400)
        mistakes = md_to_plain(extract_section(body, "Common mistakes"), 400)
        # KHÔNG lấy "SQL" (solution) — bản này là cho học viên

        out.append({
            "id": f"{theme}{num}",
            "theme": theme,
            "theme_name": THEME_NAMES.get(theme, theme),
            "level": level,
            "title": title,
            "skill": skill,
            "est": est,
            "business_context": biz_ctx,
            "approach_hint": approach,
            "expected_shape": expected,
            "common_mistakes": mistakes,
        })
    return out


def parse_all() -> list[dict]:
    rows = []
    for f in sorted(DOCS.glob("[A-L]-*.md")):
        rows.extend(parse_file(f))
    return rows


# =========================================================================
# 2. STATIC CONTENT — lộ trình + schema + hướng dẫn
# =========================================================================

SESSIONS = [
    # (số_buổi, chủ_đề, nội_dung_chính, theme_codes, exercises_range)
    # === THÁNG 1 — SQL FOUNDATION (8 buổi) ===
    (1,  "Buổi 1 — Intro tool + dataset Shopee",
     "Setup tool, đăng nhập, schema fact/dim, SELECT/FROM/WHERE/LIMIT, "
     "đọc số top-line: COUNT đơn, SUM total_amount.",
     "—", "—"),
    (2,  "Buổi 2 — ORDER BY, DISTINCT, operators",
     "ORDER BY ASC/DESC, DISTINCT, IN/BETWEEN/LIKE/IS NULL, "
     "string functions cơ bản (LOWER, UPPER, TRIM, ||).",
     "—", "(luyện cú pháp)"),
    (3,  "Buổi 3 — Aggregate functions",
     "COUNT, SUM, AVG, MIN, MAX, COUNT(DISTINCT). "
     "Tính GMV, AOV, basket size. Phân biệt COUNT(*) vs COUNT(col).",
     "A", "A1, A2"),
    (4,  "Buổi 4 — GROUP BY + HAVING",
     "GROUP BY 1 cột, nhiều cột. HAVING vs WHERE. "
     "GMV theo ngày/tuần/tháng (DATE_TRUNC sơ lược).",
     "A", "A3, A4"),
    (5,  "Buổi 5 — INNER JOIN",
     "Khái niệm join, JOIN 2 bảng (fact_orders + dim_date), "
     "JOIN 3 bảng (orders + items + product).",
     "A, F", "A5, F1"),
    (6,  "Buổi 6 — LEFT/RIGHT/FULL JOIN",
     "Khi nào dùng LEFT vs INNER. Tìm 'customer chưa mua', "
     "'sản phẩm chưa bán'. Anti-join pattern (NOT EXISTS / LEFT IS NULL).",
     "B, F", "B1, F2"),
    (7,  "Buổi 7 — Multi-table JOIN nâng cao",
     "JOIN 4-5 bảng. Bí quyết tránh Cartesian. Alias rõ ràng. "
     "Decompose query phức tạp.",
     "F, K", "F3, K1"),
    (8,  "Buổi 8 — Mini-project tháng 1",
     "Bài tổng hợp: viết GMV weekly report đầy đủ với MoM growth. "
     "Trình bày trên Google Sheets (paste TSV từ tool).",
     "A", "A6, A7, A8"),

    # === THÁNG 2 — TIME INTELLIGENCE + WINDOW FUNCTIONS (8 buổi) ===
    (9,  "Buổi 9 — DATE_TRUNC, EXTRACT, INTERVAL",
     "DATE_TRUNC('week'/'month'/'quarter'). EXTRACT(DOW/HOUR). "
     "INTERVAL math. Pattern theo giờ trong ngày.",
     "C", "C1, C2"),
    (10, "Buổi 10 — Time-series: WoW, MoM, YoY",
     "So sánh kỳ với kỳ. Self-join trên dim_date (chưa dùng window). "
     "Tăng trưởng tuyệt đối vs tăng trưởng %.",
     "C", "C3, C4"),
    (11, "Buổi 11 — Subquery cơ bản",
     "Scalar subquery, subquery trong WHERE/IN/EXISTS. "
     "Khi nào nên dùng subquery vs JOIN.",
     "B, F", "B2, F4"),
    (12, "Buổi 12 — CTE (WITH clause)",
     "WITH ... AS (...) SELECT. Multi-CTE. "
     "Lý do CTE > nested subquery: dễ đọc, dễ debug.",
     "B", "B3, B4"),
    (13, "Buổi 13 — Window function intro",
     "OVER (), PARTITION BY, ORDER BY trong window. "
     "Khác biệt aggregate vs window aggregate (giữ nguyên row).",
     "F", "F5"),
    (14, "Buổi 14 — Ranking: ROW_NUMBER, RANK, NTILE",
     "Top-N per group (top 5 SP mỗi seller). RANK vs DENSE_RANK. "
     "NTILE để chia tier (RFM segment).",
     "F, B", "F6, B5"),
    (15, "Buổi 15 — LAG, LEAD, running total",
     "Lag để tính growth %. Lead để check next event. "
     "SUM(...) OVER (ORDER BY ... ROWS BETWEEN ...) cho running total/MA.",
     "A, B", "A8 ext, B6"),
    (16, "Buổi 16 — Mini-project tháng 2",
     "Cohort retention 7/30 ngày + MoM signup growth. "
     "Output: bảng cohort matrix.",
     "B", "B7, B8, B9"),

    # === THÁNG 3 — BUSINESS ANALYTICS (8 buổi) ===
    (17, "Buổi 17 — RFM customer segmentation",
     "Recency / Frequency / Monetary. NTILE chia 5 tier. "
     "Crossing 3 dimension → 125 segment (rút gọn còn 4-5 nhóm chính).",
     "B", "B (extension)"),
    (18, "Buổi 18 — Voucher / promotion analysis",
     "Voucher redemption rate, average discount per order. "
     "Voucher có thật sự drive incremental orders?",
     "D", "D1-D4"),
    (19, "Buổi 19 — Campaign uplift",
     "Compare campaign period vs baseline (3 tuần trước). "
     "Cẩn thận seasonality. Self-join hoặc CTE để tính uplift.",
     "C, D", "C5-C7, D5-D7"),
    (20, "Buổi 20 — Marketing: ROAS, CTR, CPC",
     "fact_ad_spend × fact_ad_performance_daily. "
     "Tính ROAS, CTR, CPC theo channel/campaign. Channel nào hiệu quả nhất?",
     "G", "G1-G4"),
    (21, "Buổi 21 — Seller performance",
     "Top sellers theo GMV/units/AOV. Long tail vs head. "
     "Shop_type (mall/preferred/normal) ảnh hưởng GMV?",
     "E", "E1-E4"),
    (22, "Buổi 22 — Product / category trends",
     "Cat1 nào growth nhất 3 tháng qua? Brand contribution. "
     "Pareto 80/20 trên SKU level.",
     "F", "F7, F8"),
    (23, "Buổi 23 — Geographic analysis",
     "GMV theo region (north/central/south). Penetration rate. "
     "Province nào tỷ lệ cancel cao bất thường?",
     "K", "K1-K5"),
    (24, "Buổi 24 — Mini-project tháng 3",
     "Marketing dashboard end-to-end: top campaign, top seller, "
     "top SKU, ROAS theo channel. Trình bày bằng số + chart suggestion.",
     "C, D, E, G", "(tổng hợp)"),

    # === THÁNG 4 — OPERATIONS + CAPSTONE (8 buổi) ===
    (25, "Buổi 25 — Shipping & SLA",
     "On-time delivery rate. SLA breach theo carrier/route. "
     "Avg delivery time intra-city vs cross-region.",
     "H", "H1-H4"),
    (26, "Buổi 26 — Cancellation & return",
     "Cancel rate theo lý do, theo seller. Return reason analysis. "
     "Buyer cancel vs seller cancel patterns.",
     "I", "I1-I4"),
    (27, "Buổi 27 — Customer service tickets",
     "Ticket category distribution. Avg resolution time. "
     "Seller nào nhiều complaint nhất? Correlation với cancel/return.",
     "J", "J1-J5"),
    (28, "Buổi 28 — Advanced SQL patterns",
     "FILTER (WHERE ...), conditional aggregate, PIVOT bằng FILTER. "
     "CASE WHEN trong aggregate. JSON functions (nếu có thời gian).",
     "L (intro)", "L1, L2"),
    (29, "Buổi 29 — Performance & EXPLAIN",
     "Index, EXPLAIN basic. Vì sao query chậm? "
     "Best practice: filter sớm, tránh SELECT *, JOIN order.",
     "—", "(thực hành EXPLAIN)"),
    (30, "Buổi 30 — Capstone phần 1",
     "Bốc 1 case business thật từ theme L. Định nghĩa câu hỏi, "
     "phân rã thành sub-query, viết draft.",
     "L", "L3-L8 (tự chọn)"),
    (31, "Buổi 31 — Capstone phần 2",
     "Hoàn thiện query, validate kết quả, viết insight + recommendation. "
     "Format Google Slides / Sheets.",
     "L", "L9-L14"),
    (32, "Buổi 32 — Final presentation + Q&A",
     "Mỗi học viên trình bày capstone 5-7 phút. Giảng viên + bạn cùng lớp "
     "feedback. Tổng kết khoá + roadmap nâng cao.",
     "L", "L15-L17"),
]


SCHEMA = [
    # (table, group, grain, description)
    ("fact_orders", "fact", "1 row = 1 đơn hàng",
     "Bảng fact chính. Payment, shipping, customer/seller, timestamps qua lifecycle. "
     "Filter payment_status='paid' để tính GMV."),
    ("fact_order_items", "fact", "1 row = 1 dòng hàng trong đơn",
     "Line item chi tiết. quantity, unit_price, item_discount, line_total. JOIN với fact_orders qua order_id."),
    ("fact_shipment", "fact", "1 row = 1 lô hàng",
     "Pickup/deliver timestamps, SLA committed vs actual. is_on_time TRUE/FALSE."),
    ("fact_returns", "fact", "1 row = 1 yêu cầu trả hàng",
     "Reason, status (approved/completed/rejected/requested), refund_amount."),
    ("fact_ad_spend", "fact", "1 row = 1 chi tiêu ads / ngày / channel",
     "Daily spend per campaign × channel (search/display/affiliate/kol). impressions, clicks."),
    ("fact_ad_performance_daily", "fact", "1 row = 1 (ngày × campaign × cat1)",
     "Daily attribution: orders_attributed, gmv_attributed cho campaign theo cat1."),
    ("fact_voucher_usage", "fact", "1 row = 1 voucher dùng trong order",
     "Mapping order ↔ voucher_id, discount_applied. Chỉ orders có platform_voucher > 0."),
    ("fact_traffic_session", "fact", "1 row = 1 session truy cập",
     "Customer (or guest), device, traffic_source, pageviews, duration. has_order = đã chuyển đổi?"),
    ("fact_inventory_weekly", "fact", "1 row = (tuần × product)",
     "Snapshot stock_qty mỗi thứ 2. is_in_stock. Cho ~50% sản phẩm active."),
    ("fact_customer_service_ticket", "fact", "1 row = 1 ticket CS",
     "Category (shipping/quality/refund/...), priority, status, resolved_at."),
    ("dim_date", "dim", "1 row = 1 ngày",
     "Calendar dim: full_date, day, month, year, quarter, week_of_year, is_weekend, is_holiday, is_sale_day."),
    ("dim_location", "dim", "1 row = 1 thành phố VN",
     "20 thành phố lớn VN: city, province, region (north/central/south), is_major_city."),
    ("dim_category", "dim", "1 row = 1 category (4 levels)",
     "Cây 4 cấp: cat1 (Điện Tử / Thời Trang / ...) → cat4 (leaf). full_path để hiển thị."),
    ("dim_customer", "dim", "1 row = 1 user đã đăng ký",
     "Tên, gender, birth_year, signup_date, city, preferred_device, tier (bronze/silver/gold/platinum)."),
    ("dim_seller", "dim", "1 row = 1 shop",
     "shop_name, shop_type (normal/preferred/mall), is_official, seller_city/province."),
    ("dim_product", "dim", "1 row = 1 SKU",
     "product_name, brand (đúng cat1), list_price, launch_date, cat1-4, is_active."),
    ("dim_campaign", "dim", "1 row = 1 chiến dịch",
     "campaign_name (3.3 Mega Sale, Payday Feb...), type, owner_team, start/end_date."),
    ("dim_voucher", "dim", "1 row = 1 voucher code",
     "voucher_code, type (shop/platform/shipping), discount_type (percent/fixed), value, min_order_value, max_discount."),
]


HOWTO = [
    ("1", "Đăng nhập",
     "Mở URL tool (do giảng viên cung cấp). Nhập email → bấm 'Gửi magic link'. Check inbox → click link → vào tool."),
    ("2", "Chạy query đầu tiên",
     "Editor SQL mặc định có query mẫu GMV theo tuần. Bấm ▶ Run hoặc Ctrl+Enter. "
     "Kết quả ra ở panel dưới."),
    ("3", "Tham khảo schema",
     "Sidebar trái có Dataset browser — click bảng để mở danh sách cột. Click cột để insert vào editor."),
    ("4", "Bài tập",
     "Mỗi bài tập có ID (A1, B2, L7...). Đọc Business context + Approach hint trong sheet 'Bài tập'. "
     "Viết SQL trong tool, chạy, so kết quả với Expected shape."),
    ("5", "Tab nhiều query cùng lúc",
     "Bấm + Tab để mở tab mới. Mỗi tab giữ SQL + result riêng. Tabs lưu local nếu reload."),
    ("6", "Format SQL",
     "Bấm ✨ Format để tự động format theo chuẩn (UPPERCASE keyword, comma leading, indent 2 space)."),
    ("7", "Copy / Export kết quả",
     "📋 Copy all (TSV → paste Excel/Sheets) hoặc ⬇ Download CSV. "
     "Click vào số dòng/tên cột để copy cả row/cả cột."),
    ("8", "Sort & Filter",
     "Click ▾ ở header cột → menu Sort A-Z / Z-A / Filter by condition / Filter by values."),
    ("9", "Lịch sử query",
     "Bấm 🕑 History ở header → drawer hiển thị 50 query gần nhất. Click 1 entry → load lại."),
    ("10", "Giới hạn",
     "Mỗi query: timeout 5s, max 1000 dòng / 2 MB payload. Nếu vượt → banner cam cảnh báo."),
    ("11", "Cấu trúc bài tập",
     "12 theme A→L. Mỗi bài có Level (L1=easy, L4=hard). Capstone (L) là tổng hợp."),
    ("12", "Cần giúp đỡ",
     "Đọc Business context + Approach hint trong sheet 'Bài tập'. Vẫn bí → hỏi giảng viên trong group lớp."),
]


# =========================================================================
# 3. WRITE XLSX
# =========================================================================

# Styles
HEADER_FILL = PatternFill("solid", fgColor="F97316")  # cam Shopee
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
TITLE_FONT  = Font(bold=True, size=16, color="0F172A")
SUBTITLE_FONT = Font(italic=True, size=11, color="64748B")
THIN = Side(border_style="thin", color="CBD5E1")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def style_header_row(ws, row_idx, num_cols):
    for col in range(1, num_cols + 1):
        c = ws.cell(row=row_idx, column=col)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = CENTER
        c.border = BORDER


def style_data_rows(ws, start_row, end_row, num_cols):
    for r in range(start_row, end_row + 1):
        for col in range(1, num_cols + 1):
            c = ws.cell(row=r, column=col)
            c.alignment = WRAP
            c.border = BORDER


def set_col_widths(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w


def build_workbook(exercises: list[dict]) -> openpyxl.Workbook:
    wb = openpyxl.Workbook()

    # ---- Sheet 1: Trang chủ ----
    ws = wb.active
    ws.title = "Trang chủ"
    ws["A1"] = "📚 Giáo án — SQL cho Data Analyst (qua case study Shopee)"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:E1")
    ws["A2"] = "Phiên bản gửi học viên · cập nhật theo dataset DA Tool"
    ws["A2"].font = SUBTITLE_FONT
    ws.merge_cells("A2:E2")

    intro = [
        "",
        "🎯 Mục tiêu khoá học",
        "  Sau 32 buổi (4 tháng), học viên có thể tự viết query SQL phân tích dataset thương mại điện tử (Shopee-like),",
        "  đọc số top-line (GMV, AOV, retention), build cohort, đo hiệu quả campaign / voucher / shipping,",
        "  và trình bày insight + recommendation cho stakeholder.",
        "",
        "📅 Cấu trúc khoá",
        "  • Tổng: 32 buổi × ~120 phút",
        "  • Lịch:  2 buổi / tuần × 16 tuần (~ 4 tháng)",
        "  • 4 module:",
        "      - Tháng 1 (B1-B8):    SQL foundation — SELECT, JOIN, GROUP BY",
        "      - Tháng 2 (B9-B16):   Time intelligence + Window functions + CTE",
        "      - Tháng 3 (B17-B24):  Business analytics (RFM, voucher, campaign, marketing, geo…)",
        "      - Tháng 4 (B25-B32):  Operations + Capstone (case study + final presentation)",
        "",
        "📖 Cách dùng file này",
        "  • Sheet 'Lộ trình' — 32 buổi, mỗi buổi 1 chủ đề + bài tập map vào.",
        "  • Sheet 'Bài tập' — 87 bài (12 theme A → L). Mỗi bài có business context + hint, KHÔNG có SQL solution",
        "    (học viên tự viết, giảng viên review qua tool teacher dashboard).",
        "  • Sheet 'Schema' — cheatsheet 18 bảng dataset.",
        "  • Sheet 'Hướng dẫn' — login & dùng tool.",
        "",
        "🛠️ Tool để làm bài",
        "  Web URL do giảng viên cung cấp (Netlify) — login bằng email magic link.",
        "  Mọi query đều log lên server → giảng viên sẽ feedback định kỳ qua teacher dashboard.",
        "",
        "⏱️ Khuyến nghị tiến độ",
        "  • Mỗi buổi: 60 phút lý thuyết + demo, 45 phút thực hành tại lớp, 15 phút Q&A.",
        "  • Bài tập về nhà giữa 2 buổi: 2-3 bài (làm trên tool, log lên server).",
        "  • Mini-project cuối mỗi tháng (B8, B16, B24, B32) → trình bày 5-7 phút.",
    ]
    for i, line in enumerate(intro, start=3):
        ws.cell(row=i, column=1, value=line).alignment = WRAP
        ws.merge_cells(start_row=i, start_column=1, end_row=i, end_column=5)
    ws.column_dimensions["A"].width = 130

    # ---- Sheet 2: Lộ trình ----
    ws2 = wb.create_sheet("Lộ trình")
    headers2 = ["Buổi", "Chủ đề", "Nội dung chính (vắn tắt)", "Theme", "Bài tập"]
    ws2.append(headers2)
    style_header_row(ws2, 1, len(headers2))
    for s in SESSIONS:
        ws2.append(list(s))
    style_data_rows(ws2, 2, len(SESSIONS) + 1, len(headers2))
    set_col_widths(ws2, [6, 38, 70, 12, 22])
    ws2.row_dimensions[1].height = 28
    for r in range(2, len(SESSIONS) + 2):
        ws2.row_dimensions[r].height = 60

    # ---- Sheet 3: Bài tập ----
    ws3 = wb.create_sheet("Bài tập")
    headers3 = ["ID", "Theme", "Title", "Level", "Skills", "Est",
                "Business context", "Approach (hint)", "Expected shape", "Common mistakes"]
    ws3.append(headers3)
    style_header_row(ws3, 1, len(headers3))
    for ex in exercises:
        ws3.append([
            ex["id"],
            f"{ex['theme']} — {ex['theme_name']}",
            ex["title"],
            f"L{ex['level']}",
            ex["skill"],
            ex["est"],
            ex["business_context"],
            ex["approach_hint"],
            ex["expected_shape"],
            ex["common_mistakes"],
        ])
    style_data_rows(ws3, 2, len(exercises) + 1, len(headers3))
    set_col_widths(ws3, [6, 24, 50, 6, 30, 12, 50, 50, 40, 40])
    ws3.row_dimensions[1].height = 30
    for r in range(2, len(exercises) + 2):
        ws3.row_dimensions[r].height = 110
    # Freeze header
    ws3.freeze_panes = "A2"
    # AutoFilter
    ws3.auto_filter.ref = ws3.dimensions

    # ---- Sheet 4: Schema ----
    ws4 = wb.create_sheet("Schema")
    headers4 = ["Bảng", "Nhóm", "Grain (1 row = ?)", "Mô tả ngắn"]
    ws4.append(headers4)
    style_header_row(ws4, 1, len(headers4))
    for s in SCHEMA:
        ws4.append(list(s))
    style_data_rows(ws4, 2, len(SCHEMA) + 1, len(headers4))
    set_col_widths(ws4, [30, 8, 32, 75])
    ws4.row_dimensions[1].height = 28
    for r in range(2, len(SCHEMA) + 2):
        ws4.row_dimensions[r].height = 50

    # ---- Sheet 5: Hướng dẫn ----
    ws5 = wb.create_sheet("Hướng dẫn")
    headers5 = ["#", "Bước", "Mô tả"]
    ws5.append(headers5)
    style_header_row(ws5, 1, len(headers5))
    for h in HOWTO:
        ws5.append(list(h))
    style_data_rows(ws5, 2, len(HOWTO) + 1, len(headers5))
    set_col_widths(ws5, [4, 26, 100])
    ws5.row_dimensions[1].height = 28
    for r in range(2, len(HOWTO) + 2):
        ws5.row_dimensions[r].height = 50

    return wb


def write_csv(path: Path, header: list[str], rows: list[list]):
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def main():
    print(f"Reading exercises from {DOCS}…")
    exercises = parse_all()
    print(f"  Parsed {len(exercises)} exercises across {len(set(e['theme'] for e in exercises))} themes")

    print(f"Building xlsx → {OUT_XLSX}")
    wb = build_workbook(exercises)
    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_XLSX)

    print(f"Writing CSV mirrors → {OUT_CSV_DIR}/")
    OUT_CSV_DIR.mkdir(parents=True, exist_ok=True)

    # exercises.csv
    write_csv(
        OUT_CSV_DIR / "bai_tap.csv",
        ["ID", "Theme", "Title", "Level", "Skills", "Est",
         "Business context", "Approach (hint)", "Expected shape", "Common mistakes"],
        [[e["id"], f"{e['theme']} — {e['theme_name']}", e["title"], f"L{e['level']}",
          e["skill"], e["est"], e["business_context"], e["approach_hint"],
          e["expected_shape"], e["common_mistakes"]] for e in exercises],
    )
    # sessions.csv
    write_csv(
        OUT_CSV_DIR / "lo_trinh.csv",
        ["Buổi", "Chủ đề", "Nội dung chính", "Theme", "Bài tập"],
        [list(s) for s in SESSIONS],
    )
    # schema.csv
    write_csv(
        OUT_CSV_DIR / "schema.csv",
        ["Bảng", "Nhóm", "Grain", "Mô tả ngắn"],
        [list(s) for s in SCHEMA],
    )
    # huong_dan.csv
    write_csv(
        OUT_CSV_DIR / "huong_dan.csv",
        ["#", "Bước", "Mô tả"],
        [list(h) for h in HOWTO],
    )

    print("\n✅ Done.")
    print(f"   {OUT_XLSX} ({OUT_XLSX.stat().st_size // 1024} KB)")
    print(f"   {OUT_CSV_DIR}/ — 4 csv files")


if __name__ == "__main__":
    main()
