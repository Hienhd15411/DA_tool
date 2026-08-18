-- 005_roles_rls.sql
-- Grants + RLS. Security model:
--   • `authenticated` (Supabase built-in, caller của run_sql): SELECT trên shopee.*
--     + INSERT vào learning.query_log. Không có DELETE/UPDATE/DROP.
--   • `anon`: chỉ xem được public.exercise (đề bài public).
--   • RLS trên learning.* bảo đảm học viên chỉ đọc/ghi log của chính mình.
--   • Teacher: bypass RLS (seed role, phase 2 sẽ map qua JWT claim).

-- -----------------------------------------------------------------
-- SHOPEE schema: read-only cho mọi authenticated user
-- -----------------------------------------------------------------
GRANT USAGE  ON SCHEMA shopee TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA shopee TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA shopee GRANT SELECT ON TABLES TO authenticated;

-- -----------------------------------------------------------------
-- LEARNING schema: internal. authenticated chỉ INSERT qua run_sql.
-- -----------------------------------------------------------------
GRANT USAGE  ON SCHEMA learning TO authenticated;
GRANT INSERT, SELECT ON learning.query_log TO authenticated;
GRANT INSERT, SELECT ON learning.attempt   TO authenticated;
GRANT USAGE  ON ALL SEQUENCES IN SCHEMA learning TO authenticated;

-- -----------------------------------------------------------------
-- RLS: query_log (học viên chỉ thấy/ghi log của chính mình)
-- -----------------------------------------------------------------
ALTER TABLE learning.query_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS qlog_self_read ON learning.query_log;
CREATE POLICY qlog_self_read ON learning.query_log
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS qlog_self_insert ON learning.query_log;
CREATE POLICY qlog_self_insert ON learning.query_log
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------
-- RLS: attempt
-- -----------------------------------------------------------------
ALTER TABLE learning.attempt ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS attempt_self_read ON learning.attempt;
CREATE POLICY attempt_self_read ON learning.attempt
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS attempt_self_insert ON learning.attempt;
CREATE POLICY attempt_self_insert ON learning.attempt
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- -----------------------------------------------------------------
-- public.exercise: đề bài public, ai cũng đọc được
-- -----------------------------------------------------------------
GRANT SELECT ON public.exercise TO anon, authenticated;

-- -----------------------------------------------------------------
-- Teacher role (phase 2): bypass RLS để xem tất cả
-- -----------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'teacher') THEN
    CREATE ROLE teacher NOLOGIN;
  END IF;
END $$;

GRANT USAGE  ON SCHEMA learning TO teacher;
GRANT SELECT ON ALL TABLES IN SCHEMA learning TO teacher;
GRANT SELECT ON learning.v_student_summary TO teacher;
GRANT SELECT ON learning.v_top_errors      TO teacher;
