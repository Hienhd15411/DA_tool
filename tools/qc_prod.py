"""QC production sau mỗi lần deploy: kiểm tra trang thật trên Netlify + Supabase như người dùng thấy.

Các bước (bước nào lỗi → exit 1, GitHub gửi mail báo workflow fail):
  1. Bản web trên Netlify khớp commit (so hash app.js/index.html/styles.css với repo; chờ deploy tối đa ~6 phút)
  2. config.js: có URL + anon key; key là role 'anon' (không lộ service key)
  3. Schema: mọi bảng/view mà web đọc (quét từ app.js) đều tồn tại → thiếu = migration chưa apply
  4. Bảo mật RLS: anon key KHÔNG đăng nhập không đọc được dữ liệu
  5. Dữ liệu: daily_runs mới nhất không quá cũ, có gate snapshot
  6. Trình duyệt thật: tạo user QC tạm (admin API) → đăng nhập qua form → trang render đủ các mục,
     không có lỗi JS / dòng "Lỗi tải dữ liệu" → xóa user QC
Cần env: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY. Tùy chọn: PROD_URL (mặc định https://hienhd.netlify.app)
"""
from __future__ import annotations
import base64, datetime as dt, hashlib, json, os, re, secrets, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
PROD = os.environ.get('PROD_URL', 'https://hienhd.netlify.app').rstrip('/')
SB = os.environ['SUPABASE_URL'].rstrip('/')
SK = os.environ['SUPABASE_SERVICE_ROLE_KEY']
SH = {'apikey': SK, 'Authorization': f'Bearer {SK}'}
fails, warns = [], []


def ok(msg): print(f'  ✅ {msg}', flush=True)
def fail(msg): print(f'  ❌ {msg}', flush=True); fails.append(msg)
def warn(msg): print(f'  ⚠️  {msg}', flush=True); warns.append(msg)
def step(n, msg): print(f'\n[{n}] {msg}', flush=True)
def h(b): return hashlib.sha256(b).hexdigest()[:12]


def jwt_role(tok):
    try:
        p = tok.split('.')[1]; p += '=' * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get('role')
    except Exception:
        return 'sb_publishable' if tok.startswith('sb_publishable_') else None


def check_deploy():
    step(1, f'Bản web trên {PROD} khớp repo')
    files = ['app.js', 'index.html', 'styles.css']
    want = {f: h((ROOT / 'web' / f).read_bytes()) for f in files}
    for i in range(36):
        got = {}
        for f in files:
            try:
                got[f] = h(requests.get(f'{PROD}/{f}', params={'qc': time.time()}, timeout=30).content)
            except requests.RequestException as e:
                got[f] = f'ERR {e.__class__.__name__}'
        if got == want:
            ok(f'khớp commit ({", ".join(f"{k}={v}" for k, v in want.items())})'); return
        time.sleep(10)
    fail(f'production chưa khớp repo sau 6 phút: prod={got} repo={want}')


def check_config():
    step(2, 'config.js')
    r = requests.get(f'{PROD}/config.js', params={'qc': time.time()}, timeout=30)
    m = re.search(r'window\.VNQ_CONFIG\s*=\s*(\{.*\})', r.text)
    if r.status_code != 200 or not m:
        fail(f'config.js không hợp lệ (HTTP {r.status_code})'); return None
    c = json.loads(m.group(1))
    if c.get('DEMO'): fail('production đang ở chế độ DEMO')
    if c.get('SUPABASE_URL', '').rstrip('/') != SB: fail('SUPABASE_URL trên web khác SUPABASE_URL của engine')
    key = c.get('SUPABASE_ANON_KEY', '')
    role = jwt_role(key)
    if not key: fail('thiếu SUPABASE_ANON_KEY')
    elif key == SK or role == 'service_role': fail('web đang dùng SERVICE ROLE KEY — đổi ngay sang anon key!')
    else: ok(f'URL đúng, key role={role}')
    return key


def tables_from_app():
    js = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
    req = set(re.findall(r"db\.q\('([a-z_]+)'", js)) - {'table'}
    opt = set(re.findall(r"db\.opt\('([a-z_]+)'", js))
    return sorted(req), sorted(opt - set(req))


