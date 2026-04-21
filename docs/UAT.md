# UAT Checklist — Go-live

Chạy từ trên xuống dưới. **Tất cả phải ✅ trước khi go-live thực tế.**
Mỗi mục ghi rõ: chạy ở đâu (Supabase SQL Editor / Netlify site / GitHub Actions / local terminal), kết quả kỳ vọng, và cách khắc phục nếu fail.

> Ước lượng thời gian: ~45 phút cho full pass đầu tiên, ~10 phút cho re-run sau mỗi thay đổi.

---

## 0. Pre-flight — tài nguyên đã sẵn sàng

| # | Kiểm tra | OK khi |
|---|---|---|
| 0.1 | Supabase project đã tạo, status = `ACTIVE` | Dashboard → project list hiển thị xanh lá |
| 0.2 | `DATABASE_URL` secret đã add trong GitHub repo | Settings → Secrets and variables → Actions liệt kê `DATABASE_URL` |
| 0.3 | `SUPABASE_URL` + `SUPABASE_ANON_KEY` secret đã add (cho keep-alive) | Cùng page trên |
| 0.4 | Netlify site đã import repo | Netlify dashboard → site status `Published` |
| 0.5 | Netlify env vars `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` đã set | Site settings → Environment variables |

---

## 1. Seed data — GitHub Actions

| # | Step | Expected | Nếu fail |
|---|---|---|---|
| 1.1 | Repo → Actions → `Seed database` → Run workflow, mode=`full`, import_exercises=`true` | Workflow xanh sau ~20 phút | Xem log step "Run seed": thường lỗi FK hoặc DATABASE_URL. |
| 1.2 | Ở cuối workflow log có bảng "schema │ table │ rows" | Liệt kê **18 bảng shopee + 3 bảng learning**, rows > 0 cho tất cả | Nếu `shopee.fact_orders` = 0 → seed fail giữa chừng, re-run với mode=`reset` |
| 1.3 | Tối thiểu row counts (sanity check): `dim_customer ≥ 25k`, `dim_product ≥ 15k`, `fact_orders ≥ 130k`, `fact_order_items ≥ 250k` | Match | Giảm `volumes` trong `seed/config.yml` nếu DB quá gần 500MB limit |

**Test thủ công từ Supabase SQL Editor:**

```sql
-- UAT 1.4: tất cả bảng đã có data
SELECT schemaname, relname, n_live_tup
FROM pg_stat_user_tables
WHERE schemaname IN ('shopee','learning','public')
ORDER BY schemaname, relname;

-- UAT 1.5: FK chain hoạt động
SELECT COUNT(*) FROM shopee.fact_order_items i
JOIN shopee.fact_orders o ON o.order_id = i.order_id;  -- phải > 0 và không lỗi

-- UAT 1.6: exercise đã import
SELECT theme, COUNT(*) FROM public.exercise GROUP BY 1 ORDER BY 1;
-- kỳ vọng ~12 theme (A..L), tổng ~87 bài
```

---

## 2. Role & Grant — Supabase SQL Editor

| # | Query | Expected |
|---|---|---|
| 2.1 | `SELECT has_schema_privilege('authenticated', 'shopee', 'USAGE');` | `t` |
| 2.2 | `SELECT has_table_privilege('authenticated', 'shopee.fact_orders', 'SELECT');` | `t` |
| 2.3 | `SELECT has_table_privilege('authenticated', 'shopee.fact_orders', 'INSERT');` | `f` |
| 2.4 | `SELECT has_table_privilege('authenticated', 'shopee.fact_orders', 'UPDATE');` | `f` |
| 2.5 | `SELECT has_table_privilege('authenticated', 'shopee.fact_orders', 'DELETE');` | `f` |
| 2.6 | `SELECT has_function_privilege('authenticated', 'public.run_sql(text,text)', 'EXECUTE');` | `t` |
| 2.7 | `SELECT has_function_privilege('anon', 'public.get_schema_info()', 'EXECUTE');` | `t` |
| 2.8 | `SELECT rowsecurity FROM pg_tables WHERE schemaname='learning' AND tablename='query_log';` | `t` |

Nếu bất kỳ dòng nào sai → re-run `python seed.py --mode=migrate` hoặc workflow mode=`migrate`.

---

## 3. run_sql — Security & Functional (quan trọng nhất)

**Cần:** login một user thật, lấy JWT, hoặc test qua Supabase SQL Editor (set `request.jwt.claims`).

**Cách nhanh: chạy từ frontend sau khi login, xem Network tab browser.**

### 3.A Functional cases (phải chạy OK)

