-- 005_roles_rls.sql
-- Role read-only cho học viên + RLS trên learning.*

-- Role student_ro: chỉ SELECT trên schema shopee
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'student_ro') THEN
    CREATE ROLE student_ro NOLOGIN;
  END IF;
END $$;

GRANT USAGE ON SCHEMA shopee TO student_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA shopee TO student_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA shopee GRANT SELECT ON TABLES TO student_ro;

REVOKE ALL ON SCHEMA learning FROM student_ro;

-- RLS: query_log
ALTER TABLE learning.query_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS qlog_self_read ON learning.query_log;
CREATE POLICY qlog_self_read ON learning.query_log
  FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS qlog_self_insert ON learning.query_log;
CREATE POLICY qlog_self_insert ON learning.query_log
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- RLS: attempt
ALTER TABLE learning.attempt ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS attempt_self_read ON learning.attempt;
CREATE POLICY attempt_self_read ON learning.attempt
  FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS attempt_self_insert ON learning.attempt;
CREATE POLICY attempt_self_insert ON learning.attempt
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- public.exercise: mọi user (đã login hoặc chưa) đọc được đề bài
GRANT SELECT ON public.exercise TO anon, authenticated;

-- Role teacher bypass RLS để xem tất cả
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'teacher') THEN
    CREATE ROLE teacher NOLOGIN;
  END IF;
END $$;

GRANT USAGE ON SCHEMA learning TO teacher;
GRANT SELECT ON ALL TABLES IN SCHEMA learning TO teacher;
GRANT SELECT ON learning.v_student_summary TO teacher;
GRANT SELECT ON learning.v_top_errors      TO teacher;
