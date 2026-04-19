# DA Tool — Học SQL qua Shopee case study

Web tool cho lớp học DA: học viên mở browser, login, gõ SQL PostgreSQL thật vào editor, chạy trên dataset Shopee-like 3 tháng. Mọi query đều được log để giảng viên phân tích lỗi sai phổ biến.

**Stack 100% free:**
- DB + Auth + RPC: **Supabase** (free tier)
- Frontend: **Netlify** (free tier)
- Data pipeline: **Python + Faker** (generate deterministic 3-tháng dataset)
- Keep-alive: **GitHub Actions** (chống Supabase pause)

---

## Cấu trúc repo

```
.
├── docs/
│   ├── schema.md                 # schema reference
│   └── exercises/                # 87 bài tập case-study (12 theme)
│       ├── README.md
│       ├── A-revenue-gmv.md ... L-capstone.md
├── seed/                         # Python data generator + SQL migrations
│   ├── config.yml                # date range, volumes, probabilities
│   ├── seed.py                   # orchestrator
│   ├── import_exercises.py       # import markdown vào learning.exercise
│   ├── requirements.txt
│   ├── migrations/               # 7 SQL files (schema, RLS, run_sql RPC)
│   └── generators/               # 1 generator per table
├── web/                          # React SPA
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx               # workbench layout
│   │   ├── supabase.ts           # Supabase client
│   │   ├── lib/runSql.ts         # call run_sql RPC
│   │   └── components/           # AuthGate, SqlEditor (Monaco), ResultTable, ...
│   └── public/_redirects
├── .github/workflows/keep-alive.yml
└── netlify.toml
```

---

## Setup từ 0 → production (~45 phút)

### 1. Tạo Supabase project (5 phút)

