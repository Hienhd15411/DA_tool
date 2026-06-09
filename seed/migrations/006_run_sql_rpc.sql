-- 006_run_sql_rpc.sql
-- RPC public.run_sql(): entry point cho học viên chạy query.
--
-- Security model (v6 — SECURITY INVOKER + JSON ordering fix):
--   1. SECURITY INVOKER → chạy với quyền caller (authenticated).
--   2. authenticated được GRANT SELECT shopee.* + INSERT learning.query_log
--      → DML/DDL inject bị Postgres chặn ở permission layer.
--   3. Input sanitization: strip leading ws/comments, strip trailing `;`,
--      reject `;` giữa, whitelist SELECT/WITH/EXPLAIN.
--   4. Caps: 5s timeout, 16MB work_mem, 1000 rows, 2MB payload.
--   5. EXPLAIN qua `EXPLAIN (FORMAT JSON)` riêng.
--   6. ⭐ Dùng JSON (preserves column order) thay JSONB (sort keys
--      alphabetical) → kết quả trả về theo đúng thứ tự cột user SELECT.

-- Cleanup function cũ
DROP FUNCTION IF EXISTS learning.run_sql(TEXT, TEXT);
DROP FUNCTION IF EXISTS public.run_sql(TEXT, TEXT);

CREATE OR REPLACE FUNCTION public.run_sql(
  query_text     TEXT,
  exercise_id_in TEXT DEFAULT NULL
)
RETURNS JSON   -- ⭐ JSON, không JSONB — preserve key order
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = shopee, public
AS $$
DECLARE
  MAX_ROWS         CONSTANT INT := 1000;
  MAX_RESULT_BYTES CONSTANT INT := 2 * 1024 * 1024;

  v_start      TIMESTAMPTZ := clock_timestamp();
  v_result     JSON;     -- ⭐ JSON
  v_plan       JSON;
  v_row_cnt    INT := 0;
  v_bytes      INT := 0;
  v_exec_ms    INT;
  v_err_code   TEXT;
  v_err_msg    TEXT;
  v_uid        UUID := auth.uid();
  v_clean      TEXT;
  v_head       TEXT;
  v_is_explain BOOLEAN := FALSE;
  v_truncated  BOOLEAN := FALSE;
  v_notice     TEXT;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Not authenticated' USING ERRCODE = '28000';
  END IF;

  v_clean := regexp_replace(query_text, E'^(?:\\s+|--[^\\n]*)+', '', 'g');
  v_clean := regexp_replace(v_clean, E'[\\s;]+$', '', 'g');

  IF v_clean IS NULL OR v_clean = '' THEN
    RAISE EXCEPTION 'Empty query' USING ERRCODE = '42601';
  END IF;

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

  IF v_is_explain AND v_head !~ '^EXPLAIN\s+(SELECT|WITH)\y' THEN
    RAISE EXCEPTION 'Only bare EXPLAIN SELECT/WITH allowed (no ANALYZE/VERBOSE)' USING ERRCODE = '42501';
  END IF;

  SET LOCAL statement_timeout = '5s';
  SET LOCAL work_mem          = '16MB';

  BEGIN
    IF v_is_explain THEN
      EXECUTE E'EXPLAIN (FORMAT JSON) ' || regexp_replace(v_clean, E'^EXPLAIN\\s+', '', 'i') || E'\n'
        INTO v_plan;
      -- json_build_array / json_build_object preserve order
      v_result  := json_build_array(json_build_object('QUERY PLAN', v_plan));
      v_row_cnt := 1;
    ELSE
      -- ⭐ json_agg(row_to_json(t)) preserve column order theo SELECT.
      EXECUTE format(
        E'SELECT json_agg(row_to_json(t)) FROM (SELECT * FROM (%s\n) AS q LIMIT %s) t',
        v_clean,
        MAX_ROWS
      ) INTO v_result;
      v_row_cnt   := COALESCE(json_array_length(v_result), 0);
      v_truncated := v_row_cnt = MAX_ROWS;

      -- HARD BYTE CAP với halving (giữ thứ tự cột vì vẫn JSON)
      v_bytes := octet_length(v_result::text);
      IF v_bytes > MAX_RESULT_BYTES THEN
        v_truncated := TRUE;
        v_notice := format(
          'Kết quả %s KB vượt ngưỡng %s KB — chỉ giữ các cột hẹp hoặc thêm LIMIT/SELECT cột cụ thể.',
          (v_bytes / 1024)::INT,
          (MAX_RESULT_BYTES / 1024)::INT
        );
        FOR i IN 1..10 LOOP
          EXIT WHEN octet_length(v_result::text) <= MAX_RESULT_BYTES;
          v_row_cnt := GREATEST(1, v_row_cnt / 2);
          -- Slice JSON array bằng json_array_elements + LIMIT (giữ thứ tự)
          v_result := (
            SELECT json_agg(elem)
            FROM (
              SELECT elem
              FROM json_array_elements(v_result) AS elem
              LIMIT v_row_cnt
            ) sub
          );
        END LOOP;
        v_row_cnt := COALESCE(json_array_length(v_result), 0);
      END IF;
    END IF;
  EXCEPTION WHEN OTHERS THEN
    v_err_code := SQLSTATE;
    v_err_msg  := SQLERRM;
  END;

  v_exec_ms := EXTRACT(MILLISECONDS FROM (clock_timestamp() - v_start))::INT;

  INSERT INTO learning.query_log
    (user_id, exercise_id, sql_text, status, error_code, error_message, row_count, exec_ms)
  VALUES
    (v_uid, exercise_id_in, query_text,
     CASE WHEN v_err_code IS NULL THEN 'ok' ELSE 'error' END,
     v_err_code, v_err_msg, v_row_cnt, v_exec_ms);

  IF v_err_code IS NOT NULL THEN
    RETURN json_build_object(
      'status',        'error',
      'error_code',    v_err_code,
      'error_message', v_err_msg,
      'exec_ms',       v_exec_ms
    );
  END IF;

  RETURN json_build_object(
    'status',    'ok',
    'rows',      COALESCE(v_result, '[]'::json),
    'row_count', v_row_cnt,
    'exec_ms',   v_exec_ms,
    'truncated', v_truncated,
    'notice',    v_notice,
    'max_rows',  MAX_ROWS
  );
END;
$$;

REVOKE ALL ON FUNCTION public.run_sql(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.run_sql(TEXT, TEXT) TO authenticated;

COMMENT ON FUNCTION public.run_sql IS
  'Execute read-only SQL. SECURITY INVOKER. JSON output preserves column order. 5s timeout, 1000 rows, 2MB payload.';
