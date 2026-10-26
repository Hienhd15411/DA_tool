"""Báo cáo hằng ngày theo mục 5 + 8 của context dự án: Markdown + HTML + CSV."""
import pandas as pd, numpy as np, html, json
from pathlib import Path

RISK_LINE = ('⚠️ Đây là tín hiệu thống kê, không phải khuyến nghị đảm bảo lợi nhuận. '
             'Đây là tín hiệu để theo dõi và cân nhắc, không phải lệnh. Quyết định và rủi ro thuộc về người dùng.')


def pct(x, d=1): return '—' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{x*100:.{d}f}%'


def f3(x): return '—' if x is None or (isinstance(x, float) and np.isnan(x)) else f'{x:.3f}'


def ci(c, scale=100, d=2):
    return '—' if not c or c[0] is None else f'[{c[0]*scale:.{d}f}; {c[1]*scale:.{d}f}]'


def stock_risks(r, today, cfg, quarantine):
    risks, block = [], []
    def add(msg, blocking=False):
        risks.append(msg)
        if blocking: block.append(msg)
    if r.near_ceiling: add('đang kịch trần — có thể không khớp lệnh mua', True)
    if r.near_floor: add('đang kịch sàn', True)
    if r.liq20 < 1.5*cfg['universe']['liq_min_vnd']: risks.append(f'thanh khoản sát ngưỡng ({r.liq20/1e9:.1f} tỷ/ngày)')
    if r.regime == 'Downtrend': add('trend và ML mâu thuẫn (regime Downtrend)', True)
    if r.atr14_pct > today.atr14_pct.quantile(0.9): risks.append(f'biến động cao (ATR% {r.atr14_pct*100:.1f}%)')
    if r.ticker in quarantine: add('dữ liệu nghi chưa điều chỉnh quyền', True)
    if r.exch_src == 'inferred': risks.append(f'sàn {r.exch} là suy luận')
    risks.append('thiếu dữ liệu cơ bản (technical_proxy)')
    return risks, block