def check_schema():
    step(3, 'Bảng/view web cần đều tồn tại')
    req, opt = tables_from_app()
    mig = sorted(p.name for p in (ROOT / 'supabase' / 'migrations').glob('*.sql'))
    for t in req + opt:
        r = requests.get(f'{SB}/rest/v1/{t}', headers=SH, params={'select': '*', 'limit': 1}, timeout=30)
        if r.status_code == 200: ok(f'{t}')
        else: fail(f'{t}: HTTP {r.status_code} {r.text[:120]} → kiểm tra migration đã apply chưa (mới nhất: {mig[-1]})')


def check_rls(anon):
    step(4, 'RLS: chưa đăng nhập thì không đọc được dữ liệu')
    if not anon: fail('không có anon key để kiểm tra'); return
    req, opt = tables_from_app()
    leaked = []
    for t in req + opt:
        r = requests.get(f'{SB}/rest/v1/{t}', headers={'apikey': anon, 'Authorization': f'Bearer {anon}'},
                         params={'select': '*', 'limit': 1}, timeout=30)
        # view tổng hợp luôn trả 1 dòng (đếm = 0, giá trị null) dù RLS chặn hết → chỉ tính là lộ khi có giá trị thật
        rows = r.json() if r.status_code == 200 else []
        if any(any(v not in (None, 0, '(tất cả)') for v in row.values()) for row in rows): leaked.append(t)
    if leaked: fail(f'anon đọc được dữ liệu: {leaked}')
    else: ok(f'{len(req + opt)} bảng/view đều chặn anon')


