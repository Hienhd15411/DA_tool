"""Mô phỏng 4 danh mục paper trading (docs/09_TRADER_EXPERIMENT.md). Tính lại toàn bộ từ đầu mỗi lần chạy.

python tools/trader_sim.py --panel P --vnindex V [--signals predictions.parquet] [--publish]
  A: sổ lệnh trader/orders/<phiên>.json (bỏ file commit sau 09:00 ICT của phiên đó)
  B: tín hiệu TN06-R (tn06r_signal) từ predictions (Supabase hoặc file parquet)
  C: mua & giữ VNINDEX từ giá mở cửa phiên đầu
  D: bốc thăm đối ứng từng lệnh của A
Ghi tools/out/trader/{nav,trades,positions,orders}.csv; --publish đẩy lên Supabase (bảng trader_*).
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, json, math, os, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
START, CAPITAL = pd.Timestamp(os.environ.get('TRADER_START', '2026-10-28')), 100_000_000
FEE, TAX, LOT, NEAR = 0.0015, 0.001, 100, 0.005
MAX_W, MAX_IND, MIN_CASH = 0.20, 3, 0.10
ICT = dt.timezone(dt.timedelta(hours=7))
OUT = ROOT / 'tools' / 'out' / 'trader'


def commit_time(path):
    try:
        s = subprocess.run(['git', 'log', '--diff-filter=A', '--format=%cI', '-1', '--', str(path)], capture_output=True, text=True, cwd=ROOT).stdout.strip()
        return dt.datetime.fromisoformat(s) if s else None
    except Exception:
        return None


class Book:
    def __init__(self, name):
        self.name, self.cash, self.pos, self.trades, self.nav = name, float(CAPITAL), {}, [], []   # pos[t] = list of [qty, buy_i, px]

    def qty(self, t): return sum(l[0] for l in self.pos.get(t, []))

    def sellable(self, t, i, typ): return sum(l[0] for l in self.pos.get(t, []) if i - l[1] >= (3 if typ == 'ATO' else 2))

    def value(self, px):
        return self.cash + sum(self.qty(t) * px.get(t, np.nan) * 1000 * (1 - FEE - TAX) for t in self.pos if self.qty(t))

    def log(self, **k): self.trades.append(dict(portfolio=self.name, **k))


def fill_price(o, row, side):
    """Giá khớp theo loại lệnh; None nếu không khớp."""
    typ = o.get('type', 'ATO')
    if typ == 'ATO': return row.open
    if typ == 'ATC': return row.close
    lim = float(o['limit'])
    if side == 'BUY':
        return row.open if row.open <= lim else (lim if row.low <= lim else None)
    return row.open if row.open >= lim else (lim if row.high >= lim else None)


def run(panel, vni, signals, orders_dir, industry, now):
    panel = panel.sort_values(['ticker', 'date']).copy()
    panel['nb'] = panel.groupby('ticker').cumcount()   # số phiên lịch sử (trên toàn bộ dữ liệu)
    panel = panel[panel.date >= START - pd.Timedelta(days=60)].copy()
    if now.time() < dt.time(15, 30):   # không dùng nến của phiên chưa đóng
        panel = panel[panel.date.dt.date < now.date()]; vni = vni[vni.date.dt.date < now.date()]
    from vnq.features import exchange_limits
    lim, _ = exchange_limits(panel.rename(columns={}), {'paths': {'exchange_map': str(ROOT / 'engine/data/exchange_map.csv')}})
    lim = lim.map({'HOSE': 0.07, 'HNX': 0.10, 'UPCOM': 0.15}).to_dict()
    panel['prev'] = panel.sort_values('date').groupby('ticker').close.shift(1)
    panel['val'] = panel.close * panel.volume * 1000
    panel['liq20'] = panel.sort_values('date').groupby('ticker').val.transform(lambda s: s.rolling(20, min_periods=15).mean())
    dates = sorted(d for d in panel.date.unique() if d >= START)
    bars = {d: g.set_index('ticker') for d, g in panel[panel.date.isin(dates)].groupby('date')}
    A, B, C, D = Book('A'), Book('B'), Book('C'), Book('D')
    dmap, a_orders, rejected, d_retry = {}, [], [], {}   # d_retry[mã D] = số lượng còn phải bán
    vni = vni.set_index('date')
    c_units = None
    sig = signals[signals.tn06r_signal.astype(bool)].copy() if len(signals) else signals
    if len(sig): sig['data_date'] = pd.to_datetime(sig.data_date)
    b_exit = {}   # ticker -> phiên index phải bán (ATC)

    for i, d in enumerate(dates):
        bar = bars[d]; px = bar.close.to_dict()
        ok_px = lambda t: t in bar.index and np.isfinite(bar.at[t, 'open'])
        ceil = lambda t: bar.at[t, 'prev'] * (1 + lim.get(t, 0.07) - NEAR)
        floor = lambda t: bar.at[t, 'prev'] * (1 - lim.get(t, 0.07) + NEAR)
        nav_open = {b.name: b.value(bar.open.to_dict()) for b in (A, B, D)}

        def buy(book, t, value, o, extra=''):
            if not ok_px(t): book.log(session=d, ticker=t, side='BUY', status='no_price', note=extra); return 0
            p = fill_price(o, bar.loc[t], 'BUY')
            if p is None: book.log(session=d, ticker=t, side='BUY', status='unfilled_limit', note=extra); return 0
            if p >= ceil(t): book.log(session=d, ticker=t, side='BUY', status='unfilled_ceiling', price=p, note=extra); return 0
            q = int(min(value, book.cash / (1 + FEE)) // (p * 1000 * LOT)) * LOT
            if q <= 0: book.log(session=d, ticker=t, side='BUY', status='no_cash', note=extra); return 0
            amt = q * p * 1000; fee = amt * FEE
            book.cash -= amt + fee; book.pos.setdefault(t, []).append([q, i, p])
            book.log(session=d, ticker=t, side='BUY', status='filled', type=o.get('type'), qty=q, price=p, value=amt, fee=fee, tax=0.0, note=extra)
            return amt

        def sell(book, t, q_req, o, extra=''):
            typ = o.get('type', 'ATO')
            avail = book.sellable(t, i, typ)
            q = avail if q_req == 'all' else min(int(q_req), avail)
            if q <= 0: book.log(session=d, ticker=t, side='SELL', status='not_sellable_T+2' if book.qty(t) else 'no_position', note=extra); return 0, 0
            if not ok_px(t): book.log(session=d, ticker=t, side='SELL', status='no_price', note=extra); return 0, 0
            p = fill_price(o, bar.loc[t], 'SELL')
            if p is None: book.log(session=d, ticker=t, side='SELL', status='unfilled_limit', note=extra); return 0, 0
            if p <= floor(t): book.log(session=d, ticker=t, side='SELL', status='unfilled_floor', price=p, note=extra); return 0, 0
            total = book.qty(t); left = q
            cost = 0.0
            for l in sorted(book.pos[t], key=lambda l: l[1]):
                if i - l[1] < (3 if typ == 'ATO' else 2): continue
                take = min(l[0], left); l[0] -= take; left -= take; cost += take * l[2] * 1000
                if left == 0: break
            book.pos[t] = [l for l in book.pos[t] if l[0] > 0]
            if not book.pos[t]: del book.pos[t]
            amt = q * p * 1000; fee, tax = amt * FEE, amt * TAX
            book.cash += amt - fee - tax
            book.log(session=d, ticker=t, side='SELL', status='filled', type=typ, qty=q, price=p, value=amt, fee=fee, tax=tax,
                     pnl=amt - fee - tax - cost * (1 + FEE), note=extra)
            return q, total

        # D: bán lại phần đối ứng chưa khớp ở phiên trước (ATO)
        for t, q in list(d_retry.items()):
            got, _ = sell(D, t, q, {'type': 'ATO'}, 'bán lại đối ứng chưa khớp')
            left = (D.qty(t) if q == 'all' else q - got)
            if got and (q == 'all' or left <= 0): d_retry.pop(t)
            elif got: d_retry[t] = left
        # ---------- A: sổ lệnh ----------
        f = orders_dir / f'{d:%Y-%m-%d}.json'
        plan = []
        if f.exists():
            ct = commit_time(f)
            deadline = dt.datetime.combine(d.date(), dt.time(9, 0), ICT)
            js = json.loads(f.read_text(encoding='utf-8'))
            if ct is not None and ct > deadline:
                rejected.append(dict(session=d, ticker='*', reason=f'sổ lệnh commit {ct.isoformat()} sau 09:00 phiên → bỏ cả file'))
            else:
                plan = js.get('orders', [])
            for o in js.get('orders', []):
                a_orders.append(dict(session=d.strftime('%Y-%m-%d'), decided_at=js.get('decided_at'), committed_at=ct.isoformat() if ct else None,
                                     side=o.get('side'), ticker=o.get('ticker'), type=o.get('type'), limit=o.get('limit'),
                                     value_vnd=o.get('value_vnd'), qty=str(o.get('qty', '')), reason=o.get('reason'),
                                     sources=json.dumps(o.get('sources', []), ensure_ascii=False), market_view=js.get('market_view'),
                                     risk_plan=js.get('risk_plan')))
        order_rank = {'SELL': {'ATO': 0, 'LO': 2, 'ATC': 3}, 'BUY': {'ATO': 1, 'LO': 2, 'ATC': 4}}
        plan = sorted(plan, key=lambda o: order_rank[o['side']].get(o.get('type', 'ATO'), 2))
        elig = set(bar.index[(bar.liq20 >= 5e9) & (bar.nb >= 200)])
        for o in plan:
            t = o['ticker'].upper()
            if o['side'] == 'SELL':
                q, total = sell(A, t, o.get('qty', 'all'), o, 'A')
                if q and t in dmap:   # D bán mã đối ứng cùng tỷ lệ
                    dt_ = dmap[t]; frac = q / total
                    dq = D.qty(dt_)
                    want = 'all' if frac >= 0.999 else int(dq * frac // LOT * LOT)
                    got, _ = sell(D, dt_, want, o, f'đối ứng A:{t}')
                    if not got and D.qty(dt_): d_retry[dt_] = want
                continue
            if t not in elig:
                rejected.append(dict(session=d, ticker=t, reason='ngoài universe đủ điều kiện')); continue
            nav = nav_open['A']
            room = MAX_W * nav - A.qty(t) * bar.at[t, 'open'] * 1000
            inds = {industry.get(x) for x in A.pos} if industry else set()
            if industry and industry.get(t) and sum(industry.get(x) == industry.get(t) for x in A.pos if x != t) >= MAX_IND:
                rejected.append(dict(session=d, ticker=t, reason='quá 3 mã cùng ngành')); continue
            v = min(float(o.get('value_vnd', 0)), room, max(0.0, A.cash - MIN_CASH * nav))
            if v <= 0:
                rejected.append(dict(session=d, ticker=t, reason='vượt 20% NAV hoặc chạm sàn 10% tiền mặt')); continue
            amt = buy(A, t, v, o, 'A')
            if amt:   # D: bốc thăm 1 mã đủ điều kiện, cùng số tiền, cùng loại lệnh ATO/ATC (LO → ATO)
                if t not in dmap:
                    pool = sorted(elig - set(D.pos))
                    seed = int(hashlib.sha256(f'{d:%Y%m%d}{t}'.encode()).hexdigest(), 16) % (2 ** 32)
                    dmap[t] = pool[np.random.default_rng(seed).integers(len(pool))]
                buy(D, dmap[t], amt, {'type': 'ATC' if o.get('type') == 'ATC' else 'ATO'}, f'đối ứng A:{t}')

        # ---------- B: TN06-R ----------
        for t, ei in list(b_exit.items()):
            if ei <= i:
                q, _ = sell(B, t, 'all', {'type': 'ATC'}, 'TN06-R hết 5 phiên')
                if q or not B.qty(t): b_exit.pop(t)
        prev_d = dates[i - 1] if i else None
        sig_d = sig[sig.data_date == (prev_d if prev_d is not None else START - pd.Timedelta(days=1))] if len(sig) else []
        if i == 0 and len(sig):   # phiên đầu: tín hiệu của ngày dữ liệu ngay trước START
            last = sig[sig.data_date < START].data_date.max()
            sig_d = sig[sig.data_date == last] if pd.notna(last) else sig.iloc[0:0]
        for r in (sig_d.sort_values('rsi14').itertuples() if len(sig_d) else []):
            if len(B.pos) >= 10 or r.ticker in B.pos: continue
            if industry and sum(industry.get(x) == industry.get(r.ticker) for x in B.pos) >= MAX_IND: continue
            if buy(B, r.ticker, nav_open['B'] / 10, {'type': 'ATO'}, 'TN06-R'):
                b_exit[r.ticker] = i + 4   # tín hiệu t → mua t+1 → bán ATC t+5

        # ---------- C: VNINDEX ----------
        if c_units is None and d in vni.index:
            c_units = CAPITAL * (1 - FEE) / vni.at[d, 'open']; C.cash = 0.0
            C.log(session=d, ticker='VNINDEX', side='BUY', status='filled', type='ATO', qty=round(c_units, 4), price=vni.at[d, 'open'], value=CAPITAL, fee=CAPITAL * FEE / (1 + FEE), tax=0.0)
        c_nav = c_units * vni.close.asof(d) * (1 - FEE - TAX) if c_units else C.cash

        for b in (A, B, D):
            b.nav.append(dict(date=d, portfolio=b.name, nav=b.value(px), cash=b.cash, n_pos=len(b.pos)))
        C.nav.append(dict(date=d, portfolio='C', nav=c_nav, cash=0.0, n_pos=1))

    nav = pd.DataFrame([x for b in (A, B, C, D) for x in b.nav])
    if len(nav):
        nav = nav.sort_values(['portfolio', 'date'])
        nav['pnl_day'] = nav.groupby('portfolio').nav.diff().fillna(nav.nav - CAPITAL)
        nav['ret_cum'] = nav.nav / CAPITAL - 1
    trades = pd.DataFrame([x for b in (A, B, C, D) for x in b.trades])
    last = dates[-1] if dates else None
    pos = []
    for b in (A, B, D):
        for t, lots in b.pos.items():
            q = sum(l[0] for l in lots); cost = sum(l[0] * l[2] for l in lots) / q
            p = bars[last].close.get(t, np.nan) if last is not None else np.nan
            pos.append(dict(portfolio=b.name, ticker=t, qty=q, avg_cost=cost, last_price=p, as_of=last,
                            mkt_value=q * p * 1000, pnl=(p * (1 - FEE - TAX) - cost * (1 + FEE)) * q * 1000,
                            first_buy=dates[min(l[1] for l in lots)]))
    if c_units: pos.append(dict(portfolio='C', ticker='VNINDEX', qty=c_units, avg_cost=CAPITAL / c_units, last_price=vni.close.asof(last),
                                as_of=last, mkt_value=c_units * vni.close.asof(last), pnl=nav[nav.portfolio == 'C'].nav.iloc[-1] - CAPITAL, first_buy=dates[0]))
    return nav, trades, pd.DataFrame(pos), pd.DataFrame(a_orders), pd.DataFrame(rejected), dmap


def report(nav, trades, pos, orders, rej, dmap, next_orders):
    print('== TRADER ==')
    if nav.empty:
        print(f'Chưa có phiên nào từ {START:%d/%m/%Y}. Vốn mỗi danh mục {CAPITAL:,.0f} đ.')
    else:
        d = nav.date.max(); t = nav[nav.date == d].set_index('portfolio')
        name = {'A': 'Agent', 'B': 'TN06-R', 'C': 'VNINDEX', 'D': 'Ngẫu nhiên'}
        for k in 'ABCD':
            if k in t.index:
                r = t.loc[k]
                print(f'{k} {name[k]:10s} NAV {r.nav:,.0f} đ · hôm nay {r.pnl_day:+,.0f} đ · lũy kế {r.ret_cum * 100:+.2f}% · {int(r.n_pos)} mã · tiền mặt {r.cash:,.0f}')
        td = trades[trades.session == d] if len(trades) else trades
        for r in td.itertuples():
            print(f'  {r.portfolio} {r.side} {r.ticker} {r.status} ' + (f'{int(r.qty)} cp @ {r.price:.2f}' if r.status == 'filled' and r.portfolio != 'C' else '') + (f' ({r.note})' if isinstance(r.note, str) and r.note else ''))
    for r in (rej.itertuples() if len(rej) else []):
        print(f'  A TỪ CHỐI {r.session:%d/%m} {r.ticker}: {r.reason}')
    for r in (pos.itertuples() if len(pos) else []):
        print(f'  GIỮ {r.portfolio} {r.ticker} {r.qty:,.0f} · vốn {r.avg_cost:.2f} · giá {r.last_price:.2f} · lời/lỗ {r.pnl:+,.0f} đ')
    if dmap: print('  D đối ứng:', dmap)
    print('Sổ lệnh A phiên tới:', next_orders or 'chưa có')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', required=True); ap.add_argument('--vnindex', required=True)
    ap.add_argument('--signals'); ap.add_argument('--industry', default=str(ROOT / 'engine/data/seed/industry.csv'))
    ap.add_argument('--publish', action='store_true')
    a = ap.parse_args()
    now = dt.datetime.now(ICT)
    panel, vni = pd.read_parquet(a.panel), pd.read_parquet(a.vnindex)
    if a.signals: signals = pd.read_parquet(a.signals)
    elif os.environ.get('SUPABASE_URL'):
        import requests
        U, K = os.environ['SUPABASE_URL'].rstrip('/'), os.environ['SUPABASE_SERVICE_ROLE_KEY']
        r = requests.get(f'{U}/rest/v1/predictions_daily', headers={'apikey': K, 'Authorization': f'Bearer {K}'}, timeout=60,
                         params={'select': 'data_date,ticker,rsi14,tn06r_signal', 'tn06r_signal': 'eq.true', 'data_date': 'gte.2026-10-20'})
        r.raise_for_status(); signals = pd.DataFrame(r.json())
    else: signals = pd.DataFrame(columns=['data_date', 'ticker', 'rsi14', 'tn06r_signal'])
    ind = pd.read_csv(a.industry).set_index('ticker').industry.to_dict() if Path(a.industry).exists() else {}
    odir = Path(os.environ.get('TRADER_ORDERS', ROOT / 'trader' / 'orders'))
    nav, trades, pos, orders, rej, dmap = run(panel, vni, signals, odir, ind, now)
    nxt = sorted(odir.glob('*.json'))
    nxt = [p.name for p in nxt if p.stem > (nav.date.max().strftime('%Y-%m-%d') if len(nav) else '0')]
    report(nav, trades, pos, orders, rej, dmap, nxt)
    OUT.mkdir(parents=True, exist_ok=True)
    for nm, df in dict(nav=nav, trades=trades, positions=pos, orders=orders, rejected=rej).items(): df.to_csv(OUT / f'{nm}.csv', index=False)
    if a.publish: publish(nav, trades, pos, orders, rej)


def publish(nav, trades, pos, orders, rej):
    sys.path.insert(0, str(ROOT / 'engine'))
    from vnq.supa import Supa, records
    sb = Supa()
    def ds(df, cols):
        df = df.copy()
        for c in cols:
            if c in df: df[c] = pd.to_datetime(df[c]).dt.strftime('%Y-%m-%d')
        return df
    try:
        n = {}
        if len(nav): n['trader_nav'] = sb.upsert('trader_nav', records(ds(nav, ['date'])), 'date,portfolio')
        if len(trades):
            tr = ds(trades, ['session']).reset_index(drop=True); tr['seq'] = tr.index
            n['trader_trades'] = sb.upsert('trader_trades', records(tr), 'seq')
        sb.delete_where('trader_positions', 'portfolio', 'neq.__none__')
        if len(pos): n['trader_positions'] = sb.upsert('trader_positions', records(ds(pos, ['as_of', 'first_buy'])), 'portfolio,ticker')
        if len(orders): n['trader_orders'] = sb.upsert('trader_orders', records(orders.reset_index().rename(columns={'index': 'idx'})), 'session,idx')
        print('publish', n)
    except RuntimeError as e:
        print('BỎ QUA publish (bảng trader_* chưa có?):', str(e)[:200])


if __name__ == '__main__':
    main()
