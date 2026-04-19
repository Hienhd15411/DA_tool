-- 004_learning_schema.sql
-- Schema `learning`: query log, exercises, student progress.
-- Tách riêng để update dataset không ảnh hưởng data học viên.

CREATE TABLE IF NOT EXISTS learning.exercise (
  exercise_id    TEXT PRIMARY KEY,             -- 'A1', 'B3', ...
  theme          TEXT NOT NULL,                -- 'A' (Revenue), 'B', ...
  title          TEXT NOT NULL,
  level          SMALLINT NOT NULL CHECK (level BETWEEN 1 AND 4),
  description_md TEXT NOT NULL,                -- markdown đề bài
  expected_sql   TEXT,                         -- đáp án mẫu (không show học viên)
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS learning.query_log (
  id              BIGSERIAL PRIMARY KEY,
  user_id         UUID NOT NULL,                          -- auth.users.id
  exercise_id     TEXT REFERENCES learning.exercise(exercise_id),
  sql_text        TEXT NOT NULL,
  status          TEXT NOT NULL,                          -- 'ok' | 'error' | 'timeout'
  error_code      TEXT,                                   -- SQLSTATE
  error_message   TEXT,
  row_count       INT,
  exec_ms         INT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_query_log_user_time ON learning.query_log (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_query_log_exercise  ON learning.query_log (exercise_id, status);

CREATE TABLE IF NOT EXISTS learning.attempt (
  id             BIGSERIAL PRIMARY KEY,
  user_id        UUID NOT NULL,
  exercise_id    TEXT NOT NULL REFERENCES learning.exercise(exercise_id),
  is_correct     BOOLEAN NOT NULL,
  submitted_sql  TEXT NOT NULL,
  attempted_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, exercise_id, attempted_at)
);

CREATE INDEX IF NOT EXISTS ix_attempt_user ON learning.attempt (user_id, exercise_id);

-- View tổng hợp để giảng viên xem
CREATE OR REPLACE VIEW learning.v_student_summary AS
SELECT
  user_id,
  COUNT(*)                                         AS total_queries,
  COUNT(*) FILTER (WHERE status = 'ok')            AS ok_queries,
  COUNT(*) FILTER (WHERE status = 'error')         AS error_queries,
  COUNT(DISTINCT exercise_id)                      AS exercises_touched,
  MAX(created_at)                                  AS last_active_at
FROM learning.query_log
GROUP BY user_id;

CREATE OR REPLACE VIEW learning.v_top_errors AS
SELECT
  error_code,
  COUNT(*)                                     AS occurrences,
  COUNT(DISTINCT user_id)                      AS affected_students,
  (ARRAY_AGG(error_message ORDER BY created_at DESC))[1] AS sample_message
FROM learning.query_log
WHERE status = 'error'
GROUP BY error_code
ORDER BY occurrences DESC;