def check_data():
    step(5, 'Dữ liệu mới')
    r = requests.get(f'{SB}/rest/v1/daily_runs', headers=SH, params={'select': 'data_date,run_at', 'order': 'data_date.desc', 'limit': 1}, timeout=30)
    if r.status_code != 200 or not r.json(): fail('daily_runs trống'); return
    d = dt.date.fromisoformat(r.json()[0]['data_date'])
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=7))).date()
    bdays = sum(1 for i in range(1, (today - d).days + 1) if (d + dt.timedelta(days=i)).weekday() < 5)
    (fail if bdays > 3 else warn if bdays > 1 else ok)(f'ngày dữ liệu mới nhất {d} (trễ {bdays} ngày làm việc)')
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
    if d == now.date() and now.time() < dt.time(15, 30):
        fail(f'dữ liệu ngày {d} được publish lúc phiên chưa đóng ({now:%H:%M} ICT) — nến chưa chốt')
    pr = requests.get(f'{SB}/rest/v1/predictions_daily', headers=SH, params={'select': 'vol_ratio20', 'data_date': f'eq.{d}'}, timeout=30)
    vr = sorted(x['vol_ratio20'] for x in (pr.json() if pr.status_code == 200 else []) if x['vol_ratio20'] is not None)
    if vr:
        med = vr[len(vr) // 2]
        (fail if med < 0.5 else ok)(f'khối lượng trung vị ngày {d} = {med:.2f}× TB20 (< 0,5× → nghi nến chưa chốt)')
    g = requests.get(f'{SB}/rest/v1/gate_snapshots', headers=SH, params={'select': 'data_date', 'data_date': f'eq.{d}'}, timeout=30)
    (ok if g.status_code == 200 and g.json() else fail)(f'gate snapshot cho {d}')


def browser_smoke():
    step(6, 'Trình duyệt thật: đăng nhập + render')
    from playwright.sync_api import sync_playwright
    email = f'qc-bot-{secrets.token_hex(4)}@vnq-qc.invalid'; pw = secrets.token_urlsafe(18)
    r = requests.post(f'{SB}/auth/v1/admin/users', headers={**SH, 'Content-Type': 'application/json'}, timeout=30,
                      json={'email': email, 'password': pw, 'email_confirm': True, 'user_metadata': {'qc_bot': True}})
    if r.status_code >= 300: fail(f'không tạo được user QC: {r.status_code} {r.text[:150]}'); return
    uid = r.json()['id']
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(); pg = b.new_page(viewport={'width': 1280, 'height': 900})
            errs = []
            pg.on('pageerror', lambda e: errs.append(f'pageerror: {e}'))
            pg.on('console', lambda m: errs.append(f'console.{m.type}: {m.text}') if m.type == 'error' else None)
            pg.goto(f'{PROD}/?qc={int(time.time())}', wait_until='networkidle')
            pg.wait_for_selector('#loginForm', state='visible', timeout=20000)
            pg.fill('#email', email); pg.fill('#password', pw); pg.click('#loginForm button[type=submit]')
            pg.wait_for_selector('#content:not([hidden]), #err:not([hidden])', timeout=30000)
            pg.wait_for_timeout(4000)
            err = pg.locator('#err')
            if err.is_visible(): fail(f'trang báo lỗi: {err.inner_text()[:200]}')
            else: ok('đăng nhập OK, không có dòng lỗi')
            checks = {'status': '#status .tile', 'gate': '#gate .checks li', 'plan': '#plan .tile, #plan p.mut',
                      'live': '#live .tile, #live p.mut', 'top10': '#sigTable tr', 'tn06r': '#tn06rTable tr',
                      'uptrend': '#upTable tr', 'risk': 'footer .risk'}
            for k, sel in checks.items():
                n = pg.locator(sel).count()
                (ok if n else fail)(f'mục {k}: {n} phần tử')
            for sec in ('#plan', '#live'):
                t = pg.locator(sec).inner_text()
                if 'chưa được tạo' in t: fail(f'{sec}: {t[:150]}')
            pg.fill('#tickerIn', 'HPG'); pg.click('#lookupForm button'); pg.wait_for_timeout(2500)
            lk = pg.locator('#lookup').inner_text()
            (ok if 'HPG' in lk else fail)(f'tra cứu HPG: {lk[:80]!r}')
            real = [e for e in errs if 'favicon' not in e]
            (fail if real else ok)(f'lỗi JS/console: {real[:5] if real else 0}')
            Path('qc_out').mkdir(exist_ok=True); pg.screenshot(path='qc_out/prod.png', full_page=True)
            b.close()
    finally:
        d = requests.delete(f'{SB}/auth/v1/admin/users/{uid}', headers=SH, timeout=30)
        print(f'  (xóa user QC: HTTP {d.status_code})')


def scope():
    """Chỉ QC phần vừa deploy. QC_EVENT: push | data | all; QC_CHANGED: danh sách file đổi (push)."""
    ev = os.environ.get('QC_EVENT', 'all')
    if ev == 'data': return {'schema', 'data'}, 'job dữ liệu vừa chạy'
    if ev != 'push': return {'deploy', 'config', 'schema', 'rls', 'data', 'browser'}, 'chạy tay / toàn bộ'
    files = [f for f in os.environ.get('QC_CHANGED', '').split() if f]
    if not files or any(f.startswith(('tools/qc_prod.py', '.github/workflows/vnq-qc.yml')) for f in files):
        return {'deploy', 'config', 'schema', 'rls', 'data', 'browser'}, 'QC thay đổi hoặc không xác định được file đổi'
    st = set()
    if any(f.startswith(('web/', 'scripts/')) for f in files): st |= {'deploy', 'config', 'browser'}
    if 'web/app.js' in files: st.add('schema')
    if any(f.startswith('supabase/migrations/') for f in files): st |= {'schema', 'rls'}
    return st, 'file đổi: ' + ', '.join(files[:12]) + (' …' if len(files) > 12 else '')


if __name__ == '__main__':
    print(f'QC production {PROD} · {dt.datetime.now(dt.timezone.utc):%Y-%m-%d %H:%M} UTC')
    st, why = scope()
    print(f'Phạm vi: {sorted(st) or "không có gì cần QC"} ({why})')
    if 'deploy' in st: check_deploy()
    anon = check_config() if st & {'config', 'rls'} else None
    if 'schema' in st: check_schema()
    if 'rls' in st: check_rls(anon)
    if 'data' in st: check_data()
    if 'browser' in st: browser_smoke()
    print(f'\nKẾT QUẢ: {"FAIL" if fails else "PASS"} · {len(fails)} lỗi · {len(warns)} cảnh báo')
    for f in fails: print('  ❌', f)
    sys.exit(1 if fails else 0)
