-- 006_run_sql_rpc.sql
-- RPC function run_sql(): entry point cho học viên chạy query.
-- Chạy với quyền student_ro, enforce timeout, ghi log.

CREATE OR REPLACE FUNCTION learning.run_sql(
  query_text     TEXT,
  exercise_id_in TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER            -- chạy với quyền owner (để set role + ghi log)
SET search_path = shopee, public
AS $$
DECLARE
  v_start    TIMESTAMPTZ := clock_timestamp();
  v_result   JSONB;
  v_row_cnt  INT;
  v_exec_ms  INT;
  v_err_code TEXT;
  v_err_msg  TEXT;
  v_uid      UUID := auth.uid();
BEGIN
  -- Bắt buộc login
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated' USING ERRCODE = '28000';
  END IF;

  -- Chặn câu lệnh không phải SELECT/WITH (chống DDL/DML phá hoại)
  IF NOT (
    upper(btrim(query_text)) LIKE 'SELECT%'
    OR upper(btrim(query_text)) LIKE 'WITH%'
    OR upper(btrim(query_text)) LIKE 'EXPLAIN%'
  ) THEN
    RAISE EXCEPTION 'Only SELECT/WITH/EXPLAIN are allowed' USING ERRCODE = '42501';
  END IF;

  -- Giới hạn tài nguyên trong transaction
  SET LOCAL statement_timeout = '5s';
  SET LOCAL work_mem = '16MB';
  SET LOCAL ROLE student_ro;

  BEGIN
    EXECUTE format(
      'SELECT jsonb_agg(row_to_json(t)) FROM (%s LIMIT 500) t',
      query_text
    ) INTO v_result;

    v_row_cnt := COALESCE(jsonb_array_length(v_result), 0);
  EXCEPTION WHEN OTHERS THEN
    v_err_code := SQLSTATE;
    v_err_msg  := SQLERRM;
  END;

  -- Reset role để ghi log được
  RESET ROLE;

  v_exec_ms := EXTRACT(MILLISECONDS FROM (clock_timestamp() - v_start))::INT;

  -- Ghi log (luôn ghi dù ok hay lỗi)
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

-- Cho phép user đã login gọi
REVOKE ALL ON FUNCTION learning.run_sql(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION learning.run_sql(TEXT, TEXT) TO authenticated;

COMMENT ON FUNCTION learning.run_sql IS
  'Execute read-only SQL from students. Enforces 5s timeout, 500-row limit, logs to query_log.';
