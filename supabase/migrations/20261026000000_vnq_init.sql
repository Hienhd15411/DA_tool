-- =====================================================================
-- VNQ — schema kết quả tín hiệu hằng ngày (engine ghi bằng service_role,
-- dashboard chỉ ĐỌC). Mặc định: chỉ user đăng nhập (authenticated) được đọc.
-- Muốn mở công khai: xem khối "PUBLIC READ (tùy chọn)" ở cuối file.
-- =====================================================================


-- ---------- Model & thí nghiệm ----------
create table if not exists public.model_versions (
  version              text primary key,
  created_at           timestamptz not null,
  ledger_hash          text not null,
  best                 text,
  params               jsonb,
  features             jsonb,
  train_start          date,
  train_end            date,
  train_end_effective  date,
  n_train              integer,
  wf_ic                jsonb,
  note                 text
);

create table if not exists public.experiments (
  version    text not null references public.model_versions(version),
  fold       integer not null,
  model      text not null,
  cfg        text,
  ic_mean    double precision,
  n_train    integer,
  n_val      integer,
  logged_at  timestamptz not null default now(),
  primary key (version, fold, model)
);

-- ---------- Mỗi lần chạy (1 dòng / ngày dữ liệu) ----------
create table if not exists public.daily_runs (
  data_date        date primary key,
  run_at           timestamptz not null,
  model_version    text not null references public.model_versions(version),
  n_eligible       integer not null,
  n_pool           integer not null,
  regime_universe  jsonb,
  regime_pool      jsonb,
  qc               jsonb,
  warnings         jsonb,
  quarantine       jsonb,
  gate_pass        boolean not null,
  report_path      text
);

create table if not exists public.gate_snapshots (
  data_date      date primary key references public.daily_runs(data_date) on delete cascade,
  model_version  text not null,
  test_start     date not null,
  n_test_days    integer not null,
  checks         jsonb not null,
  metrics        jsonb not null,
  strategy_pass  boolean not null,
  computed_at    timestamptz
);

-- ---------- Điểm toàn universe đủ điều kiện mỗi ngày ----------
create table if not exists public.scores_daily (
  data_date     date not null,
  ticker        text not null,
  industry      text,
  close         double precision,
  p_up_5        double precision,
  p_lr          double precision,
  rank_all      integer,
  value_score   double precision,
  value_mode    text,
  value_top30   boolean,
  trend_score   double precision,
  regime        text check (regime in ('Uptrend','Downtrend','Sideways')),
  atr14_pct     double precision,
  liq20         double precision,
  near_ceiling  smallint,
  near_floor    smallint,
  exch          text,
  exch_src      text,
  primary key (data_date, ticker)
);
create index if not exists scores_daily_ticker_idx on public.scores_daily (ticker, data_date desc);

-- ---------- Top-K + kết quả paper trading ----------
-- Cột chi tiết được ghi trong ngày chọn; cột kết quả (status..excess) được cập nhật khi đủ 5 phiên.
create table if not exists public.signals (
  data_date      date not null,
  ticker         text not null,
  rank_sel       integer,
  industry       text,
  close          double precision,
  p_up_5         double precision,
  rank_pool      integer,
  rank_all       integer,
  d_p            double precision,
  value_score    double precision,
  value_mode     text,
  trend_score    double precision,
  regime         text,
  regime_prev    text,
  atr14_pct      double precision,
  liq20          double precision,
  action         text check (action is null or action in ('Theo dõi','Cân nhắc mua')),
  risks          text,
  reasons        text,
  model_version  text,
  gate_pass      boolean,
  status         text check (status is null or status in ('open','settled','unfilled_ceiling')),
  gross          double precision,
  net            double precision,
  y_bin          double precision,
  univ_mean      double precision,
  excess         double precision,
  primary key (data_date, ticker)
);
create index if not exists signals_ticker_idx on public.signals (ticker, data_date desc);

-- ---------- View tổng hợp ----------
create or replace view public.v_track_record
with (security_invoker = true) as
select
  coalesce(action, '(tất cả)')                 as action,
  count(*)                                     as n_settled,
  count(distinct data_date)                    as n_days,
  avg(y_bin)                                   as hit_rate,
  avg(net)                                     as avg_net,
  avg(excess)                                  as avg_excess,
  stddev_samp(net)                             as sd_net
from public.signals
where status = 'settled'
group by grouping sets ((action), ());

create or replace view public.v_track_daily
with (security_invoker = true) as
select data_date, count(*) as n, avg(net) as avg_net, avg(excess) as avg_excess, avg(y_bin) as hit
from public.signals where status = 'settled'
group by data_date order by data_date;

-- ---------- RLS: đọc cho authenticated, ghi chỉ service_role (bypass RLS) ----------
do $$
declare t text;
begin
  foreach t in array array['model_versions','experiments','daily_runs','gate_snapshots','scores_daily','signals'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "read_authenticated" on public.%I', t);
    execute format('create policy "read_authenticated" on public.%I for select to authenticated using (true)', t);
  end loop;
end $$;

grant usage on schema public to anon, authenticated;
grant select on public.model_versions, public.experiments, public.daily_runs, public.gate_snapshots,
                public.scores_daily, public.signals, public.v_track_record, public.v_track_daily to authenticated;
revoke insert, update, delete on public.model_versions, public.experiments, public.daily_runs, public.gate_snapshots,
                public.scores_daily, public.signals from anon, authenticated;

-- ---------- Storage bucket riêng tư cho dữ liệu/trạng thái engine ----------
-- (chỉ chạy được trên Supabase — bỏ qua khi test Postgres thuần)
do $$
begin
  if exists (select 1 from information_schema.schemata where schema_name = 'storage') then
    insert into storage.buckets (id, name, public) values ('vnq-data', 'vnq-data', false)
    on conflict (id) do nothing;
  end if;
end $$;

-- ---------- PUBLIC READ (tùy chọn — CHỈ bật khi chấp nhận ai có link cũng xem được) ----------
-- do $$ declare t text; begin
--   foreach t in array array['model_versions','experiments','daily_runs','gate_snapshots','scores_daily','signals'] loop
--     execute format('create policy "read_anon" on public.%I for select to anon using (true)', t);
--   end loop; end $$;
-- grant select on all tables in schema public to anon;
