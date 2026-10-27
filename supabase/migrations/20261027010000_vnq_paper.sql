-- (1) Cột mô tả trạng thái tại t cho snapshot dự báo; (2) danh mục mô phỏng TN06-R.

alter table public.predictions_daily
  add column if not exists industry    text,
  add column if not exists value_score double precision,
  add column if not exists regime      text,
  add column if not exists trend_score double precision;

-- Mỗi tín hiệu TN06-R = 1 dòng. status: planned (vào phiên tới) | open | closed | skipped_*
create table if not exists public.paper_trades (
  signal_date     date not null,
  ticker          text not null,
  industry        text,
  rsi14           double precision,
  source          text,
  status          text not null,
  weight          double precision,   -- tỷ trọng NAV khi vào lệnh (0,10)
  amount          double precision,   -- số tiền vào lệnh trên NAV ban đầu = 1
  entry_date      date,
  entry_price     double precision,   -- giá mở cửa phiên vào (nghìn đồng)
  exit_date       date,
  exit_price      double precision,   -- giá đóng cửa phiên bán
  mark_price      double precision,   -- đóng cửa ngày dữ liệu (vị thế đang mở)
  signal_close    double precision,
  pnl             double precision,   -- lãi/lỗ sau phí của lệnh (đang mở: tạm tính)
  held_sessions   integer,
  sessions_left   integer,            -- 1 = bán ở phiên kế tiếp
  data_date       date not null,      -- ngày dữ liệu của lần tính
  primary key (signal_date, ticker)
);

create table if not exists public.paper_nav (
  date         date primary key,
  nav          double precision not null,   -- NAV ban đầu = 1
  cash_pct     double precision,
  n_open       integer,
  vnindex_rel  double precision            -- VNINDEX / VNINDEX ngày bắt đầu
);

do $$
declare t text;
begin
  foreach t in array array['paper_trades','paper_nav'] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('drop policy if exists "read_authenticated" on public.%I', t);
    execute format('create policy "read_authenticated" on public.%I for select to authenticated using (true)', t);
  end loop;
end $$;
