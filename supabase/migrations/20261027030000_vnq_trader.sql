-- Thí nghiệm 4 danh mục paper trading (docs/09_TRADER_EXPERIMENT.md). Ghi bởi GitHub Actions (service_role); web chỉ đọc.
create table if not exists public.trader_nav (
  date date not null, portfolio text not null check (portfolio in ('A','B','C','D')),
  nav double precision not null, cash double precision, n_pos integer, pnl_day double precision, ret_cum double precision,
  primary key (date, portfolio));
create table if not exists public.trader_trades (
  seq integer primary key, portfolio text not null, session date not null, ticker text not null, side text not null,
  status text not null, type text, qty double precision, price double precision, value double precision,
  fee double precision, tax double precision, pnl double precision, note text);
create table if not exists public.trader_positions (
  portfolio text not null, ticker text not null, qty double precision, avg_cost double precision, last_price double precision,
  as_of date, mkt_value double precision, pnl double precision, first_buy date, primary key (portfolio, ticker));
create table if not exists public.trader_orders (
  session date not null, idx integer not null, decided_at text, committed_at text, side text, ticker text, type text,
  "limit" double precision, value_vnd double precision, qty text, reason text, sources text, market_view text, risk_plan text,
  primary key (session, idx));
do $$
declare t text;
begin
  foreach t in array array['trader_nav','trader_trades','trader_positions','trader_orders'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "read_authenticated" on public.%I', t);
    execute format('create policy "read_authenticated" on public.%I for select to authenticated using (true)', t);
  end loop;
end $$;
