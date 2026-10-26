"""Nạp/cập nhật dữ liệu + QC. Upsert theo (ticker, date); phát hiện điều chỉnh quyền ở phần chồng lấn."""
import pandas as pd, numpy as np, shutil, datetime as dt, logging
from pathlib import Path

log = logging.getLogger('vnq')
COLS = ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'gt_khop']
ALIASES = {'time': 'date', 'tradingdate': 'date', 'symbol': 'ticker', 'code': 'ticker', 'value': 'gt_khop',
           'gtgd': 'gt_khop', 'trading_value': 'gt_khop'}


def normalize(df):
    df = df.rename(columns={c: ALIASES.get(c.lower().strip(), c.lower().strip()) for c in df.columns})
    miss = {'ticker', 'date', 'open', 'high', 'low', 'close', 'volume'} - set(df.columns)
    if miss:
        raise ValueError(f'Thiếu cột {miss}')
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).dt.normalize()
    df['ticker'] = df['ticker'].astype(str).str.upper().str.strip()
    if 'gt_khop' not in df:
        df['gt_khop'] = np.nan
    # nếu thiếu GTGD: xấp xỉ = close(nghìn đồng) * volume * 1000
    est = df['gt_khop'].isna()
    df.loc[est, 'gt_khop'] = df.loc[est, 'close'] * df.loc[est, 'volume'] * 1000
    keep = COLS + [c for c in ('gt_thoathuan', 'kl_khop', 'kl_thoathuan', 'industry') if c in df]
    return df[keep]


def read_any(p):
    p = Path(p)
    return pd.read_parquet(p) if p.suffix == '.parquet' else pd.read_csv(p)


def upsert(base, new, tol):
    """Trả về (merged, report). Mã có lệch giá ở ngày chồng lấn: nếu file mới chứa >=260 phiên của mã đó
    thì thay toàn bộ lịch sử (đã điều chỉnh lại); nếu không thì đưa vào danh sách quarantine."""
    rep = {'rows_new': 0, 'replaced_history': [], 'quarantine': [], 'revalidated': []}
    ov = base.merge(new[['ticker', 'date', 'close']], on=['ticker', 'date'], suffixes=('', '_n'))
    ov['diff'] = (ov.close_n / ov.close - 1).abs()
    bad = ov[ov['diff'] > tol].ticker.unique().tolist()
    cnt = new.groupby('ticker').size()
    for t in bad:
        if cnt.get(t, 0) >= 260:
            base = base[base.ticker != t]
            rep['replaced_history'].append(t)
        else:
            rep['quarantine'].append(t)
            new = new[new.ticker != t]
    # mã gửi đủ lịch sử (>=260 phiên) và khớp giá => coi như đã xác minh lại, gỡ khỏi quarantine
    rep['revalidated'] = [t for t, n in cnt.items() if n >= 260 and t not in bad]
    before = len(base)
    merged = pd.concat([base, new]).drop_duplicates(['ticker', 'date'], keep='last').sort_values(['ticker', 'date'])
    rep['rows_new'] = len(merged) - before
    return merged.reset_index(drop=True), rep