| # | Query | Kỳ vọng |
|---|---|---|
| 3.A.1 | `SELECT 1 AS x` | status=ok, rows=`[{"x":1}]` |
| 3.A.2 | `SELECT 1 AS x;` (trailing `;`) | status=ok (không lỗi syntax) |
| 3.A.3 | `SELECT generate_series(1,20) AS n LIMIT 5` (user LIMIT) | status=ok, row_count=5 |
| 3.A.4 | `WITH t AS (SELECT 1 x) SELECT x FROM t` | status=ok |
| 3.A.5 | `-- comment\nSELECT 1` (leading comment) | status=ok |
| 3.A.6 | `SELECT 1 -- inline` (trailing comment) | status=ok |
| 3.A.7 | `EXPLAIN SELECT * FROM shopee.dim_customer` | status=ok, rows chứa plan |
| 3.A.8 | Query JOIN dim_date + fact_orders group theo tuần | status=ok, có data |
| 3.A.9 | `SELECT * FROM shopee.fact_orders` (600k+ rows) | status=ok, truncated=true, row_count=1000, exec_ms < 3000 |
| 3.A.10 | Chạy query cố tình nặng: `SELECT pg_sleep(10)` | status=error, error_code=57014 (statement_timeout) sau ~5s |
| 3.A.11 | `SELECT generate_series(1,1500) AS n` | truncated=true, row_count=1000, banner cam hiển thị "⚠️ Đã cắt tại 1000/1000 dòng" |
| 3.A.12 | `SELECT generate_series(1,1000) AS n, repeat('x', 10000) AS big` (10MB payload) | truncated=true, row_count < 1000, notice panel cam hiển thị "💡 Kết quả ... KB vượt ngưỡng 2048 KB" |

### 3.B Security cases (phải CHẶN)

| # | Query | Kỳ vọng |
|---|---|---|
| 3.B.1 | `SELECT 1); DROP TABLE shopee.dim_customer; SELECT (1` | RPC error: "Multiple statements not allowed" |
| 3.B.2 | `UPDATE shopee.dim_customer SET tier='platinum'` | RPC error: "Only SELECT/WITH/EXPLAIN are allowed" |
| 3.B.3 | `DELETE FROM shopee.fact_orders` | Same as 3.B.2 |
| 3.B.4 | `DROP TABLE shopee.fact_orders` | Same as 3.B.2 |
| 3.B.5 | `WITH x AS (DELETE FROM shopee.fact_orders RETURNING *) SELECT * FROM x` | status=error, "WITH clause containing a data-modifying statement must be at the top level" |
| 3.B.6 | `EXPLAIN ANALYZE SELECT 1` | RPC error: "Only bare EXPLAIN SELECT/WITH allowed" |
| 3.B.7 | `-- comment only` (không SELECT gì) | RPC error: "Empty query" |
| 3.B.8 | Query dài 10MB | RPC error hoặc HTTP 413. Không crash server. |
| 3.B.9 | Sau tất cả 3.B, chạy `SELECT COUNT(*) FROM shopee.fact_orders` | Vẫn trả số đúng (data không bị xoá) |

### 3.C RLS cho query_log

| # | Test | Kỳ vọng |
|---|---|---|
| 3.C.1 | User A login, chạy 3 query; User B login, chạy `SELECT * FROM learning.query_log` qua run_sql | User B **không thấy** log của User A (RLS filter). Chỉ thấy của chính mình. |
| 3.C.2 | Từ Supabase SQL Editor (role = postgres): `SELECT user_id, COUNT(*) FROM learning.query_log GROUP BY 1` | Thấy cả A và B riêng biệt |

---

## 4. Frontend — Netlify deploy

**URL test:** `https://<your-site>.netlify.app`

