-- Snapshot dự báo hằng ngày (toàn universe) + thực tế sau 5 phiên, và chấm điểm live theo ngày.
-- Ghi bởi engine (service_role); web chỉ đọc (authenticated).

create table if not exists public.predictions_daily (
  data_date        date not null,
  ticker           text not null,
  source           text not null check (source in ('live','backfill')),
  model_version    text not null,
  close            double precision,
  p_up_5           double precision,
  p_lr             double precision,
  rank_all         integer,
  value_top30      boolean,
  tn07_pick        boolean,
  rsi14            double precision,
  vol_ratio20      double precision,
  tn06r_regime_on  boolean,
  tn06r_signal     boolean,
  status           text not null check (status in ('open','settled','unfilled_ceiling')),
  real             double precision,   -- open t+1 → close t+5 (kẹt sàn → t+6), trước phí
  net              double precision,   -- sau phí 2 chiều + thuế bán
  y_bin            double precision,
  settled_on       date,
  primary key (data_date, ticker)
);
create index if not exists predictions_daily_signal on public.predictions_daily (data_date) where tn06r_signal or tn07_pick;

create table if not exists public.live_eval_daily (
  data_date          date primary key,
  source             text not null,
  model_version      text not null,
  n                  integer,
  ic                 double precision,
  market_net         double precision,
  pool_net           double precision,
  tn07_n             integer,
  tn07_net           double precision,
  tn07_hit           double precision,
  pool_hit           double precision,
  pred_mean          double precision,
  top_decile_net     double precision,
  bottom_decile_net  double precision,
  tn06r_regime_on    boolean,
  tn06r_n            integer,
  tn06r_net          double precision
);

do $$
declare t text;
begin
  foreach t in array array['predictions_daily','live_eval_daily'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "read_authenticated" on public.%I', t);
    execute format('create policy "read_authenticated" on public.%I for select to authenticated using (true)', t);
  end loop;
end $$;
