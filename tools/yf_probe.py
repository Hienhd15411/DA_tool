"""Thử nghiệm nguồn Yahoo Finance (.VN) cho dữ liệu daily VNQ.

Không upload Supabase. Chỉ:
  1. kéo OHLCV từ 2026-07-01 đến hôm nay cho các mã có trong panel ngày 2026-07-10
  2. đối chiếu phần chồng lấn 2026-07-01..2026-07-10 với engine/data/seed/panel.parquet
     (panel đã điều chỉnh quyền, đơn vị nghìn đồng) → xem lệch giá có vượt qc.adjust_tol không
  3. ghi CSV ứng viên (đơn vị nghìn đồng) + báo cáo JSON vào tools/out/probe/
"""
from __future__ import annotations
import datetime as dt, json, sys, time
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / 'engine' / 'data' / 'seed' / 'panel.parquet'
OUT = ROOT / 'tools' / 'out' / 'probe'
OVERLAP_START, OVERLAP_END = '2026-07-01', '2026-07-10'
ADJUST_TOL = 0.005
SLEEP = 0.3


def fetch_yahoo(sym: str, start: str, end: str, auto_adjust: bool = True) -> pd.DataFrame | None:
    h = yf.Ticker(sym).history(start=start, end=end, auto_adjust=auto_adjust)
    if h is None or h.empty:
        return None
    h = h.reset_index()
    h['date'] = pd.to_datetime(h['Date']).dt.tz_localize(None).dt.normalize()
    h['events'] = (h.get('Dividends', 0).fillna(0) != 0) | (h.get('Stock Splits', 0).fillna(0) != 0)
    return h.rename(columns={'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})[
        ['date', 'open', 'high', 'low', 'close', 'volume', 'events']]


def to_candidate(ticker: str, h: pd.DataFrame) -> pd.DataFrame:
    # Yahoo: VND. Engine: nghìn đồng. Giữ quy ước panel.
    out = h.copy()
    for c in ['open', 'high', 'low', 'close']:
        out[c] = out[c] / 1000.0
    out['ticker'] = ticker
    out['gt_khop'] = out['close'] * out['volume'] * 1000  # xấp xỉ như engine/vnq/data.py
    return out[['ticker', 'date', 'open', 'high', 'low', 'close', 'volume', 'gt_khop', 'events']]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(PANEL)
    ov = panel[(panel.date >= OVERLAP_START) & (panel.date <= OVERLAP_END)]
    tickers = sorted(panel[panel.date == OVERLAP_END].ticker.unique())
    print(f'Mã có trong panel {OVERLAP_END}: {len(tickers)}')

    today = dt.date.today()
    end = (today + dt.timedelta(days=1)).isoformat()
    frames, diffs, raw_diffs, report, ev_info = [], [], [], {'ok': [], 'no_data': [], 'error': []}, {}
    for i, t in enumerate(tickers, 1):
        try:
            h = fetch_yahoo(f'{t}.VN', OVERLAP_START, end)
        except Exception as e:
            report['error'].append(f'{t}: {type(e).__name__}: {str(e)[:100]}')
            time.sleep(SLEEP)
            continue
        if h is None:
            report['no_data'].append(t)
            time.sleep(SLEEP)
            continue
        cand = to_candidate(t, h)
        try:
            raw = fetch_yahoo(f'{t}.VN', OVERLAP_START, end, auto_adjust=False)
            if raw is not None:
                rp = ov[ov.ticker == t][['date', 'close']].merge(raw[['date', 'close']], on='date', suffixes=('_p', '_r'))
                if len(rp):
                    raw_diffs.append(pd.DataFrame({'ticker': t, 'diff': (rp.close_r / rp.close_p - 1).abs().values}))
        except Exception:
            pass
        frames.append(cand.drop(columns=['events']))
        report['ok'].append(t)
        # đối chiếu chồng lấn
        pv = ov[ov.ticker == t][['date', 'close']].merge(cand[['date', 'close']], on='date', suffixes=('_p', '_y'))
        if len(pv):
            d = (pv.close_y / pv.close_p - 1).abs()
            diffs.append(pd.DataFrame({'ticker': t, 'date': pv.date, 'diff': d.values}))
        ev_after = int(cand.loc[cand.date > pd.Timestamp(OVERLAP_END), 'events'].sum())
        ev_overlap = int(cand.loc[cand.date <= pd.Timestamp(OVERLAP_END), 'events'].sum())
        ev_info[t] = (ev_after, ev_overlap)
        if i % 25 == 0:
            print(f'  {i}/{len(tickers)} ok={len(report["ok"])} no_data={len(report["no_data"])} err={len(report["error"])}')
        time.sleep(SLEEP)

    if frames:
        all_c = pd.concat(frames).sort_values(['ticker', 'date'])
        all_c.to_csv(OUT / 'candidate_inbox.csv', index=False, encoding='utf-8')
        print(f'Ghi candidate_inbox.csv: {len(all_c)} dòng, {all_c.ticker.nunique()} mã, '
              f'từ {all_c.date.min():%Y-%m-%d} đến {all_c.date.max():%Y-%m-%d}')

    summary = {'n_tickers': len(tickers), 'n_ok': len(report['ok']),
               'n_no_data': len(report['no_data']), 'n_error': len(report['error'])}
    if diffs:
        dd = pd.concat(diffs)
        per = dd.groupby('ticker')['diff'].agg(['mean', 'max', 'count'])
        over = per[per['max'] > ADJUST_TOL].index
        with_after = [t for t in over if ev_info.get(t, (0, 0))[0] > 0]
        summary.update({
            'tickers_over_tol_with_event_after_10_07': len(with_after),
            'tickers_over_tol_without_event_after_10_07': len(over) - len(with_after),
            'tickers_with_event_after_10_07_total': sum(1 for v in ev_info.values() if v[0] > 0),
            'overlap_rows': int(len(dd)),
            'overlap_mean_abs_diff_pct': round(float(dd['diff'].mean()) * 100, 4),
            'overlap_max_abs_diff_pct': round(float(dd['diff'].max()) * 100, 4),
            'tickers_over_tol': int((per['max'] > ADJUST_TOL).sum()),
            'tol_pct': ADJUST_TOL * 100,
        })
        worst = per.sort_values('max', ascending=False).head(10).round(5)
        summary['worst10'] = {k: {'max_pct': round(v['max'] * 100, 3), 'n': int(v['count'])}
                              for k, v in worst.iterrows()}
    if raw_diffs:
        rd = pd.concat(raw_diffs).groupby('ticker')['diff'].max()
        summary['raw_unadjusted_tickers_over_tol'] = int((rd > ADJUST_TOL).sum())
        summary['raw_unadjusted_tickers_match'] = int((rd <= ADJUST_TOL).sum())
    report['summary'] = summary
    (OUT / 'probe_report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('SUMMARY ' + json.dumps(summary, ensure_ascii=False))
    print('no_data sample: ' + ', '.join(report['no_data'][:30]))
    print('error sample: ' + ' | '.join(report['error'][:5]))


if __name__ == '__main__':
    sys.exit(main())