| # | Step | Kỳ vọng | Fix nếu fail |
|---|---|---|---|
| 4.1 | Mở URL lần đầu (chưa login) | Thấy form "DA Tool — Đăng nhập" với input email | Nếu blank page → check Console → thường do env vars. Set lại và **Clear cache and redeploy**. |
| 4.2 | Nhập email, click "Gửi magic link" | Thấy "✉️ Đã gửi email. Check inbox rồi click link" | Nếu error → Supabase → Authentication → URL config thiếu redirect URL. Add `https://<site>.netlify.app/**`. |
| 4.3 | Click magic link trong email | Browser tab redirect về site, đã login (thấy email ở header) | Nếu redirect sai → same như 4.2 |
| 4.4 | Sidebar trái hiển thị schema browser với **18 bảng shopee** (nhóm fact / dim), mỗi bảng có row count | Hiển thị đầy đủ | Nếu sidebar trống → check Network → `get_schema_info` trả mảng rỗng → chạy migration 009. Nếu rows=0 → chạy `ANALYZE` trên tất cả bảng shopee. |
| 4.5 | Click một bảng → expand columns | Thấy list cột, type, NOT NULL marker | |
| 4.6 | Click tên bảng trong sidebar → chữ `shopee.table_name` được insert vào editor tại cursor | Insert đúng chỗ | |
| 4.7 | Click tên cột → chỉ tên cột insert | | |
| 4.8 | Search box: gõ "order" → chỉ thấy bảng/cột match | Filter hoạt động | |
| 4.9 | Trong editor, giữ nguyên query mẫu, nhấn **Ctrl/Cmd+Enter** | Bảng kết quả hiện GMV theo tuần | Nếu error 401 → session hết hạn, reload. |
| 4.10 | Thử query không qualified: `SELECT * FROM dim_customer LIMIT 10` | Chạy OK (search_path = shopee) | |
| 4.11 | Thử query lỗi: `SELECT * FROM nonexistent` | Panel dưới hiện error đỏ, query vẫn được log | |
| 4.12 | Click "Xoá" | Editor empty, panel kết quả reset | |
| 4.13 | Click "Đăng xuất" | Về lại form login | |
| 4.14 | Sau khi chạy query OK, header kết quả có 5 nút: **📋 TSV**, **📋 CSV**, **📋 MD**, **📋 JSON**, **⬇ CSV** | Đủ 5 nút | |
| 4.15 | Click **📋 TSV** → paste (Ctrl+V) vào Excel / Google Sheets | Dữ liệu rơi đúng cột | Clipboard API có thể bị block trên HTTP, Netlify luôn HTTPS nên OK |
| 4.16 | Click **📋 CSV** → paste vào notepad | Dữ liệu comma-separated, có quote cho cell chứa `,` hoặc `\n` | |
| 4.17 | Click **📋 MD** → paste vào GitHub comment hoặc Notion | Hiển thị thành table Markdown | |
| 4.18 | Click **📋 JSON** → paste vào editor | JSON array đẹp, indent 2 space | |
| 4.19 | Click **⬇ CSV** → download file | File `query_result_YYYY-MM-DD-HH-MM-SS.csv` tải xuống, mở bằng Excel hiển thị Unicode đúng (BOM) | |
| 4.20 | Kéo chuột chọn vài ô → Ctrl+C → paste vào Excel | Chỉ ô chọn paste vào, giữ đúng cột | Nếu paste text joined tab → normal; nếu cột lộn → bug selection |
| 4.21 | Click nút **+ Tab** ở trên editor | Tab mới "Query 2" hiện, editor trống, tab cũ vẫn còn | |
| 4.22 | Switch qua lại giữa tabs | Mỗi tab giữ SQL + kết quả riêng | |
| 4.23 | Double-click tên tab | Prompt đổi tên | |
| 4.24 | Click `×` trên tab | Confirm → đóng tab, chuyển sang tab kế | Không đóng được nếu chỉ còn 1 tab |
| 4.25 | Reload browser (F5) | Tabs giữ nguyên (localStorage), nhưng result trống (phải run lại) | |
| 4.26 | Click nút **◂ Ẩn** trên Dataset browser | Sidebar co lại thành strip mỏng 32px với nút "▸ Dataset" | |
| 4.27 | Click **▸ Dataset** trên strip | Sidebar mở lại full 300px | Trạng thái nhớ sau reload (localStorage) |
| 4.28 | Click nút **✨ Format** với query xấu | SQL được format: keyword UPPERCASE, comma leading, indent 2 space | Nếu SQL syntax error → alert |
| 4.29 | Bôi đen đoạn SQL → Ctrl+Enter | Chỉ đoạn đó chạy | Hint hiện ở status bar |
| 4.30 | Gõ `SELECT * FROM ` trong editor → Ctrl+Space | Popup gợi ý hiện các table `shopee.*` | Monaco autocomplete |
| 4.31 | Gõ tên 1 column → Ctrl+Space | Popup gợi ý column names + type | |
| 4.32 | Gõ `SEL` → popup hiện snippets như "SELECT …" | Snippet skeleton insert được | |
| 4.33 | Click header cột trong result | Toggle sort: click 1 = ASC, click 2 = DESC, click 3 = no sort | Mũi tên ▲/▼ hiện bên cạnh tên cột |
| 4.34 | Gõ vào ô filter dưới header | Rows lọc real-time, chỉ giữ row chứa substring (case-insensitive) | "Lọc X/Y" hiện ở header |
| 4.35 | Click vào 1 cell bất kỳ trong bảng | Giá trị cell copied vào clipboard, cell flash cam | Paste vào đâu đó verify |
| 4.36 | Click **📋 Copy all** | Toàn bộ rows đã filter+sort copy sang clipboard (TSV) | Paste vào Excel giữ cột |
| 4.37 | Click **⬇ Download CSV** | File .csv tải về với BOM, mở bằng Excel OK Unicode | |
| 4.38 | Click **🕑 History** ở header | Drawer bên phải mở, hiển thị query history (tối đa 50) | |
| 4.39 | Click 1 entry trong history | Tạo tab mới với SQL đó, drawer đóng | |
| 4.40 | Kéo thanh ngang giữa editor và result | 2 panel resize, % lưu vào localStorage | |
| 4.41 | Reload trang | Tabs, schema collapsed, split % giữ nguyên | |

