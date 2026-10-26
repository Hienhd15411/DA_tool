import yaml, os, hashlib, json
from pathlib import Path

ROOT = Path(os.environ.get('VNQ_ROOT', Path(__file__).resolve().parent.parent))


def load(path=None):
    p = Path(path) if path else ROOT / 'config.yaml'
    cfg = yaml.safe_load(open(p, encoding='utf-8'))
    # PyYAML đọc "5.0e9" thành chuỗi → ép kiểu số
    for sec, keys in (('universe', ('liq_min_vnd',)), ('vnstock', ('min_liq_vnd',)), ('costs', ('fee_per_side', 'sell_tax')),
                      ('qc', ('adjust_tol',))):
        for k in keys:
            cfg[sec][k] = float(cfg[sec][k])
    for k, v in cfg['paths'].items():
        cfg['paths'][k] = str((ROOT / v).resolve()) if not os.path.isabs(v) else v
    for k in ('inbox', 'archive', 'models', 'reports', 'state'):
        Path(cfg['paths'][k]).mkdir(parents=True, exist_ok=True)
    return cfg


def ledger_hash(cfg):
    """Hash các tham số ảnh hưởng tới model — đổi bất kỳ tham số nào => phải train version mới."""
    keys = {'ledger': cfg['ledger'], 'universe': {k: cfg['universe'][k] for k in ('ticker_regex', 'liq_min_vnd', 'min_bars')}}
    return hashlib.sha1(json.dumps(keys, sort_keys=True).encode()).hexdigest()[:10]


def pending_confirmations(cfg):
    out = []
    if not cfg['costs'].get('fee_confirmed'):
        out.append(f"Phí môi giới {cfg['costs']['fee_per_side']*100:.2f}%/chiều là GIẢ ĐỊNH")
    if not cfg['universe'].get('liq_confirmed'):
        out.append(f"Ngưỡng thanh khoản {cfg['universe']['liq_min_vnd']/1e9:.0f} tỷ VND/ngày chưa xác nhận")
    if not Path(cfg['paths']['exchange_map']).exists():
        out.append('Chưa có exchange_map.csv — sàn (biên độ trần/sàn) đang suy luận từ biến động giá, có thể sai')
    out.append('Không có dữ liệu cơ bản — value_mode = technical_proxy')
    return out