def build(cfg, today, prev, sel, gate, qc, track, pending, quarantine, data_date, run_ts):
    L = cfg['ledger']
    m = gate['metrics']['lightgbm']; n_test = m.get('n_days', 0)
    rows = []
    pv = prev.set_index('ticker') if prev is not None else None
    today = today.copy(); today['rank_all'] = today.p_up_5.rank(ascending=False, method='min').astype(int)
    pool = today[today.value_top30].copy(); pool['rank_pool'] = pool.p_up_5.rank(ascending=False, method='min').astype(int)
    for _, r in sel.iterrows():
        risks, block = stock_risks(r, today, cfg, quarantine)
        action = 'Cân nhắc mua' if gate['strategy_pass'] and not block else 'Theo dõi'
        reasons = [] if action == 'Cân nhắc mua' else (['chiến lược chưa qua gate mục 6'] if not gate['strategy_pass'] else []) + block
        dp = r.p_up_5 - pv.p_up_5.get(r.ticker, np.nan) if pv is not None else np.nan
        dr = None
        if pv is not None and r.ticker in pv.index: dr = pv.regime.get(r.ticker)
        reasons = '; '.join(reasons)
        rows.append(dict(ticker=r.ticker, industry=r.industry if isinstance(r.industry, str) else '—', p_up_5=r.p_up_5,
                         rank_all=int(today.loc[today.ticker == r.ticker, 'rank_all'].iloc[0]),
                         rank_pool=int(pool.loc[pool.ticker == r.ticker, 'rank_pool'].iloc[0]),
                         d_p=dp, value_score=r.value_score, value_mode=r.value_mode, trend_score=r.trend_score,
                         regime=r.regime, regime_prev=dr, atr14_pct=r.atr14_pct, liq20=r.liq20, close=r.close,
                         action=action, risks='; '.join(risks), reasons=reasons))
    tab = pd.DataFrame(rows)
    n_el, n_pool = len(today), int(today.value_top30.sum())
    reg_u = today.regime.value_counts().to_dict(); reg_p = pool.regime.value_counts().to_dict()

    md = []
    md.append(f'# Báo cáo tín hiệu ngày {data_date:%d/%m/%Y}')
    md.append(f'Ngày dữ liệu **{data_date:%Y-%m-%d}** · chạy lúc {run_ts} · model `{cfg["model_version"]}` · '
              f'đủ điều kiện **{n_el}** mã · qua lọc value **{n_pool}** mã · '
              f'regime universe: {", ".join(f"{k} {v}" for k, v in reg_u.items())} · regime pool: {", ".join(f"{k} {v}" for k, v in reg_p.items())}')
    warn = []
    if qc['stale']: warn.append(f"Dữ liệu cũ {qc['stale_days']} ngày (mới nhất {qc['last_date']}) — tín hiệu không còn tính thời sự")
    if quarantine: warn.append(f"Mã bị loại do nghi lệch điều chỉnh quyền: {', '.join(sorted(quarantine))}")
    warn += pending
    md.append('\n**Cảnh báo / chưa xác nhận**\n' + '\n'.join(f'- {w}' for w in warn))
    md.append('\n## 1. Gate mục 6 (tập test từ ' + L['test_start'] + f', {n_test} ngày có nhãn)')
    md.append('| Điều kiện | Kết quả |\n|---|---|')
    md += [f'| {k} | {"✅" if v else "❌"} |' for k, v in gate['checks'].items()]
    md.append(f'\n**Trạng thái: {"ĐẠT — được phép nhận định “cân nhắc mua”" if gate["strategy_pass"] else "CHƯA ĐẠT — chỉ được “theo dõi”"}**')
    if n_test:
        md.append(f"\nLightGBM trên test: hit top10 {pct(m['hit_top10'])} (base pool {pct(m['base_pool'])}, lift {m['lift']*100:+.1f} đđ) · "
                  f"net top10 {pct(m['net_top10'],2)}/5 phiên · excess vs universe {pct(m['excess_ret_5'],2)} CI95 {ci(m['excess_ci'])} · "
                  f"IC {f3(m['ic_daily'])} CI95 {ci(m['ic_ci'],1,3)} · decile spread {pct(m['decile_spread'],2)} · calibration {'đơn điệu' if m['calib_monotone'] else 'không đơn điệu'}")
        b = gate['metrics']['logistic']
        if b.get('n_days'):
            md.append(f"Baseline logistic: hit {pct(b['hit_top10'])}, excess {pct(b['excess_ret_5'],2)}, IC {f3(b['ic_daily'])}")
    md.append(f'\n## 2. Top {L["topk"]} (lọc thanh khoản → value top {int(L["value_top_pct"]*100)}% → xếp hạng p_up_5, ≤{L["max_per_industry"]} mã/ngành)')
    md.append('| # | Mã | Ngành | p_up_5 | Hạng pool / universe | Δp vs hôm qua | value_score | trend_score | Regime | ATR% | Nhận định |')
    md.append('|---|---|---|---|---|---|---|---|---|---|---|')
    for i, r in tab.iterrows():
        md.append(f"| {i+1} | **{r.ticker}** | {r.industry} | {r.p_up_5:.3f} | {r.rank_pool}/{n_pool} · {r.rank_all}/{n_el} | "
                  f"{'—' if pd.isna(r.d_p) else f'{r.d_p:+.3f}'} | {r.value_score:.2f} | {r.trend_score:+.2f} | {r.regime}"
                  f"{'' if not r.regime_prev or r.regime_prev == r.regime else f' (từ {r.regime_prev})'} | {r.atr14_pct*100:.1f}% | {r.action} |")
    md.append('\n## 3. Rủi ro & kết luận từng mã')
    ev = (f"excess {pct(m['excess_ret_5'],2)}/5 phiên sau chi phí, IC {f3(m['ic_daily'])} ({n_test} ngày)" if n_test else 'chưa có ngày test nào đủ nhãn')
    for _, r in tab.iterrows():
        md.append(f"- **{r.ticker}** — {r.action}. Theo mô hình, {r.ticker} có p_up_5 = {r.p_up_5:.2f} (top {r.rank_pool}/{n_pool} pool, "
                  f"{r.rank_all}/{n_el} universe), trend đang {r.regime}. Trên tập test, chiến lược có {ev}. "
                  f"Rủi ro chính: {r.risks}." + (f" Lý do chỉ theo dõi: {r.reasons}." if r.reasons else ''))
    md.append('\n## 4. Theo dõi thực tế (paper trading từ signals_log)')
    if track:
        md.append(f"Đã quyết toán {track['n']} tín hiệu / {track['days']} ngày: hit {pct(track['hit'])}, net TB {pct(track['net'],2)}/5 phiên, "
                  f"excess vs universe {pct(track['excess'],2)}. Đang mở: {track['open']}.")
        for a in track['by_action']:
            md.append(f"- {a['action']}: n={a['n']}, hit {pct(a['hit'])}, net {pct(a['net'],2)}, excess {pct(a['excess'],2)}")
    else:
        md.append('Chưa có tín hiệu nào đủ 5 phiên để quyết toán.')
    md.append(f"\n## 5. Nguồn\nDữ liệu: `{Path(cfg['paths']['panel']).name}` (đến {qc['last_date']}), `{Path(cfg['paths']['vnindex']).name}` · "
              f"model `{cfg['model_version']}` · gate `state/gate.json` ({gate['updated']}) · chi phí {cfg['costs']['fee_per_side']*100:.2f}%/chiều + thuế bán {cfg['costs']['sell_tax']*100:.1f}%")
    md.append('\n' + RISK_LINE)
    return '\n'.join(md), tab


