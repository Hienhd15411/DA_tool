# Session State — Snapshot 2026-06-14

Doc này lưu trạng thái project ở cuối session để continue được từ session mới. Update mỗi khi có milestone lớn.

---

## 1. Git state

### Branches

| Branch | Vai trò | Commit mới nhất |
|---|---|---|
| `claude/review-continue-editing-UOeCU` | **Feature branch** — có tất cả fix + feature từ session này | `2eccb5e` |
| `claude/sql-learning-tool-rQoRj` | **Default branch** — chỉ có workflow files copy sang (để Actions UI register) | `4992f7e` |

### Netlify config (kiểm tra định kỳ)

- **Production branch**: nên là `claude/review-continue-editing-UOeCU` (feature — có frontend fixes)
- Nếu Production branch = default → cần merge feature → default để frontend update

### Timeline commits chính (session này)

```
2eccb5e  feat(backup): 2 workflow backup/restore shopee data
0b86e3d  feat(run_sql): bump cap 15s/48MB → 60s/128MB (cho lớp 2 user)
bbabf6f  chore: update comment cuối migration
0956074  feat(run_sql): bump cap 5s/16MB → 15s/48MB
47b52b4  fix(run_sql): trả thêm 'columns' array để fix JS reorder numeric keys
e0e444d  fix(run_sql): JSON thay JSONB → giữ đúng thứ tự cột user SELECT
b668a81  fix(seed): order_id strict monotonic theo created_at
5457ed3  fix(seed): deep review — 8 logic bug ở 7 generator
dd62bb9  fix(seed): dim_product brand khớp cat1 + tên sản phẩm realistic
1d2e0a0  feat(ux): 8 improvements — autocomplete, format, sort/filter, 1000 rows
9d3c2dc  feat(ui): copy/export kết quả query — 4 format + download CSV
5825431  fix(critical): run_sql security hardening + data-loss prevention
```

---

## 2. Dataset hiện tại

- **DB size**: ~178 MB / 500 MB free tier limit
- **Range**: 2024-02-01 → 2024-04-30 (89 ngày, 3 tháng)
- **Volumes**: 25k customers, 3k sellers, 15k products, ~135k orders, ~234k items, ~170k sessions
- **Sale days config**: 3/3, 4/4 only
- **Trend factors**: Mar ×0.88, Apr ×0.82 (dạy A3 — post-Tết slump)
- **Config file**: `seed/config.yml` (giữ nguyên state cũ, chưa extend)

---

## 3. run_sql function state (migration 006)

**Caps hiện tại:**
- `statement_timeout`: **60s**
- `work_mem`: **128MB**
- `MAX_ROWS`: **1000**
- `MAX_RESULT_BYTES`: **2 MB**

**Return type**: `JSON` (không phải JSONB — preserve column order)

**Response fields**:
```json
{
  "status": "ok",
  "columns": ["col1", "col2", ...],  // NEW — preserve order for JS
  "rows": [{...}, ...],
  "row_count": N,
  "exec_ms": N,
  "truncated": bool,
  "notice": "...",
  "max_rows": 1000
}
```

**Security model**: SECURITY INVOKER + authenticated role có SELECT trên shopee.* + INSERT trên learning.query_log. Chặn multi-statement `;`, whitelist SELECT/WITH/EXPLAIN, chỉ bare EXPLAIN.

---

## 4. Frontend tool state

**Latest commit trên feature branch**: `2eccb5e`

**Features đã có**:
- Multi-tab editor (persist localStorage `datool.tabs.v1`)
- Ctrl+Enter chạy query (fix stale closure bằng useRef)
- Run selection nếu có bôi đen
- Format SQL (sql-formatter, lazy-load)
- Copy TSV/CSV/MD/JSON + Download CSV
- Result table: sort, filter (per column menu), row# copy, cell copy
- Column selection persistent (click header)
- Column menu (Google Sheets style)
- Native drag-select preserved (drag detect + hasTextSelection guard)
- Autocomplete DISABLED (Monaco quiet mode)
- Uncontrolled Monaco (tránh nhảy chữ khi gõ nhanh)
- Auto-close brackets/quotes OFF (tránh conflict Vietnamese Telex)
- Debounced localStorage write 500ms
- 🕑 History drawer
- 👨‍🏫 Teacher dashboard (chỉ hiện nếu email trong `public.teacher_emails`)
- Schema browser sidebar hide/show
- Resizable editor/result split
- Status bar hint

**Teacher whitelist đã seed**: `hienhd15411@gmail.com` (migration 010)

---

## 5. Workflows GitHub Actions

