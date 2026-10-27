"""In bảng ứng viên theo phạm vi ngành từng agent (trader/agents.json) cho phiên kế tiếp. Chỉ đọc, dữ liệu ≤ ngày dữ liệu.

python tools/agent_candidates.py   (chạy trong thư mục gốc repo, sau `python -m vnq storage pull`)
"""
import datetime as dt, json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
import os
os.chdir(ROOT / 'engine')
from vnq import config, features  # noqa: E402

cfg = config.load(None)
panel = pd.read_parquet(cfg['paths']['panel'])
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
if now.time() < dt.time(15, 30):
    panel = panel[panel.date.dt.date < now.date()]
e = features.build(cfg, panel=panel)
d0 = e.date.max(); t = e[e.date == d0].copy()
agents = json.loads((ROOT / 'trader' / 'agents.json').read_text(encoding='utf-8'))['agents']
cols = ['ticker', 'industry', 'close', 'ret1', 'ret5', 'ret20', 'ret60', 'rsi14', 'regime', 'trend_score', 'dist_ema50', 'dist_ema200',
        'pos20', 'pos60', 'atr14_pct', 'vol_ratio20', 'liq20', 'near_ceiling', 'near_floor']
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 30); pd.set_option('display.max_rows', 200)
print(f'== CANDIDATES · dữ liệu {d0:%d/%m/%Y} · {len(t)} mã đủ điều kiện ==')
for g in agents:
    x = t[t.industry.isin(g['industries'])][cols].copy()
    for c in ['ret1', 'ret5', 'ret20', 'ret60', 'dist_ema50', 'dist_ema200', 'atr14_pct']: x[c] = (x[c] * 100).round(1)
    x['liq20'] = (x.liq20 / 1e9).round(1); x[['trend_score', 'pos20', 'pos60', 'vol_ratio20']] = x[['trend_score', 'pos20', 'pos60', 'vol_ratio20']].round(2)
    x['rsi14'] = x.rsi14.round(1)
    print(f'\n--- {g["id"]} {g["name"]} · {len(x)} mã · ngành: {", ".join(g["industries"])} ---')
    print('(ret/dist/atr tính %, liq20 tỷ đ/phiên)')
    print(x.sort_values('trend_score', ascending=False).to_string(index=False))
