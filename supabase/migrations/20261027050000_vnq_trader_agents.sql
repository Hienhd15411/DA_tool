-- Nhiều agent trader (A1..A4) + danh mục bốc thăm đối ứng (R1..R4) + mốc B, C.
alter table public.trader_nav drop constraint if exists trader_nav_portfolio_check;

alter table public.trader_orders add column if not exists agent text not null default 'A1';
alter table public.trader_orders drop constraint if exists trader_orders_pkey;
alter table public.trader_orders add primary key (agent, session, idx);

create table if not exists public.trader_agents (
  id text primary key, name text, color text, style text, risk text,
  risk_per_trade double precision, max_weight double precision, min_cash double precision, max_per_industry integer,
  horizon text, goal_short text, goal_long text, industries text, _note text);
alter table public.trader_agents enable row level security;
drop policy if exists "read_authenticated" on public.trader_agents;
create policy "read_authenticated" on public.trader_agents for select to authenticated using (true);

-- dữ liệu thử nghiệm của bản 1 agent (chưa có phiên thật nào) → xóa để bắt đầu sạch
delete from public.trader_nav; delete from public.trader_trades; delete from public.trader_positions; delete from public.trader_orders;
