-- 001_init_schemas.sql
-- Tạo 2 schema: stock (dataset giảng dạy — chứng khoán VN), learning (log học viên)

CREATE SCHEMA IF NOT EXISTS stock;
CREATE SCHEMA IF NOT EXISTS learning;

COMMENT ON SCHEMA stock    IS 'Vietnam stock market dataset (HOSE) for SQL exercises. Re-seedable from vnstock.';
COMMENT ON SCHEMA learning IS 'Student activity: query log, attempts, progress. Persistent.';
