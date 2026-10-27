-- Kế hoạch giao dịch chi tiết cho sổ lệnh agent (cắt lỗ, chốt lời, thời gian giữ, độ tự tin, điều kiện theo dõi).
alter table public.trader_orders
  add column if not exists stop_loss        double precision,
  add column if not exists take_profit      double precision,
  add column if not exists horizon_sessions integer,
  add column if not exists confidence       text,
  add column if not exists condition        text;
