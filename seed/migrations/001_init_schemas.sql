-- 001_init_schemas.sql
-- Tạo 2 schema tách bạch: shopee (dataset giảng dạy), learning (log học viên)

CREATE SCHEMA IF NOT EXISTS shopee;
CREATE SCHEMA IF NOT EXISTS learning;

COMMENT ON SCHEMA shopee   IS 'Shopee-like dataset for SQL exercises. Re-seedable.';
COMMENT ON SCHEMA learning IS 'Student activity: query log, attempts, progress. Persistent.';
