"""TN07 — feature, label, universe point-in-time. Mọi feature tại t chỉ dùng dữ liệu đến hết t."""
import pandas as pd, numpy as np

PANEL = '/mnt/user-data/uploads/panel.parquet'
VNI = '/mnt/user-data/attachments/edd81786-5462-5b5e-834d-1a0c6a72417a/14534939-vnindex.parquet'
LIQ_MIN = 5e9          # 5 tỷ VND/ngày (đề xuất, CHƯA XÁC NHẬN)
H = 5

def ema(s, n): return s.ewm(span=n, adjust=False, min_periods=n).mean()

def wilder(s, n): return s.ewm(alpha=1/n, adjust=False, min_periods=n).mean()

def per_ticker(d):
    d = d.sort_values('date').copy()
    c, h, l, o, v = d.close, d.high, d.low, d.open, d.volume
    pc = c.shift(1)
    d['ret1'] = c.pct_change(); d['ret5'] = c.pct_change(5)
    d['ret20'] = c.pct_change(20); d['ret60'] = c.pct_change(60)
    e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    d['dist_ema20'] = c/e20-1; d['dist_ema50'] = c/e50-1; d['dist_ema200'] = c/e200-1
    d['ema20_50'] = e20/e50-1; d['ema50_slope10'] = e50/e50.shift(10)-1
    tr = pd.concat([h-l, (h-pc).abs(), (l-pc).abs()], axis=1).max(axis=1)
    atr = wilder(tr, 14); d['atr14_pct'] = atr/c
    up, dn = h.diff(), -l.diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdi = 100*wilder(pd.Series(pdm, index=d.index), 14)/atr
    mdi = 100*wilder(pd.Series(mdm, index=d.index), 14)/atr
    dx = 100*(pdi-mdi).abs()/(pdi+mdi)
    d['adx14'] = wilder(dx, 14); d['di_diff'] = (pdi-mdi)/(pdi+mdi)
    delta = c.diff(); g = wilder(delta.clip(lower=0), 14); ls = wilder(-delta.clip(upper=0), 14)
    d['rsi14'] = 100-100/(1+g/ls)
    macd = ema(c, 12)-ema(c, 26); d['macd_hist'] = (macd-ema(macd, 9))/c
    d['volat20'] = d.ret1.rolling(20).std(); d['volat60'] = d.ret1.rolling(60).std()
    d['vol_ratio20'] = v/v.rolling(20).mean()
    val = d.gt_khop.fillna(0)
    d['liq20'] = val.rolling(20, min_periods=15).mean()
    d['log_liq20'] = np.log1p(d.liq20)
    for n in (20, 60):
        hi, lo = h.rolling(n).max(), l.rolling(n).min()
        d[f'pos{n}'] = (c-lo)/(hi-lo)
    d['dd252'] = c/h.rolling(252, min_periods=120).max()-1
    d['up252'] = c/l.rolling(252, min_periods=120).min()-1
    d['clv'] = ((c-l)-(h-c))/(h-l).replace(0, np.nan)
    # cấu trúc đỉnh đáy: 10 phiên gần vs 10 phiên trước đó
    d['hh10'] = h.rolling(10).max()/h.shift(10).rolling(10).max()-1
    d['hl10'] = l.rolling(10).min()/l.shift(10).rolling(10).min()-1
    d['nbars'] = np.arange(1, len(d)+1)
    # ---- label (tương lai, chỉ dùng làm target) ----
    o1 = o.shift(-1); c5 = c.shift(-H)
    d['open_t1'] = o1; d['close_t5'] = c5
    d['open_gap_t1'] = o1/c-1
    d['ret_t5_day'] = c5/c.shift(-(H-1))-1        # biến động phiên t+5 (kiểm tra kẹt sàn)
    d['close_t6'] = c.shift(-(H+1))
    d['fwd_ret_5'] = c5/o1-1
    d['y_bin'] = (d.fwd_ret_5 > 0.5*d.atr14_pct).astype(float)
    d.loc[d.fwd_ret_5.isna(), 'y_bin'] = np.nan
    return d