---

## 3.D Teacher dashboard

**Điều kiện:** email của user phải trong `public.teacher_emails`. Admin setup:

```sql
-- Supabase SQL Editor
INSERT INTO public.teacher_emails (email) VALUES ('teacher@your-school.com');
```

Sau đó teacher login, nút **👨‍🏫 Teacher** xuất hiện ở header.

| # | Step | Kỳ vọng |
|---|---|---|
| 3.D.1 | Student login (email chưa add whitelist) | Không thấy nút 👨‍🏫 Teacher |
| 3.D.2 | Student gọi `SELECT public.is_teacher()` trong editor | Trả `false` |
| 3.D.3 | Teacher login | Thấy nút 👨‍🏫 Teacher ở header |
| 3.D.4 | Click 👨‍🏫 Teacher | Modal mở, hiển thị 5 stats cards + filters + query log list + panel detail bên phải |
| 3.D.5 | Filter "Email" gõ 1 phần email học viên | Bảng chỉ còn query của học viên match |
| 3.D.6 | Filter "Status" chọn "Error" | Chỉ còn query status=error |
| 3.D.7 | Click 1 row trong bảng | Panel phải hiện full SQL + error (nếu có) + nút Copy SQL |
| 3.D.8 | Click ✕ hoặc click ngoài modal | Modal đóng |
| 3.D.9 | Thử gọi `teacher_query_log()` từ tab SQL editor với user non-teacher | RPC lỗi "Not authorized (need teacher role)" |

### 4.x Cross-browser smoke test (ít nhất 2 browser)

- [ ] Chrome (latest) — desktop
- [ ] Safari (latest) — desktop
- [ ] Firefox (latest) — desktop
- [ ] Chrome — mobile (check Monaco editor usable, ít nhất đọc được kết quả)

---

## 5. Performance & Limits

| # | Test | Kỳ vọng | Lý do |
|---|---|---|---|
| 5.1 | 5 user login đồng thời, mỗi user chạy 10 query liên tiếp | Không user nào crash; Supabase free tier dư sức | Connection pool ~60 |
| 5.2 | Tải initial bundle (Network tab): tổng < 600 KB gzipped | Bundle: index.js + supabase + monaco chunks | Monaco chunked riêng (~7.5 KB) |
| 5.3 | DB size (Dashboard → Database → Backups) | < 400 MB | Nếu gần 500 MB limit → giảm `orders_per_day_normal` |

---

## 6. Keep-alive

| # | Step | Kỳ vọng |
|---|---|---|
| 6.1 | Actions → `Keep Supabase alive` → Run workflow | Workflow xanh, log in ra JSON response từ `/rest/v1/exercise?select=exercise_id&limit=1` |
| 6.2 | Cron schedule đã active | Actions tab hiển thị next run vào thứ 2 tới |

---

## 7. Teacher dashboard (read-only qua SQL Editor — phase 1)

Giảng viên tự chạy ở **Supabase SQL Editor** (không cần frontend).

| # | Query | Kỳ vọng |
|---|---|---|
| 7.1 | `SELECT * FROM learning.v_student_summary ORDER BY last_active_at DESC LIMIT 20;` | Trả list học viên, tổng queries, ok/error counts |
| 7.2 | `SELECT * FROM learning.v_top_errors LIMIT 10;` | Top error_code kèm sample message |
| 7.3 | `SELECT u.email, q.* FROM learning.query_log q JOIN auth.users u ON u.id = q.user_id ORDER BY q.created_at DESC LIMIT 20;` | Join được auth.users để lấy email |

---

## 8. Rollback plan (nếu go-live fail)

1. Revert commit: `git revert HEAD && git push` → Netlify auto rebuild phiên bản cũ.
2. Nếu data bị corrupt: Actions → `Seed database` mode=`reset` → re-import fresh.
3. Hard reset DB schema: Supabase dashboard → SQL Editor:
   ```sql
   DROP SCHEMA shopee CASCADE;
   DROP SCHEMA learning CASCADE;
   ```
   Rồi re-run seed mode=full.

---

## 9. Sign-off

Mọi mục trên đã tick ✅:

- [ ] Người test: ________________
- [ ] Ngày: ________________
- [ ] Ghi chú (nếu có): ________________

**Chỉ khi tất cả mục ở section 1-6 pass mới go-live cho học viên.**
