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

def _bullets(*items):
    return "\n".join(f"• {i}" for i in items)


SESSIONS = [
    # Mỗi dict: no, week, month, title, objectives (list), homework (list), themes, exercises
    # === THÁNG 1 — SQL FOUNDATION (8 buổi) ===
    {
        "no": 1, "week": 1, "month": 1,
        "title": "Intro tool + dataset Shopee + SELECT cơ bản",
        "objectives": _bullets(
            "Đăng nhập tool, làm quen UI (editor, schema browser, kết quả).",
            "Hiểu cấu trúc schema 'shopee' — phân biệt bảng fact (giao dịch) vs dim (master).",
            "Viết SELECT đơn giản với FROM, WHERE, LIMIT.",
            "Đọc số top-line cơ bản: COUNT(*) số đơn, SUM(total_amount) doanh thu.",
        ),
        "homework": _bullets(
            "Nộp: viết 5 query SELECT trên fact_orders với filter khác nhau (status, payment_method, ngày).",
            "Coi trước: sheet 'Schema' — đọc kỹ dim_date, dim_customer, dim_product.",
            "Chuẩn bị: ghi chú 3 câu hỏi business muốn trả lời từ dataset.",
        ),
        "themes": "—", "exercises": "—",
    },
    {
        "no": 2, "week": 1, "month": 1,
        "title": "ORDER BY, DISTINCT, operators",
        "objectives": _bullets(
            "Sort kết quả với ORDER BY ASC/DESC, sort theo nhiều cột.",
            "Loại trùng với DISTINCT, COUNT(DISTINCT col).",
            "Dùng các operator: IN, BETWEEN, LIKE, IS NULL.",
            "String functions cơ bản: LOWER, UPPER, TRIM, concat ||.",
        ),
        "homework": _bullets(
            "Nộp: list top 20 đơn cao nhất theo total_amount.",
            "Nộp: list distinct payment_method và số đơn mỗi loại.",
            "Nộp: tìm shop có shop_name chứa từ 'Store' (case-insensitive).",
            "Coi trước: khái niệm aggregate (COUNT, SUM, AVG, MIN, MAX).",
        ),
        "themes": "—", "exercises": "(luyện cú pháp)",
    },
    {
        "no": 3, "week": 2, "month": 1,
        "title": "Aggregate functions",
        "objectives": _bullets(
            "Phân biệt COUNT(*), COUNT(col), COUNT(DISTINCT col).",
            "Tính GMV (SUM total_amount), AOV (SUM/COUNT), max/min order.",
            "Hiểu khi nào dùng aggregate function nào cho metric biz.",
        ),
        "homework": _bullets(
            "Nộp: Bài A1, A2 (sheet Bài tập). Lưu ý filter payment_status='paid' khi tính GMV.",
            "Coi trước: GROUP BY là gì, vì sao cần?",
        ),
        "themes": "A", "exercises": "A1, A2",
    },
    {
        "no": 4, "week": 2, "month": 1,
        "title": "GROUP BY + HAVING",
        "objectives": _bullets(
            "GROUP BY 1 cột rồi nhiều cột.",
            "Phân biệt HAVING vs WHERE (filter trước/sau aggregate).",
            "GMV theo ngày/tuần/tháng — sơ lược DATE_TRUNC.",
        ),
        "homework": _bullets(
            "Nộp: Bài A3, A4.",
            "Coi trước: khái niệm JOIN — vì sao cần JOIN nhiều bảng?",
        ),
        "themes": "A", "exercises": "A3, A4",
    },
    {
        "no": 5, "week": 3, "month": 1,
        "title": "INNER JOIN",
        "objectives": _bullets(
            "Hiểu join là gì, vẽ Venn diagram.",
            "JOIN 2 bảng (fact_orders + dim_date), 3 bảng (orders + items + product).",
            "Dùng alias cho dễ đọc; ON condition đúng khoá.",
        ),
        "homework": _bullets(
            "Nộp: Bài A5 (GMV theo cat1), Bài F1.",
            "Coi trước: LEFT JOIN khác INNER chỗ nào? Khi nào cần LEFT?",
        ),
        "themes": "A, F", "exercises": "A5, F1",
    },
    {
        "no": 6, "week": 3, "month": 1,
        "title": "LEFT / RIGHT / FULL JOIN",
        "objectives": _bullets(
            "Khi nào dùng LEFT vs INNER. NULL từ bên không match.",
            "Anti-join pattern: customer chưa từng mua, sản phẩm chưa bán.",
            "LEFT JOIN ... WHERE x IS NULL = NOT EXISTS.",
        ),
        "homework": _bullets(
            "Nộp: Bài B1 (customer chưa quay lại), Bài F2 (sản phẩm bán chậm).",
            "Coi trước: query 5+ bảng — chiến lược tránh nhầm Cartesian.",
        ),
        "themes": "B, F", "exercises": "B1, F2",
    },
    {
        "no": 7, "week": 4, "month": 1,
        "title": "Multi-table JOIN nâng cao",
        "objectives": _bullets(
            "JOIN 4-5 bảng trong 1 query, alias rõ ràng.",
            "Decompose query phức tạp thành step nhỏ.",
            "Phát hiện + tránh Cartesian product (cardinality check).",
        ),
        "homework": _bullets(
            "Nộp: Bài F3 (top SP theo cat), Bài K1 (GMV theo region).",
            "Chuẩn bị mini-project tháng 1: GMV weekly report.",
        ),
        "themes": "F, K", "exercises": "F3, K1",
    },
    {
        "no": 8, "week": 4, "month": 1,
        "title": "Mini-project tháng 1: GMV Weekly Report",
        "objectives": _bullets(
            "Tổng hợp SQL foundation đã học.",
            "Viết end-to-end report GMV weekly với MoM growth.",
            "Trình bày kết quả Google Sheets (paste TSV từ tool).",
        ),
        "homework": _bullets(
            "Nộp: 1 query SQL + 1 trang Google Sheets phân tích insights.",
            "Coi trước: DATE_TRUNC, EXTRACT — chuẩn bị cho tháng 2.",
        ),
        "themes": "A", "exercises": "A6, A7, A8",
    },

    # === THÁNG 2 — TIME INTELLIGENCE + WINDOW + CTE (8 buổi) ===
    {
        "no": 9, "week": 5, "month": 2,
        "title": "DATE_TRUNC, EXTRACT, INTERVAL",
        "objectives": _bullets(
            "DATE_TRUNC ('day', 'week', 'month', 'quarter') — group theo period.",
            "EXTRACT (DOW, HOUR, MONTH) — bóc thành phần.",
            "INTERVAL math: cộng/trừ ngày, tính tuổi đơn.",
            "Pattern theo giờ trong ngày: peak hour, dip hour.",
        ),
        "homework": _bullets(
            "Nộp: Bài C1 (GMV theo giờ), C2 (GMV theo ngày trong tuần).",
            "Coi trước: WoW / MoM growth — cách so sánh kỳ với kỳ.",
        ),
        "themes": "C", "exercises": "C1, C2",
    },
    {
        "no": 10, "week": 5, "month": 2,
        "title": "Time-series: WoW, MoM, YoY growth",
        "objectives": _bullets(
            "So sánh tuần này vs tuần trước (WoW), tháng vs tháng trước (MoM).",
            "Self-join trên dim_date để align period.",
            "Tăng trưởng tuyệt đối (Δ) vs tăng trưởng % (growth rate).",
        ),
        "homework": _bullets(
            "Nộp: Bài C3, C4.",
            "Coi trước: subquery — query lồng nhau, IN / EXISTS.",
        ),
        "themes": "C", "exercises": "C3, C4",
    },
    {
        "no": 11, "week": 6, "month": 2,
        "title": "Subquery cơ bản",
        "objectives": _bullets(
            "Scalar subquery (trả 1 giá trị).",
            "Subquery trong WHERE: IN, NOT IN, EXISTS, NOT EXISTS.",
            "Khi nào nên dùng subquery vs JOIN — trade-off readability vs performance.",
        ),
        "homework": _bullets(
            "Nộp: Bài B2 (customer mua > X đơn), F4 (sản phẩm có rating cao).",
            "Coi trước: CTE (WITH clause) — vì sao CTE tốt hơn nested subquery?",
        ),
        "themes": "B, F", "exercises": "B2, F4",
    },
    {
        "no": 12, "week": 6, "month": 2,
        "title": "CTE — WITH clause",
        "objectives": _bullets(
            "Cú pháp WITH name AS (...) SELECT.",
            "Multi-CTE: WITH a AS (...), b AS (...) — chain logic.",
            "Lợi: dễ đọc, dễ debug, có thể reference nhiều lần.",
        ),
        "homework": _bullets(
            "Nộp: Bài B3 (segment customer), B4 (cohort signup theo tháng).",
            "Coi trước: window function là gì? Khác aggregate chỗ nào?",
        ),
        "themes": "B", "exercises": "B3, B4",
    },
    {
        "no": 13, "week": 7, "month": 2,
        "title": "Window function intro: OVER, PARTITION BY",
        "objectives": _bullets(
            "Khái niệm window: aggregate KHÔNG collapse row.",
            "OVER (PARTITION BY ... ORDER BY ...) — khung tính toán.",
            "Use case: % share trong group, rank trong group.",
        ),
        "homework": _bullets(
            "Nộp: Bài F5 (% GMV mỗi cat trong tổng).",
            "Coi trước: ROW_NUMBER, RANK, DENSE_RANK — khác nhau ra sao?",
        ),
        "themes": "F", "exercises": "F5",
    },
    {
        "no": 14, "week": 7, "month": 2,
        "title": "Ranking: ROW_NUMBER, RANK, DENSE_RANK, NTILE",
        "objectives": _bullets(
            "ROW_NUMBER vs RANK vs DENSE_RANK — handle ties.",
            "Top-N per group (top 5 SP mỗi seller).",
            "NTILE để chia tier (RFM: 5 nhóm Recency/Frequency/Monetary).",
        ),
        "homework": _bullets(
            "Nộp: Bài F6 (top 5 SP mỗi seller), B5 (xếp tier customer).",
            "Coi trước: LAG, LEAD — tính growth rate qua window.",
        ),
        "themes": "F, B", "exercises": "F6, B5",
    },
    {
        "no": 15, "week": 8, "month": 2,
        "title": "LAG, LEAD, running total, moving average",
        "objectives": _bullets(
            "LAG để tính growth %: (this - prev) / prev.",
            "LEAD để check next event (next purchase, next session).",
            "SUM(...) OVER (ORDER BY ... ROWS BETWEEN ...) cho running total / MA-7.",
        ),
        "homework": _bullets(
            "Nộp: Bài A8 extension (MoM growth qua LAG), B6 (thời gian giữa 2 đơn).",
            "Chuẩn bị mini-project tháng 2: cohort retention.",
        ),
        "themes": "A, B", "exercises": "A8 ext, B6",
    },
    {
        "no": 16, "week": 8, "month": 2,
        "title": "Mini-project tháng 2: Cohort retention 7/30",
        "objectives": _bullets(
            "Tổng hợp time + window + CTE.",
            "Build cohort matrix: signup_month × tháng quay lại.",
            "Tính retention rate 7d / 30d / 90d.",
        ),
        "homework": _bullets(
            "Nộp: 1 query cohort + bảng matrix paste vào Google Sheets.",
            "Coi trước: RFM segmentation — recency/frequency/monetary.",
        ),
        "themes": "B", "exercises": "B7, B8, B9",
    },

    # === THÁNG 3 — BUSINESS ANALYTICS (8 buổi) ===
    {
        "no": 17, "week": 9, "month": 3,
        "title": "RFM customer segmentation",
        "objectives": _bullets(
            "RFM = Recency × Frequency × Monetary.",
            "Dùng NTILE chia 5 tier mỗi dimension → 125 segment.",
            "Rút gọn 125 → 4-5 nhóm chính (Champion, Loyal, At-risk, Lost…).",
        ),
        "homework": _bullets(
            "Nộp: query RFM + danh sách 100 'Champion customer' để remarketing.",
            "Coi trước: voucher analysis — redemption rate là gì?",
        ),
        "themes": "B", "exercises": "(B mở rộng)",
    },
    {
        "no": 18, "week": 9, "month": 3,
        "title": "Voucher / promotion analysis",
        "objectives": _bullets(
            "Voucher redemption rate = (used / issued).",
            "Avg discount per order, total discount cost.",
            "Voucher có drive incremental orders, hay chỉ subsidize organic?",
        ),
        "homework": _bullets(
            "Nộp: Bài D1, D2, D3, D4.",
            "Coi trước: campaign uplift — đo hiệu quả campaign so với baseline.",
        ),
        "themes": "D", "exercises": "D1-D4",
    },
    {
        "no": 19, "week": 10, "month": 3,
        "title": "Campaign uplift",
        "objectives": _bullets(
            "Compare campaign period vs baseline (3 tuần trước cùng kỳ).",
            "Cẩn thận seasonality, lễ tết.",
            "Self-join hoặc CTE để tính uplift %.",
        ),
        "homework": _bullets(
            "Nộp: Bài C5, C6, C7, D5, D6, D7.",
            "Coi trước: ROAS = Return on Ad Spend, CTR, CPC.",
        ),
        "themes": "C, D", "exercises": "C5-C7, D5-D7",
    },
    {
        "no": 20, "week": 10, "month": 3,
        "title": "Marketing: ROAS, CTR, CPC",
        "objectives": _bullets(
            "JOIN fact_ad_spend × fact_ad_performance_daily.",
            "Tính ROAS (revenue/spend), CTR (clicks/impressions), CPC (spend/clicks).",
            "So sánh hiệu quả channel: search vs display vs affiliate vs KOL.",
        ),
        "homework": _bullets(
            "Nộp: Bài G1, G2, G3, G4.",
            "Coi trước: seller performance — long tail vs head sellers.",
        ),
        "themes": "G", "exercises": "G1-G4",
    },
    {
        "no": 21, "week": 11, "month": 3,
        "title": "Seller performance",
        "objectives": _bullets(
            "Top sellers theo GMV / units sold / AOV.",
            "Pareto 80/20: top 20% sellers chiếm bao nhiêu % GMV?",
            "Shop_type (mall / preferred / normal) ảnh hưởng GMV / cancel rate?",
        ),
        "homework": _bullets(
            "Nộp: Bài E1, E2, E3, E4.",
            "Coi trước: product / category trends — cat nào growth nhất?",
        ),
        "themes": "E", "exercises": "E1-E4",
    },
    {
        "no": 22, "week": 11, "month": 3,
        "title": "Product / Category trends",
        "objectives": _bullets(
            "Cat1 nào growth GMV nhanh nhất 3 tháng qua?",
            "Brand contribution: top brand mỗi cat1.",
            "Pareto trên SKU level — 20% SKU sinh 80% GMV?",
        ),
        "homework": _bullets(
            "Nộp: Bài F7, F8.",
            "Coi trước: geographic analysis — region/province.",
        ),
        "themes": "F", "exercises": "F7, F8",
    },
    {
        "no": 23, "week": 12, "month": 3,
        "title": "Geographic analysis",
        "objectives": _bullets(
            "GMV theo region (north/central/south).",
            "Penetration rate: % customer / population (giả định population).",
            "Province nào tỷ lệ cancel cao bất thường? (red flag).",
        ),
        "homework": _bullets(
            "Nộp: Bài K1, K2, K3, K4, K5.",
            "Chuẩn bị mini-project tháng 3: marketing dashboard.",
        ),
        "themes": "K", "exercises": "K1-K5",
    },
    {
        "no": 24, "week": 12, "month": 3,
        "title": "Mini-project tháng 3: Marketing Dashboard",
        "objectives": _bullets(
            "Tổng hợp business analytics đã học.",
            "Build dashboard: top campaign, top seller, top SKU, ROAS theo channel.",
            "Trình bày bằng số + chart suggestion (loại chart nào cho metric nào).",
        ),
        "homework": _bullets(
            "Nộp: Google Sheets dashboard 1 trang + insight 3-5 bullet.",
            "Coi trước: shipping & SLA — on-time rate là gì.",
        ),
        "themes": "C, D, E, G", "exercises": "(tổng hợp)",
    },

    # === THÁNG 4 — OPERATIONS + CAPSTONE (8 buổi) ===
    {
        "no": 25, "week": 13, "month": 4,
        "title": "Shipping & SLA analysis",
        "objectives": _bullets(
            "On-time delivery rate = is_on_time / total shipments.",
            "SLA breach theo carrier, theo route (intra-city / cross-region).",
            "Avg delivery time + p90/p95.",
        ),
        "homework": _bullets(
            "Nộp: Bài H1, H2, H3, H4.",
            "Coi trước: cancel/return analysis — pattern lý do hủy.",
        ),
        "themes": "H", "exercises": "H1-H4",
    },
    {
        "no": 26, "week": 13, "month": 4,
        "title": "Cancellation & return analysis",
        "objectives": _bullets(
            "Cancel rate theo lý do, theo seller, theo cat1.",
            "Return reason analysis — top 3 lý do return.",
            "Buyer cancel (customer_change_mind) vs seller cancel (out_of_stock) — phân biệt.",
        ),
        "homework": _bullets(
            "Nộp: Bài I1, I2, I3, I4.",
            "Coi trước: customer service tickets — category breakdown.",
        ),
        "themes": "I", "exercises": "I1-I4",
    },
    {
        "no": 27, "week": 14, "month": 4,
        "title": "Customer service tickets",
        "objectives": _bullets(
            "Ticket category distribution: shipping vs quality vs refund.",
            "Avg resolution time (resolved_at - created_at).",
            "Seller nào nhiều complaint nhất — correlation với cancel/return.",
        ),
        "homework": _bullets(
            "Nộp: Bài J1, J2, J3, J4, J5.",
            "Coi trước: advanced patterns — FILTER, conditional aggregate.",
        ),
        "themes": "J", "exercises": "J1-J5",
    },
    {
        "no": 28, "week": 14, "month": 4,
        "title": "Advanced SQL patterns",
        "objectives": _bullets(
            "FILTER (WHERE ...) trong aggregate — pivot bằng FILTER.",
            "CASE WHEN trong SUM/COUNT để conditional metric.",
            "Cú pháp pivot manual: SUM(CASE WHEN cat='X' THEN ...) AS x_gmv.",
        ),
        "homework": _bullets(
            "Nộp: Bài L1, L2 (capstone — chuẩn bị).",
            "Coi trước: EXPLAIN — đọc execution plan cơ bản.",
        ),
        "themes": "L", "exercises": "L1, L2",
    },
    {
        "no": 29, "week": 15, "month": 4,
        "title": "Performance & EXPLAIN",
        "objectives": _bullets(
            "EXPLAIN cơ bản — đọc plan output.",
            "Vì sao query chậm: full scan, missing index, bad join order.",
            "Best practice: filter sớm, tránh SELECT *, dùng index column trong WHERE.",
        ),
        "homework": _bullets(
            "Nộp: 3 query đã optimize (kèm EXPLAIN trước/sau).",
            "Bốc 1 case study từ theme L cho capstone (sẽ làm 2 buổi).",
        ),
        "themes": "—", "exercises": "(thực hành EXPLAIN)",
    },
    {
        "no": 30, "week": 15, "month": 4,
        "title": "Capstone — Phần 1: phân rã & draft query",
        "objectives": _bullets(
            "Định nghĩa câu hỏi business của capstone.",
            "Phân rã thành 3-5 sub-question.",
            "Viết draft SQL cho từng sub-question.",
        ),
        "homework": _bullets(
            "Nộp: outline capstone + draft query (chưa cần hoàn thiện).",
            "Coi trước: cách viết insight + recommendation.",
        ),
        "themes": "L", "exercises": "L3-L8 (tự chọn 1)",
    },
    {
        "no": 31, "week": 16, "month": 4,
        "title": "Capstone — Phần 2: hoàn thiện + viết insight",
        "objectives": _bullets(
            "Validate kết quả query: cross-check số, edge case.",
            "Viết insight (số nói gì) + recommendation (nên làm gì).",
            "Format slide / Sheets cho final presentation.",
        ),
        "homework": _bullets(
            "Nộp: Google Slides / Sheets capstone hoàn chỉnh (5-7 slide).",
            "Chuẩn bị: trình bày 5-7 phút buổi sau.",
        ),
        "themes": "L", "exercises": "L9-L14",
    },
    {
        "no": 32, "week": 16, "month": 4,
        "title": "Final presentation + Q&A + Tổng kết khoá",
        "objectives": _bullets(
            "Mỗi học viên trình bày capstone 5-7 phút.",
            "Q&A từ giảng viên + bạn cùng lớp.",
            "Tổng kết: skill đã học, roadmap nâng cao (analytics engineer, BI dev).",
        ),
        "homework": _bullets(
            "Final: bản capstone v2 (sau feedback).",
            "Roadmap nâng cao: học dbt, đọc 'SQL for Data Analysts' (Cathy Tanimura).",
        ),
        "themes": "L", "exercises": "L15-L17",
    },
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
    headers2 = ["Buổi", "Tuần", "Tháng", "Chủ đề", "Mục tiêu buổi học", "Bài tập về nhà", "Theme", "Bài tập map"]
    ws2.append(headers2)
    style_header_row(ws2, 1, len(headers2))
    for s in SESSIONS:
        ws2.append([
            s["no"], s["week"], f"Tháng {s['month']}", s["title"],
            s["objectives"], s["homework"], s["themes"], s["exercises"],
        ])
    style_data_rows(ws2, 2, len(SESSIONS) + 1, len(headers2))
    set_col_widths(ws2, [6, 6, 9, 40, 70, 70, 10, 16])
    ws2.row_dimensions[1].height = 30
    for r in range(2, len(SESSIONS) + 2):
        ws2.row_dimensions[r].height = 130
    ws2.freeze_panes = "A2"
    ws2.auto_filter.ref = ws2.dimensions

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
        ["Buổi", "Tuần", "Tháng", "Chủ đề", "Mục tiêu buổi học", "Bài tập về nhà", "Theme", "Bài tập map"],
        [[s["no"], s["week"], f"Tháng {s['month']}", s["title"],
          s["objectives"], s["homework"], s["themes"], s["exercises"]] for s in SESSIONS],
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
