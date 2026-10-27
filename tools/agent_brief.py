"""Bản tin cho agent vận hành: tổng quan thị trường · lệnh phiên tới (mô phỏng TN06-R) · giữ bao lâu thì hòa vốn.

Chỉ đọc (Storage + Supabase), in ra log để agent tổng hợp báo cáo. Không ghi gì.
Cần env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY. Tùy chọn: BRIEF_CAPITAL_MILLION (mặc định 100).
"""
import io, os, time, datetime as dt
import numpy as np, pandas as pd, requests

U, K = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SERVICE_ROLE_KEY']
H = {'apikey': K, 'Authorization': f'Bearer {K}'}
CAP = float(os.environ.get('BRIEF_CAPITAL_MILLION', 100)) * 1e6
FEE, TAX = 0.0015, 0.001                      # engine/config.yaml costs
BE = (1 + FEE) / (1 - FEE - TAX) - 1           # mức tăng giá cần để hòa vốn sau phí 2 chiều + thuế bán
ICT = dt.timezone(dt.timedelta(hours=7))


def storage(key):
    r = requests.get(f'{U}/storage/v1/object/vnq-data/{key}', headers={**H, 'Cache-Control': 'no-cache'}, params={'t': time.time()}, timeout=120)
    r.raise_for_status(); return pd.read_parquet(io.BytesIO(r.content))


def rest(t, **p):
    r = requests.get(f'{U}/rest/v1/{t}', headers=H, params=p, timeout=60); r.raise_for_status(); return r.json()


def pct(x): return '—' if x is None or pd.isna(x) else f'{x * 100:+.2f}%'


now = dt.datetime.now(ICT)
panel, vni = storage('data/panel.parquet'), storage('data/vnindex.parquet').sort_values('date')
if now.time() < dt.time(15, 30):   # cùng quy tắc engine: không dùng nến của phiên chưa đóng
    panel, vni = panel[panel.date.dt.date < now.date()], vni[vni.date.dt.date < now.date()]
run = rest('daily_runs', select='data_date,n_eligible,regime_universe', order='data_date.desc', limit=1)[0]
d0 = pd.Timestamp(run['data_date'])

# ---------- 1. tổng quan thị trường ----------
v = vni.set_index('date').close
ema50, ema200 = v.ewm(span=50, adjust=False).mean(), v.ewm(span=200, adjust=False).mean()
c = v.asof(d0)
ch = lambda n: c / v[v.index <= d0].iloc[-1 - n] - 1
p = panel[panel.date <= d0].sort_values(['ticker', 'date'])
p['r1'] = p.groupby('ticker').close.pct_change()
p['ema50'] = p.groupby('ticker').close.transform(lambda s: s.ewm(span=50, adjust=False, min_periods=50).mean())
day = p[p.date == d0]
val = p.assign(v=p.close * p.volume * 1000).groupby('date').v.sum()
liq_ratio = val.asof(d0) / val[val.index < d0].tail(20).mean()
print('== MARKET ==')
print(f'Ngày {d0:%d/%m/%Y} · VNINDEX {c:,.2f} ({pct(ch(1))} 1 phiên, {pct(ch(5))} 5 phiên, {pct(ch(20))} 20 phiên)')
print(f'VNINDEX so với EMA50 {pct(c / ema50.asof(d0) - 1)} · EMA200 {pct(c / ema200.asof(d0) - 1)} '
      f'→ tầng 1 TN06-R {"BẬT (thị trường điều chỉnh)" if c < ema50.asof(d0) else "TẮT"}')
print(f'Độ rộng: {int((day.r1 > 0).sum())} tăng / {int((day.r1 < 0).sum())} giảm / {int((day.r1 == 0).sum())} đứng · '
      f'{(day.close > day.ema50).mean() * 100:.0f}% mã trên EMA50 · giá trị khớp ước tính {liq_ratio:.2f}× TB20')
print(f'Xu hướng universe ({run["n_eligible"]} mã đủ điều kiện): {run["regime_universe"]}')