Đang đăng ký (default branch):
1. **Keep Supabase alive** — cron weekly (chống pause 7 ngày idle)
2. **Seed database** — manual (mode: full/migrate/data/reset)
3. **Backup shopee data** — manual, tạo GitHub Release
4. **Restore shopee data** — manual, restore từ release

Trên feature branch còn có (chưa merge sang default):
- Các file source đã có, nhưng backup + restore đã copy sang default rồi.

---

## 6. Đang chờ user action

### ⏳ Chờ user click backup workflow

**→ https://github.com/Hienhd15411/DA_tool/actions/workflows/backup-shopee.yml**

- Click Run workflow
- Branch: `claude/sql-learning-tool-rQoRj`
- tag_name: `dataset-v1-3month`
- note: `89 ngay Feb-Apr, 135k orders, ~178MB`

Sau khi xanh → check https://github.com/Hienhd15411/DA_tool/releases

---

## 7. Next steps (đang pending)

Sau khi backup xong, các option sẽ triển khai (chưa quyết định thứ tự):

### A. Extend data range Feb → Jul 2024 (Phương án A)
User đã confirm. Plan:
1. `seed/config.yml`: extend end 2024-07-31, sale_days [3.3, 4.4, 5.5, 6.6, 7.7], holidays thêm 30/4 + 1/5, vouchers 800, ad_campaigns 80
2. `gen_fact_orders.py`: trend `{2:1.00, 3:0.92, 4:0.95, 5:1.10, 6:1.25, 7:1.20}`, bỏ heuristic `d.day == d.month`, pre-group seller_products
3. `gen_dim_date.py`: bỏ heuristic, chỉ check `d in sale_days`
4. `gen_dim_voucher.py`: spread `v_from` across full range
5. `gen_fact_returns.py`: fallback delivered_at → created_at + 5 days
6. `.github/workflows/cleanup-query-log.yml` (mới): retention 30 ngày
7. `docs/exercises/A-revenue-gmv.md`: A3 -8% + extension Jun peak

Sau đó chạy `seed database` workflow mode=**reset** (~30-40 phút).

### B. Materialized views cho query nặng
- `shopee.mv_daily_churn`
- `shopee.mv_daily_gmv`
- Refresh cron weekly

### C. Curriculum + student exercises files
Đã có:
- `docs/giao_an_hoc_vien.xlsx` (32 buổi lộ trình + BT về nhà)
- `docs/bai_tap_hoc_vien.xlsx` (5 cột: tên bài, độ khó, thời gian, skill, business context)

Có thể regenerate:
```bash
python3 seed/gen_student_curriculum.py
python3 seed/gen_student_exercises.py
```

### D. Power BI integration
- Đã có hướng dẫn connect Session pooler port 5432
- User cần tự tạo `pbi_reader` role (SQL trong hướng dẫn README)

---

## 8. Known limitations & workarounds

| Limitation | Workaround |
|---|---|
| Timeout 60s (hard cap by PostgREST HTTP) | Materialized views cho query nặng |
| Không tạo được temp table (RPC transaction isolation) | `WITH ... AS MATERIALIZED (...)` — CTE cached |
| Không dùng được `DO $$ ... $$` / BEGIN loops | Rewrite as CTE + window function (declarative) |
| MCP GitHub không trigger được workflow_dispatch (403) | User phải click UI |
| Git tag push bị 403 (git proxy limit) | Tag trên GitHub UI, hoặc dùng commit SHA làm reference |
| `;` không cho phép ở giữa query (chống inject) | Bỏ trailing `;`, KHÔNG dùng multi-statement |

---

## 9. Files quan trọng (đọc kỹ khi resume session)

- `seed/config.yml` — dataset config
- `seed/generators/*.py` — 15 generators
- `seed/migrations/*.sql` — 10 migration files (chú ý 006 = run_sql, 010 = teacher)
- `web/src/App.tsx` — main workbench
- `web/src/components/*.tsx` — 8 components
- `web/src/lib/*.ts` — hooks + utils
- `.github/workflows/*.yml` — 4 workflows
- `docs/UAT.md` — UAT checklist
- `docs/exercises/*.md` — 87 bài tập
- `docs/SESSION_STATE.md` — file này

---

## 10. Contact / project info

- **Owner email**: hienhd15411@gmail.com (seed vào teacher_emails)
- **GitHub**: https://github.com/Hienhd15411/DA_tool
- **Netlify site**: đã config nhưng URL không được lưu ở đây (user tự nhớ)
- **Supabase project**: Free tier, region SG (ap-southeast-1)
