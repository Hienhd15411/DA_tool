-- 005_roles_rls.sql
-- Role read-only cho học viên + Row Level Security trên learning.*

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

-- Đảm bảo student_ro KHÔNG ghi được schema learning
REVOKE ALL ON SCHEMA learning FROM student_ro;

-- RLS trên learning.query_log: học viên chỉ thấy log của chính mình
ALTER TABLE learning.query_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS qlog_self_read ON learning.query_log;
CREATE POLICY qlog_self_read ON learning.query_log
  FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS qlog_self_insert ON learning.query_log;
CREATE POLICY qlog_self_insert ON learning.query_log
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- RLS trên learning.attempt
ALTER TABLE learning.attempt ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS attempt_self_read ON learning.attempt;
CREATE POLICY attempt_self_read ON learning.attempt
  FOR SELECT
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS attempt_self_insert ON learning.attempt;
CREATE POLICY attempt_self_insert ON learning.attempt
  FOR INSERT
  WITH CHECK (user_id = auth.uid());

-- exercise bảng public read (ai cũng xem được đề bài)
GRANT SELECT ON learning.exercise TO authenticated, anon;

-- Giảng viên: role 'teacher' bypass RLS
-- (Sau này gán cho user bằng cách set custom claim trong JWT)
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
