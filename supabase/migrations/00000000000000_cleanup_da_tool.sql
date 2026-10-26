-- =====================================================================
-- Supabase cleanup: drop toàn bộ schema của DA Tool cũ (shopee + stock + learning)
-- Chạy TRƯỚC khi apply migration VNQ.
--
-- CẨN THẬN: SẼ XÓA HẾT dữ liệu Shopee + Stock + Learning history.
-- Nếu muốn giữ query_log học viên cũ, bỏ qua phần DROP learning.
-- =====================================================================

-- 1. Drop old schemas
DROP SCHEMA IF EXISTS shopee   CASCADE;
DROP SCHEMA IF EXISTS stock    CASCADE;
DROP SCHEMA IF EXISTS learning CASCADE;

-- 2. Drop RPCs từ DA Tool era
DROP FUNCTION IF EXISTS public.run_sql(TEXT, TEXT);
DROP FUNCTION IF EXISTS public.get_schema_info();
DROP FUNCTION IF EXISTS public.is_teacher();
DROP FUNCTION IF EXISTS public.teacher_query_log(TEXT, TEXT, TEXT, INT, INT);
DROP FUNCTION IF EXISTS public.teacher_stats(INT);

-- 3. Drop old whitelist table
DROP TABLE IF EXISTS public.teacher_emails;
DROP TABLE IF EXISTS public.exercise;

-- 4. Drop role 'teacher' nếu có
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'teacher') THEN
    DROP ROLE teacher;
  END IF;
END $$;

-- 5. Verify sạch
SELECT 'Schemas remaining:' AS info;
SELECT schema_name
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast',
                          'auth', 'storage', 'realtime', 'graphql',
                          'graphql_public', 'supabase_functions',
                          'pgsodium', 'pgsodium_masks', 'vault',
                          'extensions', 'net', 'cron')
ORDER BY schema_name;

SELECT 'Public tables remaining:' AS info;
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;

-- Sau khi chạy, phần output nên:
-- Schemas remaining: public (duy nhất)
-- Public tables remaining: (rỗng)
-- → Ready để apply VNQ migration.
