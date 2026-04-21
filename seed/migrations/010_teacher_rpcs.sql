-- 010_teacher_rpcs.sql
-- Teacher dashboard: RPCs để giảng viên xem + filter query log của học viên.
--
-- Kiến trúc access control:
--   1. Table public.teacher_emails (email TEXT PRIMARY KEY) — whitelist giảng viên.
--      Chỉ admin (qua Supabase SQL Editor) insert email vào đây.
--   2. Function is_teacher() đọc auth.jwt()->>'email' so với whitelist → BOOLEAN.
--   3. Các teacher_* RPC check is_teacher() ở đầu → raise nếu không phải teacher.
--   4. SECURITY DEFINER bypass RLS → xem được query_log của tất cả học viên.

-- -------------------------------------------------------------------
-- 1. Teacher whitelist table
-- -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.teacher_emails (
  email      TEXT PRIMARY KEY,
  added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  added_note TEXT
);

COMMENT ON TABLE public.teacher_emails IS
  'Whitelist của email giảng viên. Admin insert qua Supabase SQL Editor.';

-- Không grant SELECT cho authenticated — bảng này chỉ admin quản lý.
REVOKE ALL ON public.teacher_emails FROM PUBLIC;

-- -------------------------------------------------------------------
-- 2. is_teacher() — check user hiện tại có trong whitelist không
-- -------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_teacher()
RETURNS BOOLEAN
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
STABLE
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.teacher_emails te
    WHERE te.email = (auth.jwt()->>'email')
  );
$$;

REVOKE ALL ON FUNCTION public.is_teacher() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_teacher() TO authenticated;

COMMENT ON FUNCTION public.is_teacher IS
  'True nếu email của user trong JWT match public.teacher_emails whitelist.';

-- -------------------------------------------------------------------
-- 3. teacher_query_log() — list queries với filters
-- -------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.teacher_query_log(
  filter_email    TEXT DEFAULT NULL,   -- ILIKE '%xxx%'
  filter_exercise TEXT DEFAULT NULL,   -- ILIKE '%xxx%'
  filter_status   TEXT DEFAULT NULL,   -- 'ok' | 'error' | NULL
  since_days      INT  DEFAULT 7,
  max_rows        INT  DEFAULT 200
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, learning
AS $$
DECLARE
  v_data JSONB;
BEGIN
  IF NOT public.is_teacher() THEN
    RAISE EXCEPTION 'Not authorized (need teacher role)' USING ERRCODE = '42501';
  END IF;

  max_rows := LEAST(GREATEST(max_rows, 1), 1000);
  since_days := LEAST(GREATEST(since_days, 1), 365);

  SELECT jsonb_agg(r ORDER BY created_at DESC) INTO v_data
  FROM (
    SELECT
      ql.id,
      ql.created_at,
      u.email            AS student_email,
      ql.exercise_id,
      ql.status,
      ql.error_code,
      ql.error_message,
      ql.row_count,
      ql.exec_ms,
      ql.sql_text
    FROM learning.query_log ql
    LEFT JOIN auth.users u ON u.id = ql.user_id
    WHERE ql.created_at >= now() - (since_days || ' days')::INTERVAL
      AND (filter_email    IS NULL OR u.email        ILIKE '%' || filter_email    || '%')
      AND (filter_exercise IS NULL OR ql.exercise_id ILIKE '%' || filter_exercise || '%')
      AND (filter_status   IS NULL OR ql.status = filter_status)
    ORDER BY ql.created_at DESC
    LIMIT max_rows
  ) r;

  RETURN COALESCE(v_data, '[]'::jsonb);
END;
$$;

REVOKE ALL ON FUNCTION public.teacher_query_log(TEXT, TEXT, TEXT, INT, INT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.teacher_query_log(TEXT, TEXT, TEXT, INT, INT) TO authenticated;

COMMENT ON FUNCTION public.teacher_query_log IS
  'Teacher dashboard: list queries với filters. Chỉ teacher gọi được.';

-- -------------------------------------------------------------------
-- 4. teacher_stats() — summary cards
-- -------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.teacher_stats(
  since_days INT DEFAULT 7
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, learning
AS $$
DECLARE
  v_since    TIMESTAMPTZ;
  v_total    BIGINT;
  v_ok       BIGINT;
  v_err      BIGINT;
  v_students BIGINT;
  v_ex       BIGINT;
  v_top_err  JSONB;
  v_top_stu  JSONB;
BEGIN
  IF NOT public.is_teacher() THEN
    RAISE EXCEPTION 'Not authorized (need teacher role)' USING ERRCODE = '42501';
  END IF;

  since_days := LEAST(GREATEST(since_days, 1), 365);
  v_since := now() - (since_days || ' days')::INTERVAL;

  SELECT COUNT(*),
         COUNT(*) FILTER (WHERE status = 'ok'),
         COUNT(*) FILTER (WHERE status = 'error'),
         COUNT(DISTINCT user_id),
         COUNT(DISTINCT exercise_id) FILTER (WHERE exercise_id IS NOT NULL)
    INTO v_total, v_ok, v_err, v_students, v_ex
  FROM learning.query_log
  WHERE created_at >= v_since;

  SELECT jsonb_agg(r ORDER BY occurrences DESC) INTO v_top_err
  FROM (
    SELECT
      error_code,
      COUNT(*)                               AS occurrences,
      COUNT(DISTINCT user_id)                AS affected_students,
      (ARRAY_AGG(error_message ORDER BY created_at DESC))[1] AS sample_message
    FROM learning.query_log
    WHERE status = 'error' AND created_at >= v_since
    GROUP BY error_code
    ORDER BY COUNT(*) DESC
    LIMIT 10
  ) r;

  SELECT jsonb_agg(r ORDER BY queries DESC) INTO v_top_stu
  FROM (
    SELECT
      u.email,
      COUNT(*)                                 AS queries,
      COUNT(*) FILTER (WHERE ql.status = 'ok') AS ok_queries,
      COUNT(*) FILTER (WHERE ql.status='error') AS err_queries,
      MAX(ql.created_at)                       AS last_active
    FROM learning.query_log ql
    LEFT JOIN auth.users u ON u.id = ql.user_id
    WHERE ql.created_at >= v_since
    GROUP BY u.email
    ORDER BY COUNT(*) DESC
    LIMIT 20
  ) r;

  RETURN jsonb_build_object(
    'since_days',         since_days,
    'total_queries',      v_total,
    'ok_queries',         v_ok,
    'error_queries',      v_err,
    'active_students',    v_students,
    'active_exercises',   v_ex,
    'error_rate_pct',     CASE WHEN v_total = 0 THEN 0 ELSE ROUND(v_err::numeric * 100 / v_total, 1) END,
    'top_errors',         COALESCE(v_top_err, '[]'::jsonb),
    'top_students',       COALESCE(v_top_stu, '[]'::jsonb)
  );
END;
$$;

REVOKE ALL ON FUNCTION public.teacher_stats(INT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.teacher_stats(INT) TO authenticated;

COMMENT ON FUNCTION public.teacher_stats IS
  'Teacher dashboard: summary stats + top errors + top active students.';