def build():
    p = pd.read_parquet(PANEL)
    p = p[p.ticker.str.fullmatch(r'[A-Z0-9]{3}') & (p.date >= '2022-01-01')].copy()
    # suy luận sàn từ biên độ (xấp xỉ, không có cột sàn trong dữ liệu)
    p = p.sort_values(['ticker', 'date'])
    r = p.groupby('ticker').close.pct_change().abs()
    q = r[p.date >= '2024-01-01'].groupby(p.ticker).quantile(0.999)
    exch = pd.cut(q, [-1, 0.072, 0.102, 9], labels=['HOSE', 'HNX', 'UPCOM']).astype(str)
    p['exch_inferred'] = p.ticker.map(exch).fillna('UPCOM')
    p['limit'] = p.exch_inferred.map({'HOSE': 0.07, 'HNX': 0.10, 'UPCOM': 0.15})
    f = pd.concat([per_ticker(d) for _, d in p.groupby('ticker')], ignore_index=True)
    # thị trường
    v = pd.read_parquet(VNI).sort_values('date')
    v['vni_ret5'] = v.close.pct_change(5); v['vni_ret20'] = v.close.pct_change(20)
    v['vni_dist_ema50'] = v.close/ema(v.close, 50)-1
    f = f.merge(v[['date', 'vni_ret5', 'vni_ret20', 'vni_dist_ema50']], on='date', how='left')
    # universe point-in-time
    f['eligible'] = (f.liq20 >= LIQ_MIN) & (f.nbars >= 200) & (f.volume > 0)
    f['near_ceiling'] = (f.ret1 >= f.limit-0.005).astype(int)
    f['near_floor'] = (f.ret1 <= -(f.limit-0.005)).astype(int)
    e = f[f.eligible].copy()
    # breadth trong universe
    br = e.groupby('date').dist_ema50.apply(lambda s: (s > 0).mean()).rename('breadth_ema50')
    e = e.merge(br, on='date', how='left')
    # value proxy (technical_proxy): rank TB của drawdown sâu, dưới EMA200, biến động thấp, thanh khoản cao
    g = e.groupby('date')
    e['value_score'] = (g.dd252.rank(pct=True, ascending=False) + g.dist_ema200.rank(pct=True, ascending=False)
                        + g.volat60.rank(pct=True, ascending=False) + g.liq20.rank(pct=True)) / 4
    e['value_mode'] = 'technical_proxy'
    e['value_top30'] = g.value_score.rank(pct=True) >= 0.70
    # regime & trend_score từng mã
    up = (e.close > e.close/(1+e.dist_ema50)) & (e.ema20_50 > 0) & (e.adx14 >= 20)
    dn = (e.dist_ema50 < 0) & (e.ema20_50 < 0) & (e.adx14 >= 20)
    e['regime'] = np.select([up, dn], ['Uptrend', 'Downtrend'], 'Sideways')
    e['trend_score'] = 0.5*np.tanh(10*e.ema20_50) + 0.5*e.di_diff
    # rank cross-sectional
    for col in ['ret5', 'ret20', 'vol_ratio20', 'volat20', 'rsi14']:
        e[f'{col}_xr'] = g[col].rank(pct=True)
    return e

FEATURES = ['ret1', 'ret5', 'ret20', 'ret60', 'dist_ema20', 'dist_ema50', 'dist_ema200', 'ema20_50',
            'ema50_slope10', 'atr14_pct', 'adx14', 'di_diff', 'rsi14', 'macd_hist', 'volat20', 'volat60',
            'vol_ratio20', 'log_liq20', 'pos20', 'pos60', 'dd252', 'up252', 'clv', 'hh10', 'hl10',
            'vni_ret5', 'vni_ret20', 'vni_dist_ema50', 'breadth_ema50',
            'ret5_xr', 'ret20_xr', 'vol_ratio20_xr', 'volat20_xr', 'rsi14_xr', 'value_score', 'trend_score']

if __name__ == '__main__':
    e = build()
    e.to_parquet('dataset.parquet')
    print(e.shape, e.date.min(), e.date.max())
    print(e.groupby(e.date.dt.year).ticker.nunique())
    print(e.exch_inferred.value_counts(normalize=True))
    print(e.groupby('date').ticker.count().describe())
    print('base rate y_bin 2025+', e[e.date >= '2025-01-01'].y_bin.mean())
