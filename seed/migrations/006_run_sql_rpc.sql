-- 006_run_sql_rpc.sql
-- RPC public.run_sql(): entry point cho học viên chạy query.
-- Public schema để Supabase PostgREST expose qua REST API.
--
-- Security model (v4 — SECURITY INVOKER):
--   SECURITY DEFINER + SET ROLE không dùng được (Postgres chặn SET ROLE
--   trong security-definer function). Thay vào đó:
--
--   1. Function là SECURITY INVOKER → chạy với quyền caller (authenticated).
--   2. Role `authenticated` được GRANT:
--        • SELECT trên shopee.* (read-only)
--        • USAGE trên learning + INSERT trên learning.query_log
--      → Nếu user inject UPDATE/DELETE/DROP, Postgres chặn vì thiếu privilege.
--   3. Input sanitization (thêm layer):
--        • Strip leading whitespace + line comments
--        • Strip trailing whitespace + `;`
--        • Reject nếu còn `;` ở giữa (chặn multi-statement)
--        • Whitelist SELECT/WITH/EXPLAIN ở đầu
--   4. Wrap SELECT/WITH trong `SELECT * FROM (...) q LIMIT 500` — cho phép
--      user LIMIT riêng không clash syntax.
--   5. EXPLAIN chạy qua `EXPLAIN (FORMAT JSON)`, không wrap subquery.
--   6. RLS trên learning.query_log: WITH CHECK (user_id = auth.uid()) → pass
--      vì ta truyền v_uid = auth.uid().

-- Cleanup nếu còn function cũ
DROP FUNCTION IF EXISTS learning.run_sql(TEXT, TEXT);
DROP FUNCTION IF EXISTS public.run_sql(TEXT, TEXT);

CREATE OR REPLACE FUNCTION public.run_sql(
  query_text     TEXT,
  exercise_id_in TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = shopee, public
AS $$
DECLARE
  v_start    TIMESTAMPTZ := clock_timestamp();
  v_result   JSONB;
  v_plan     JSONB;
  v_row_cnt  INT := 0;
  v_exec_ms  INT;
  v_err_code TEXT;
  v_err_msg  TEXT;
  v_uid      UUID := auth.uid();
  v_clean    TEXT;
  v_head     TEXT;
  v_is_explain BOOLEAN := FALSE;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated' USING ERRCODE = '28000';
  END IF;

  -- 1. Strip leading whitespace + line comments (với hoặc không có trailing \n)
  v_clean := regexp_replace(query_text, E'^(?:\\s+|--[^\\n]*)+', '', 'g');
  -- Strip trailing whitespace + semicolons
  v_clean := regexp_replace(v_clean, E'[\\s;]+$', '', 'g');

  IF v_clean IS NULL OR v_clean = '' THEN
    RAISE EXCEPTION 'Empty query' USING ERRCODE = '42601';
  END IF;

  -- 2. Chặn multi-statement: reject `;` ở giữa
  IF position(';' IN v_clean) > 0 THEN
    RAISE EXCEPTION 'Multiple statements not allowed; remove ";"' USING ERRCODE = '42601';
  END IF;

  v_head := upper(v_clean);
  v_is_explain := v_head LIKE 'EXPLAIN%';

  IF NOT (
    v_head LIKE 'SELECT%'
    OR v_head LIKE 'WITH%'
    OR v_is_explain
  ) THEN
    RAISE EXCEPTION 'Only SELECT/WITH/EXPLAIN are allowed' USING ERRCODE = '42501';
  END IF;

  -- Chỉ bare `EXPLAIN SELECT/WITH` — chặn ANALYZE/VERBOSE.
  -- (Postgres POSIX regex dùng \y cho word boundary, không phải \b)
  IF v_is_explain AND v_head !~ '^EXPLAIN\s+(SELECT|WITH)\y' THEN
    RAISE EXCEPTION 'Only bare EXPLAIN SELECT/WITH allowed (no ANALYZE/VERBOSE)' USING ERRCODE = '42501';
  END IF;

  -- 3. Resource limits (trong transaction)
  SET LOCAL statement_timeout = '5s';
  SET LOCAL work_mem = '16MB';

  -- 4. Execute
  BEGIN
    IF v_is_explain THEN
      -- Trailing \n chống inline comment ở cuối query
      EXECUTE E'EXPLAIN (FORMAT JSON) ' || regexp_replace(v_clean, E'^EXPLAIN\\s+', '', 'i') || E'\n'
        INTO v_plan;
      v_result := jsonb_build_array(jsonb_build_object('QUERY PLAN', v_plan));
      v_row_cnt := 1;
    ELSE
      -- Append \n để nếu user query kết thúc bằng `-- comment`, comment không
      -- nuốt mất phần wrapper `) AS q LIMIT 500) t`.
      EXECUTE format(
        E'SELECT jsonb_agg(row_to_json(t)) FROM (SELECT * FROM (%s\n) AS q LIMIT 500) t',
        v_clean
      ) INTO v_result;
      v_row_cnt := COALESCE(jsonb_array_length(v_result), 0);
    END IF;
  EXCEPTION WHEN OTHERS THEN
    v_err_code := SQLSTATE;
    v_err_msg  := SQLERRM;
  END;

  v_exec_ms := EXTRACT(MILLISECONDS FROM (clock_timestamp() - v_start))::INT;

  -- 5. Log (authenticated có INSERT trên learning.query_log; RLS WITH CHECK pass
  --    vì user_id = v_uid = auth.uid())
  INSERT INTO learning.query_log
    (user_id, exercise_id, sql_text, status, error_code, error_message, row_count, exec_ms)
  VALUES
    (v_uid, exercise_id_in, query_text,
     CASE WHEN v_err_code IS NULL THEN 'ok' ELSE 'error' END,
     v_err_code, v_err_msg, v_row_cnt, v_exec_ms);

  IF v_err_code IS NOT NULL THEN
    RETURN jsonb_build_object(
      'status', 'error',
      'error_code', v_err_code,
      'error_message', v_err_msg,
      'exec_ms', v_exec_ms
    );
  END IF;

  RETURN jsonb_build_object(
    'status', 'ok',
    'rows', COALESCE(v_result, '[]'::jsonb),
    'row_count', v_row_cnt,
    'exec_ms', v_exec_ms,
    'truncated', v_row_cnt = 500
  );
END;
$$;

REVOKE ALL ON FUNCTION public.run_sql(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.run_sql(TEXT, TEXT) TO authenticated;

COMMENT ON FUNCTION public.run_sql IS
  'Execute read-only SQL from students. SECURITY INVOKER — runs as authenticated (SELECT-only on shopee). 5s timeout, 500-row limit, logs to learning.query_log.';