# ---------- 2. lệnh phiên tới (mô phỏng) ----------
tr = pd.DataFrame(rest('paper_trades', select='*', order='signal_date.desc'))
nav = rest('paper_nav', select='*', order='date.desc', limit=1)
navv = nav[0]['nav'] if nav else 1.0
print('\n== PLAN (danh mục mô phỏng TN06-R, chưa đạt kiểm định) ==')
print(f'NAV mô phỏng {pct(navv - 1)} từ 01/07 · VNINDEX {pct(nav[0]["vnindex_rel"] - 1) if nav else "—"} · '
      f'đang giữ {int((tr.status == "open").sum()) if len(tr) else 0}/10 · vốn quy đổi {CAP / 1e6:.0f} tr')
last_px = p[p.date == d0].set_index('ticker').close
for _, t in (tr[tr.status == 'planned'] if len(tr) else tr).iterrows():
    px = t.signal_close or last_px.get(t.ticker)
    amt = CAP * 0.1 * navv
    print(f'VÀO  {t.ticker:4s} mở cửa phiên tới · 10% NAV ≈ {amt / 1e6:.1f} tr ≈ {int(amt / (px * 1000) // 100 * 100)} cp '
          f'(tham chiếu {px:.2f}) · hòa vốn khi giá ≥ {px * (1 + BE):.2f} · bán ATC sau 5 phiên')
op = tr[tr.status == 'open'] if len(tr) else tr
for _, t in op.iterrows():
    tag = 'THOÁT' if t.sessions_left <= 1 else 'GIỮ '
    be = t.entry_price * (1 + BE)
    print(f'{tag} {t.ticker:4s} vào {t.entry_date} giá {t.entry_price:.2f} · hòa vốn {be:.2f} · hiện {pct(t.pnl)} sau phí · '
          f'{"bán ATC phiên tới (100%)" if t.sessions_left <= 1 else f"còn {int(t.sessions_left)} phiên"}')
if not len(tr) or not ((tr.status == 'planned') | (tr.status == 'open')).any():
    print('Không vào / không thoát lệnh nào ở phiên tới.')

# ---------- 3. giữ bao lâu thì hòa vốn (lịch sử lệnh đã đóng) ----------
cl = tr[tr.status == 'closed'] if len(tr) else tr
print('\n== BREAKEVEN ==')
print(f'Hòa vốn cần giá tăng ≥ {BE * 100:.2f}% so với giá mua (phí {FEE * 100:.2f}%/chiều + thuế bán {TAX * 100:.1f}%)')
if len(cl):
    cp = panel.pivot(index='date', columns='ticker', values='close')
    first = []
    for _, t in cl.iterrows():
        path = cp.loc[pd.Timestamp(t.entry_date):pd.Timestamp(t.exit_date), t.ticker].dropna()
        hit = np.where(path.values >= t.entry_price * (1 + BE))[0]
        first.append(hit[0] + 1 if len(hit) else None)   # phiên thứ mấy (1 = ngay phiên mua) đóng cửa ≥ giá hòa vốn
    f = pd.Series(first, dtype='float')
    print(f'{len(cl)} lệnh đã đóng: {f.notna().mean() * 100:.0f}% từng đóng cửa ≥ giá hòa vốn trong 5 phiên '
          f'(trung vị ở phiên thứ {f.median():.0f}); kết thúc có lãi {(cl.pnl > 0).mean() * 100:.0f}%; '
          f'lãi/lỗ TB {pct(cl.pnl.mean())}/lệnh; tốt nhất {pct(cl.pnl.max())}, tệ nhất {pct(cl.pnl.min())}')
    exp = cl.pnl.mean()
    print(f'Kỳ vọng hiện tại {pct(exp)}/lệnh → ' + ('dương: trung bình mỗi lệnh 5 phiên có lãi sau phí' if exp > 0 else
          'ÂM: theo lịch sử, giữ đủ 5 phiên trung bình chưa hòa vốn; kéo dài thời gian giữ không nằm trong luật đã kiểm định'))