1. Đăng ký [supabase.com](https://supabase.com) (free).
2. **New project** → chọn region gần nhất (Singapore cho VN).
3. Set password strong → **Create**.
4. Chờ ~2 phút DB khởi tạo.

### 2. Chạy migrations + seed data (20–30 phút)

**Yêu cầu local:**
- Python 3.10+
- Postgres client (`psql`) — không bắt buộc nhưng tiện

```bash
# Clone repo, vào thư mục
git clone <repo-url> && cd DA_tool

# Python deps
cd seed
pip install -r requirements.txt

# Copy env template, điền DATABASE_URL từ Supabase
# (Supabase dashboard → Project Settings → Database → Connection string → URI,
#  nhớ thay [YOUR-PASSWORD])
cp .env.example .env
nano .env

# Chạy migrations + sinh data (15-20 phút tuỳ máy)
python seed.py --mode=full

# Import 87 bài tập vào bảng learning.exercise
python import_exercises.py
```

Sau lệnh này, Supabase có:
- Schema `shopee` (~400MB) đầy đủ dim + fact
- Schema `learning` với `query_log`, `attempt`, `exercise`
- Role `student_ro` read-only
- RPC `learning.run_sql()` có timeout + log

### 3. Deploy frontend lên Netlify (10 phút)

**Cách 1 — kết nối GitHub (khuyến nghị):**

1. Push code lên GitHub.
2. [netlify.com](https://netlify.com) → **Add new site → Import from Git** → chọn repo.
3. Netlify tự đọc `netlify.toml`, không cần config thủ công.
4. **Site configuration → Environment variables** thêm:
   - `VITE_SUPABASE_URL` = URL Supabase (dashboard → Settings → API)
   - `VITE_SUPABASE_ANON_KEY` = anon key (public, không phải service_role)
5. **Deploy** → chờ ~2 phút → site live ở `your-project.netlify.app`.

**Cách 2 — drag & drop (cho prototype nhanh):**

```bash
cd web
npm install
cp .env.example .env.local && nano .env.local   # điền SUPABASE_URL + ANON_KEY
npm run build
# Drag folder web/dist vào netlify.com/drop
```

### 4. Cấu hình Supabase Auth (5 phút)

1. Supabase dashboard → **Authentication → URL Configuration**:
   - **Site URL**: `https://your-project.netlify.app`
   - **Redirect URLs**: thêm `https://your-project.netlify.app/**`
2. **Authentication → Providers → Email**: enable **Magic link** (mặc định đã bật).
3. (Tuỳ chọn) Custom SMTP — free tier Supabase có giới hạn 4 email/giờ. Lớp đông có thể cần SMTP riêng.

### 5. Keep-alive (2 phút)

Chống Supabase pause sau 7 ngày idle:

1. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `SUPABASE_URL` = Supabase URL
   - `SUPABASE_ANON_KEY` = anon key
2. Actions → bật workflow `Keep Supabase alive` — chạy tự động mỗi thứ Hai.

---

## Sử dụng hàng ngày

### Thêm bài tập mới

1. Tạo file `.md` trong `docs/exercises/` theo format hiện có (hoặc thêm vào file theme có sẵn).
2. Chạy:
   ```bash
   cd seed && python import_exercises.py
   ```
3. Học viên refresh browser, thấy bài mới trong sidebar.

### Update dataset (thêm tháng mới / sửa data)

Xem [docs/schema.md](docs/schema.md) chi tiết. Quick reference:

```bash
cd seed
# Thay đổi config.yml, rồi:

# A. Thêm data mới (idempotent, không đụng data cũ)
python seed.py --mode=data

# B. Reset hoàn toàn schema shopee (giữ nguyên learning.query_log)
python seed.py --mode=reset

# C. Chỉ apply migrations SQL (vd sau khi edit file 00X_...)
python seed.py --mode=migrate
```

### Xem stats lớp học

Supabase dashboard → SQL Editor:

```sql
-- Học viên active nhất tuần qua
SELECT * FROM learning.v_student_summary
ORDER BY last_active_at DESC LIMIT 20;

-- Lỗi SQL phổ biến nhất (từ SQLSTATE)
SELECT * FROM learning.v_top_errors LIMIT 20;

-- Chi tiết 20 query mới nhất
SELECT u.email, ql.*
FROM learning.query_log ql
JOIN auth.users u ON u.id = ql.user_id
ORDER BY ql.created_at DESC
LIMIT 20;
```

### Thêm giảng viên (bypass RLS)

```sql
-- Supabase dashboard → SQL Editor
-- Giả sử email giảng viên là teacher@example.com
-- Set custom claim để tool dashboard biết đây là teacher (tuỳ chọn, phase 2)
```

---

## Giới hạn free tier

| Giới hạn | Threshold | Hết thì sao |
|---|---|---|
| Supabase DB | 500 MB | Upgrade Pro $25/mo (8GB) |
| Supabase Auth | 50k MAU | Dư cho lớp học |
| Supabase Edge Fn | 500k/tháng | Không dùng (bài này chạy RPC trực tiếp) |
| Netlify bandwidth | 100 GB/tháng | Dư cho 100+ học viên |
| Netlify build | 300 phút/tháng | Push ~30 lần/tháng OK |
| GitHub Actions | 2000 phút/tháng | Keep-alive chỉ dùng ~5 phút/tháng |

Dataset `shopee` ~300-400 MB (theo config.yml default). `learning` tăng theo usage của học viên (~10 KB/ngày/học viên).

---

## Troubleshooting

**`permission denied for schema shopee` khi chạy query:**
→ Migration `005_roles_rls.sql` chưa chạy. Chạy lại `python seed.py --mode=migrate`.

**`run_sql` trả "Not authenticated":**
→ Frontend chưa login. Check `AuthGate` component đã bao ngoài workbench.

**Query 1 câu đơn giản mà trả "Only SELECT/WITH/EXPLAIN are allowed":**
→ Kiểm tra câu query có bắt đầu bằng comment `--`. `run_sql` regex check chỉ nhận SELECT/WITH/EXPLAIN ở đầu. Học viên nên tách comment xuống dưới.

**Seed chậm:**
→ Chạy trên máy local rồi `pg_dump` export + `psql` import vào Supabase. Hoặc giảm `volumes` trong `config.yml`.

**Supabase DB đầy (>500 MB):**
→ Giảm `orders_per_day_normal` từ 1500 xuống 800 trong `config.yml`, hoặc rút `fact_traffic_session` (chiếm ~70MB). Rồi `python seed.py --mode=reset`.

---

## Lộ trình phát triển

- [x] **Phase 1** — Schema, seed, auth, editor, run_sql, log
- [ ] **Phase 2** — Auto-grade (expected result hash), hint system, teacher dashboard
- [ ] **Phase 3** — Leaderboard, streak, export CSV báo cáo lớp

---

## License

MIT. Dataset là synthetic, không phải data Shopee thật.
