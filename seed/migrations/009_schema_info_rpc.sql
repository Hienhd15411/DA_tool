-- 009_schema_info_rpc.sql
-- RPC public.get_schema_info(): trả về toàn bộ bảng + cột trong schema shopee
-- để frontend render schema browser (sidebar bên trái).

CREATE OR REPLACE FUNCTION public.get_schema_info()
RETURNS JSONB
LANGUAGE sql
SECURITY DEFINER
SET search_path = shopee, public
AS $$
  WITH tables AS (
    SELECT
      t.table_name,
      -- GREATEST(n_live_tup, reltuples) — cả 2 đều approximate nhưng khác nguồn.
      -- reltuples update ngay khi insert+commit lớn; n_live_tup cần ANALYZE.
      GREATEST(
        COALESCE(
          (SELECT n_live_tup FROM pg_stat_user_tables s
           WHERE s.schemaname = 'shopee' AND s.relname = t.table_name),
          0
        ),
        COALESCE(
          (SELECT c.reltuples::BIGINT FROM pg_class c
           JOIN pg_namespace n ON n.oid = c.relnamespace
           WHERE n.nspname = 'shopee' AND c.relname = t.table_name),
          0
        )
      )::BIGINT AS row_count,
      CASE
        WHEN t.table_name LIKE 'dim_%'  THEN 'dim'
        WHEN t.table_name LIKE 'fact_%' THEN 'fact'
        ELSE 'other'
      END AS group_name
    FROM information_schema.tables t
    WHERE t.table_schema = 'shopee' AND t.table_type = 'BASE TABLE'
  ),
  cols AS (
    SELECT
      c.table_name,
      jsonb_agg(
        jsonb_build_object(
          'name',      c.column_name,
          'type',      c.data_type,
          'nullable',  c.is_nullable = 'YES',
          'position',  c.ordinal_position
        ) ORDER BY c.ordinal_position
      ) AS columns
    FROM information_schema.columns c
    WHERE c.table_schema = 'shopee'
    GROUP BY c.table_name
  )
  SELECT COALESCE(
    jsonb_agg(
      jsonb_build_object(
        'table_name', t.table_name,
        'group',      t.group_name,
        'row_count',  t.row_count,
        'columns',    COALESCE(c.columns, '[]'::jsonb)
      ) ORDER BY t.group_name DESC, t.table_name
    ),
    '[]'::jsonb
  )
  FROM tables t
  LEFT JOIN cols c USING (table_name);
$$;

REVOKE ALL ON FUNCTION public.get_schema_info() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_schema_info() TO authenticated, anon;

COMMENT ON FUNCTION public.get_schema_info IS
  'Return all tables+columns in shopee schema (with live row counts) for frontend schema browser.';