def ingest_inbox(cfg):
    P = cfg['paths']
    files = sorted([f for f in Path(P['inbox']).iterdir() if f.suffix in ('.csv', '.parquet')])
    panel = pd.read_parquet(P['panel'])
    vni = pd.read_parquet(P['vnindex'])
    reports = []
    for f in files:
        new = normalize(read_any(f))
        is_idx = new.ticker.isin(['VNINDEX', 'VN-INDEX'])
        if is_idx.any():
            v = new[is_idx].assign(ticker='VNINDEX')[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']]
            vni = pd.concat([vni, v]).drop_duplicates(['ticker', 'date'], keep='last').sort_values('date')
        if 'industry' in new:
            _update_industry(cfg, new[['ticker', 'industry']].dropna().drop_duplicates('ticker', keep='last'))
        panel, rep = upsert(panel, new[~is_idx].drop(columns=['industry'], errors='ignore'), cfg['qc']['adjust_tol'])
        rep['file'] = f.name
        reports.append(rep)
        shutil.move(str(f), Path(P['archive']) / f'{dt.datetime.now():%Y%m%d_%H%M%S}_{f.name}')
        log.info('ingest %s: %s', f.name, rep)
    if files:
        panel.to_parquet(P['panel'], index=False)
        vni.to_parquet(P['vnindex'], index=False)
    return reports


def _update_industry(cfg, df):
    p = Path(cfg['paths']['industry'])
    cur = pd.read_csv(p) if p.exists() else pd.DataFrame(columns=['ticker', 'industry'])
    pd.concat([cur, df]).drop_duplicates('ticker', keep='last').to_csv(p, index=False)


def fetch_vnstock(cfg):
    """THỬ NGHIỆM — chưa kiểm thử được trong môi trường build. Kéo dữ liệu gần đây cho các mã có thanh khoản,
    ghi vào inbox rồi đi qua cùng luồng upsert/QC như file thả tay."""
    from vnstock import Vnstock  # pip install vnstock
    P, V = cfg['paths'], cfg['vnstock']
    panel = pd.read_parquet(P['panel'])
    last = panel.date.max()
    recent = panel[panel.date > last - pd.Timedelta(days=40)]
    liq = recent.groupby('ticker').gt_khop.mean()
    tickers = sorted(liq[liq >= V['min_liq_vnd']].index.tolist()) + ['VNINDEX']
    start = (last - pd.Timedelta(days=V['lookback_days'])).strftime('%Y-%m-%d')
    end = dt.date.today().strftime('%Y-%m-%d')
    out, fails = [], []
    for t in tickers:
        try:
            q = Vnstock().stock(symbol=t, source=V['source']).quote.history(start=start, end=end, interval='1D')
            q['ticker'] = t
            out.append(q)
        except Exception as e:  # noqa
            fails.append(t)
    if out:
        df = normalize(pd.concat(out))
        df.to_parquet(Path(P['inbox']) / f'vnstock_{end}.parquet', index=False)
    # mã bị lệch giá (điều chỉnh quyền) cần kéo lại toàn bộ lịch sử
    tmp = pd.read_parquet(Path(P['inbox']) / f'vnstock_{end}.parquet') if out else pd.DataFrame()
    if len(tmp):
        ov = panel.merge(tmp[['ticker', 'date', 'close']], on=['ticker', 'date'], suffixes=('', '_n'))
        bad = ov[(ov.close_n / ov.close - 1).abs() > cfg['qc']['adjust_tol']].ticker.unique()
        full = []
        for t in bad:
            try:
                q = Vnstock().stock(symbol=t, source=V['source']).quote.history(start='2022-01-01', end=end, interval='1D')
                q['ticker'] = t; full.append(q)
            except Exception:
                fails.append(t)
        if full:
            normalize(pd.concat(full)).to_parquet(Path(P['inbox']) / f'vnstock_full_{end}.parquet', index=False)
    return {'tickers': len(tickers), 'fails': fails}


def qc(cfg, panel=None, today=None):
    P = cfg['paths']
    panel = pd.read_parquet(P['panel']) if panel is None else panel
    today = pd.Timestamp(today or dt.date.today())
    last = panel.date.max()
    r = panel.sort_values(['ticker', 'date']).groupby('ticker').close.pct_change()
    issues = {
        'last_date': str(last.date()),
        'stale_days': int((today - last).days),
        'dups': int(panel.duplicated(['ticker', 'date']).sum()),
        'nonpositive_price': int((panel[['open', 'high', 'low', 'close']] <= 0).any(axis=1).sum()),
        'high_lt_low': int((panel.high < panel.low).sum()),
        'jumps_gt_16pct_last60d': sorted(panel.loc[(r.abs() > 0.16) & (panel.date > last - pd.Timedelta(days=90)), 'ticker'].unique().tolist()),
        'n_tickers_last_day': int((panel.date == last).sum()),
    }
    issues['stale'] = issues['stale_days'] > cfg['qc']['max_stale_days']
    issues['blocking'] = issues['dups'] > 0 or issues['nonpositive_price'] > 0
    return issues