CSS = """:root{--bg:#fbfbfa;--fg:#1d1d1f;--mut:#6b6b70;--line:#e3e3e0;--card:#fff;--ok:#1f7a4d;--bad:#b42318;--acc:#2f5bd3}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#ececec;--mut:#9a9aa0;--line:#2c2c30;--card:#1c1c1f;--ok:#4cc38a;--bad:#ff6b5e;--acc:#7c9cff}}
body{background:var(--bg);color:var(--fg);font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px 16px}
main{max-width:1100px;margin:auto}h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px;border-bottom:1px solid var(--line);padding-bottom:4px}
p,li{color:var(--fg)}.mut{color:var(--mut)}table{border-collapse:collapse;width:100%;background:var(--card);font-variant-numeric:tabular-nums}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}th{color:var(--mut);font-weight:600;font-size:12px}
.wrap{overflow-x:auto}code{font-size:12px}strong{font-weight:650}.warn{border-left:3px solid var(--bad);padding:6px 12px;background:var(--card)}"""


def to_html(md_text, title):
    out, in_table, in_list = [], False, False
    import re
    def inline(s):
        s = html.escape(s)
        s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
        return re.sub(r'`(.+?)`', r'<code>\1</code>', s)
    for line in md_text.split('\n'):
        if line.startswith('|'):
            cells = [c.strip() for c in line.strip('|').split('|')]
            if set(''.join(cells)) <= set('-'): continue
            if not in_table:
                out.append('<div class="wrap"><table><tr>' + ''.join(f'<th>{inline(c)}</th>' for c in cells) + '</tr>'); in_table = True
            else:
                out.append('<tr>' + ''.join(f'<td>{inline(c)}</td>' for c in cells) + '</tr>')
            continue
        if in_table: out.append('</table></div>'); in_table = False
        if line.startswith('- '):
            if not in_list: out.append('<ul>'); in_list = True
            out.append(f'<li>{inline(line[2:])}</li>'); continue
        if in_list: out.append('</ul>'); in_list = False
        if line.startswith('# '): out.append(f'<h1>{inline(line[2:])}</h1>')
        elif line.startswith('## '): out.append(f'<h2>{inline(line[3:])}</h2>')
        elif line.strip(): out.append(f'<p>{inline(line)}</p>')
    if in_table: out.append('</table></div>')
    if in_list: out.append('</ul>')
    return f'<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>{"".join(out)}</main></body></html>'
