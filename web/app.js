// VNQ dashboard — chỉ ĐỌC dữ liệu do engine ghi vào Supabase. Không chứa service key.
// Cấu hình ở config.js (sinh lúc build trên Netlify từ env): window.VNQ_CONFIG = { SUPABASE_URL, SUPABASE_ANON_KEY, DEMO }
const CFG = window.VNQ_CONFIG || {};
const DEMO = CFG.DEMO || new URLSearchParams(location.search).has('demo') || !CFG.SUPABASE_URL;
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const pct = (x, d = 1) => (x == null || Number.isNaN(x) ? '—' : `${(x * 100).toFixed(d)}%`);
const sgn = (x, d = 2) => (x == null ? '—' : `${x >= 0 ? '+' : ''}${(x * 100).toFixed(d)}%`);
const f3 = (x) => (x == null ? '—' : Number(x).toFixed(3));
const ci = (c, s = 100, d = 2) => (!c || c[0] == null ? '—' : `[${(c[0] * s).toFixed(d)}; ${(c[1] * s).toFixed(d)}]`);
const fmtDate = (d) => { const [y, m, dd] = d.slice(0, 10).split('-'); return `${dd}/${m}/${y}`; };

// ---------------- data layer ----------------
let sb = null, demo = null;
const db = {
  async init() {
    if (DEMO) { demo = await (await fetch('demo-data.json')).json(); return { user: { email: 'demo' } }; }
    const { createClient } = await import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/+esm');
    sb = createClient(CFG.SUPABASE_URL, CFG.SUPABASE_ANON_KEY);
    const { data } = await sb.auth.getSession();
    return data.session;
  },
  async q(table, build, demoFn) {
    if (DEMO) return demoFn(demo[table] || []);
    const { data, error } = await build(sb.from(table));
    if (error) throw new Error(`${table}: ${error.message}`);
    return data;
  },
  runs: () => db.q('daily_runs', (t) => t.select('data_date').order('data_date', { ascending: false }).limit(250),
    (r) => [...r].sort((a, b) => b.data_date.localeCompare(a.data_date))),
  run: (d) => db.q('daily_runs', (t) => t.select('*').eq('data_date', d).single(), (r) => r.find((x) => x.data_date === d)),
  gate: (d) => db.q('gate_snapshots', (t) => t.select('*').eq('data_date', d).maybeSingle(), (r) => r.find((x) => x.data_date === d)),
  signals: (d) => db.q('signals', (t) => t.select('*').eq('data_date', d).order('rank_sel'),
    (r) => r.filter((x) => x.data_date === d && x.rank_sel != null).sort((a, b) => a.rank_sel - b.rank_sel)),
  track: () => db.q('v_track_record', (t) => t.select('*'), (r) => r),
  trackDaily: () => db.q('v_track_daily', (t) => t.select('*').order('data_date'), (r) => r),
  tickerScores: (tk) => db.q('scores_daily', (t) => t.select('data_date,p_up_5,rank_all,value_score,value_top30,regime,trend_score,close').eq('ticker', tk).order('data_date', { ascending: false }).limit(60),
    (r) => r.filter((x) => x.ticker === tk).sort((a, b) => b.data_date.localeCompare(a.data_date)).slice(0, 60)),
  tickerSignals: (tk) => db.q('signals', (t) => t.select('data_date,rank_sel,action,status,net,excess').eq('ticker', tk).order('data_date', { ascending: false }),
    (r) => r.filter((x) => x.ticker === tk).sort((a, b) => b.data_date.localeCompare(a.data_date))),
  async login(email, password) { return sb.auth.signInWithPassword({ email, password }); },
  async forgot(email) { return sb.auth.resetPasswordForEmail(email, { redirectTo: location.origin }); },
  async setPassword(password) { return sb.auth.updateUser({ password }); },
  async logout() { await sb.auth.signOut(); location.reload(); },
};

// ---------------- tooltip ----------------
const tip = $('tip');
function showTip(e, html) { tip.innerHTML = html; tip.hidden = false; const r = tip.getBoundingClientRect();
  let x = e.clientX + 12, y = e.clientY - r.height - 10; if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 12; if (y < 8) y = e.clientY + 14;
  tip.style.left = `${x}px`; tip.style.top = `${y}px`; }
const hideTip = () => { tip.hidden = true; };

// ---------------- render ----------------
function renderStatus(run, gate) {
  const stale = run.qc?.stale_days;
  const reg = (o) => Object.entries(o || {}).map(([k, v]) => `${k} ${v}`).join(' · ') || '—';
  $('status').innerHTML = [
    ['Ngày dữ liệu', fmtDate(run.data_date), `chạy ${new Date(run.run_at).toLocaleString('vi-VN')}`],
    ['Model', esc(run.model_version), stale != null ? `dữ liệu cũ ${stale} ngày khi chạy` : ''],
    ['Đủ điều kiện', run.n_eligible, reg(run.regime_universe)],
    ['Qua lọc value', run.n_pool, reg(run.regime_pool)],
    ['Gate mục 6', gate?.strategy_pass ? '<span class="badge ok">✓ ĐẠT</span>' : '<span class="badge no">✕ CHƯA ĐẠT</span>',
      gate?.strategy_pass ? 'được phép “cân nhắc mua”' : 'chỉ “theo dõi”'],
  ].map(([k, v, s]) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${esc(s)}</div></div>`).join('');
  const w = run.warnings || [];
  $('warnings').hidden = !w.length;
  $('warnings').innerHTML = `<strong>Cảnh báo / chưa xác nhận</strong><ul>${w.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>`;
  $('source').textContent = `Nguồn: Supabase daily_runs/signals · ${run.report_path || ''} · model ${run.model_version}`;
}

function renderGate(g) {
  if (!g) { $('gate').innerHTML = '<p class="mut">Chưa có snapshot gate.</p>'; return; }
  $('gateSub').textContent = `test từ ${fmtDate(g.test_start)}, ${g.n_test_days} ngày có nhãn`;
  const m = g.metrics?.lightgbm || {}, b = g.metrics?.logistic || {};
  const checks = Array.isArray(g.checks) ? g.checks.map((c) => [c.name, c.pass]) : Object.entries(g.checks);
  const failed = checks.filter(([, v]) => !v).length;
  $('gate').innerHTML = `<ul class="checks">${checks.map(([k, v]) =>
    `<li><span aria-label="${v ? 'đạt' : 'không đạt'}">${v ? '✅' : '❌'}</span>${esc(k)}</li>`).join('')}</ul>` +
    `<p class="mut" style="margin:6px 0">${failed ? `Gate chưa đạt: ${failed} mục ❌. Các mục ✅ không đủ để kết luận.` : 'Tất cả mục đều đạt.'}</p>` +
    (m.n_days ? `<dl class="kv">
      <dt>Hit top10</dt><dd>${pct(m.hit_top10)} · base pool ${pct(m.base_pool)} · lift ${m.lift != null ? (m.lift * 100).toFixed(1) : '—'} đđ</dd>
      <dt>Net top10 / 5 phiên</dt><dd>${pct(m.net_top10, 2)}</dd>
      <dt>Excess vs universe</dt><dd>${sgn(m.excess_ret_5)} · CI95 ${ci(m.excess_ci)}</dd>
      <dt>IC daily</dt><dd>${f3(m.ic_daily)} · CI95 ${ci(m.ic_ci, 1, 3)}</dd>
      <dt>Decile spread</dt><dd>${sgn(m.decile_spread)}</dd>
      <dt>Calibration</dt><dd>${m.calib_monotone ? 'đơn điệu' : 'không đơn điệu'}</dd>
      <dt>Baseline logistic</dt><dd>${b.n_days ? `hit ${pct(b.hit_top10)} · excess ${sgn(b.excess_ret_5)} · IC ${f3(b.ic_daily)}` : '—'}</dd></dl>` : '');
}

function renderSignals(rows) {
  const head = `<tr><th>#</th><th>Mã</th><th>Ngành</th><th class="num">p_up_5</th><th class="num">Hạng pool / univ.</th><th class="num">Δp</th>
    <th class="num">value</th><th class="num">trend</th><th>Regime</th><th class="num">ATR%</th><th>Nhận định</th><th>Kết quả 5p</th></tr>`;
  const body = rows.map((r) => {
    const res = r.status === 'settled' ? `${sgn(r.net)} <span class="mut">(excess ${sgn(r.excess)})</span>` : r.status === 'unfilled_ceiling' ? 'không khớp (trần)' : '<span class="mut">đang mở</span>';
    return `<tr class="main" data-t="${esc(r.ticker)}"><td>${r.rank_sel}</td><td><strong>${esc(r.ticker)}</strong></td><td>${esc(r.industry || '—')}</td>
      <td class="num">${f3(r.p_up_5)}</td><td class="num">${r.rank_pool ?? '—'} · ${r.rank_all ?? '—'}</td>
      <td class="num">${r.d_p == null ? '—' : (r.d_p >= 0 ? '+' : '') + r.d_p.toFixed(3)}</td><td class="num">${r.value_score?.toFixed(2) ?? '—'}</td>
      <td class="num">${r.trend_score == null ? '—' : (r.trend_score >= 0 ? '+' : '') + r.trend_score.toFixed(2)}</td>
      <td>${esc(r.regime)}${r.regime_prev && r.regime_prev !== r.regime ? ` <span class="mut">(từ ${esc(r.regime_prev)})</span>` : ''}</td>
      <td class="num">${pct(r.atr14_pct)}</td><td><span class="chip ${r.action === 'Cân nhắc mua' ? 'act' : ''}">${esc(r.action)}</span></td><td>${res}</td></tr>
      <tr class="detail" hidden><td colspan="12"><strong>Rủi ro:</strong> ${esc(r.risks)}${r.reasons ? `<br><strong>Lý do chỉ theo dõi:</strong> ${esc(r.reasons)}` : ''}</td></tr>`;
  }).join('');
  $('sigTable').innerHTML = `<thead>${head}</thead><tbody>${body || '<tr><td colspan="12" class="mut">Không có tín hiệu.</td></tr>'}</tbody>`;
  $('sigTable').querySelectorAll('tr.main').forEach((tr) => tr.addEventListener('click', () => { tr.nextElementSibling.hidden = !tr.nextElementSibling.hidden; }));
}

function trackChart(rows) {
  const days = [...rows].sort((a, b) => a.data_date.localeCompare(b.data_date));
  const W = 520, H = 180, P = { l: 52, r: 12, t: 10, b: 24 };
  let cn = 0, ce = 0;
  const pts = [{ n: 0, e: 0 }].concat(days.map((r) => {
    cn += r.avg_net; ce += r.avg_excess;
    return { n: cn, e: ce, r, dn: r.avg_net, de: r.avg_excess };
  }));
  const mx = Math.max(0.01, ...pts.flatMap((p) => [Math.abs(p.n), Math.abs(p.e)]));
  const x = (i) => P.l + (pts.length === 1 ? 0 : i * (W - P.l - P.r) / (pts.length - 1));
  const y = (v) => P.t + (H - P.t - P.b) * (1 - (v + mx) / (2 * mx));
  const line = (k) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p[k])}`).join('');
  const ticks = [-mx, 0, mx];
  const dots = pts.slice(1).map((p, i) => {
    const tip = `${fmtDate(p.r.data_date)}: lũy kế rổ ${sgn(p.n)} · lũy kế excess ${sgn(p.e)} · trong ngày net ${sgn(p.dn)} (n=${p.r.n}, hit ${pct(p.r.hit)})`;
    return `<circle cx="${x(i + 1)}" cy="${y(p.n)}" r="4" fill="var(--accent)" data-tip="${tip}"/>`;
  }).join('');
  const first = days[0]?.data_date, last = days.at(-1)?.data_date;
  const xlabels = first === last
    ? `<text x="${x(1)}" y="${H - 6}" text-anchor="middle">${first ? fmtDate(first) : ''}</text>`
    : `<text x="${P.l}" y="${H - 6}">${first ? fmtDate(first) : ''}</text><text x="${W - P.r}" y="${H - 6}" text-anchor="end">${last ? fmtDate(last) : ''}</text>`;
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Lũy kế lãi/lỗ rổ top 10 và excess so với universe, theo ngày tín hiệu">
    <g class="axis">${ticks.map((t) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(t)}" y2="${y(t)}" ${t === 0 ? '' : 'stroke-dasharray="2 3"'}/><text x="${P.l - 6}" y="${y(t) + 4}" text-anchor="end">${sgn(t, 1)}</text>`).join('')}</g>
    <path d="${line('e')}" fill="none" stroke="var(--muted)" stroke-dasharray="4 3" stroke-width="1.5"/>
    <path d="${line('n')}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    ${dots}
    ${xlabels}</svg>
    <p class="mut" style="font-size:12px;margin:4px 0 0">— rổ top 10 (lũy kế) &nbsp; ┅ excess so với universe (lũy kế) &nbsp; · trục X là ngày tín hiệu</p>`;
}

function renderTrack(rec, daily) {
  const all = rec.find((r) => r.action === '(tất cả)');
  if (!all || !all.n_settled) { $('track').innerHTML = '<p class="mut">Chưa có tín hiệu nào đủ 5 phiên để quyết toán. Kết quả sẽ hiện khi có dữ liệu sau ngày tín hiệu.</p>'; return; }
  const by = rec.filter((r) => r.action !== '(tất cả)');
  $('track').innerHTML = `<div class="band" style="margin-bottom:8px">
      <div class="tile"><div class="k">Đã quyết toán</div><div class="v">${all.n_settled}</div><div class="s">${all.n_days} ngày tín hiệu</div></div>
      <div class="tile"><div class="k">Hit rate</div><div class="v">${pct(all.hit_rate)}</div><div class="s">y_bin = 1</div></div>
      <div class="tile"><div class="k">Net TB / 5 phiên</div><div class="v">${sgn(all.avg_net)}</div><div class="s">excess ${sgn(all.avg_excess)}</div></div></div>
    ${trackChart(daily)}${daily.length < 20 ? `<p class="warn" style="margin:6px 0 0;padding:6px 8px;font-size:12px">Chỉ có ${daily.length} ngày tín hiệu đã quyết toán. Chưa đủ dữ liệu để kết luận.</p>` : ''}
    <details><summary class="mut">Xem dạng bảng</summary><table class="tbl"><tr><th>Ngày</th><th class="num">n</th><th class="num">Net</th><th class="num">Excess</th><th class="num">Hit</th></tr>
      ${daily.map((r) => `<tr><td>${fmtDate(r.data_date)}</td><td class="num">${r.n}</td><td class="num">${sgn(r.avg_net)}</td><td class="num">${sgn(r.avg_excess)}</td><td class="num">${pct(r.hit)}</td></tr>`).join('')}</table></details>
    ${by.length ? `<table class="tbl" style="margin-top:8px"><tr><th>Nhận định</th><th class="num">n</th><th class="num">Hit</th><th class="num">Net</th><th class="num">Excess</th></tr>
      ${by.map((r) => `<tr><td>${esc(r.action)}</td><td class="num">${r.n_settled}</td><td class="num">${pct(r.hit_rate)}</td><td class="num">${sgn(r.avg_net)}</td><td class="num">${sgn(r.avg_excess)}</td></tr>`).join('')}</table>` : ''}`;
  $('track').querySelectorAll('[data-tip]').forEach((el) => { el.addEventListener('mousemove', (e) => showTip(e, esc(el.dataset.tip))); el.addEventListener('mouseleave', hideTip); });
}

function sparkline(rows) {
  const pts = [...rows].reverse(); if (pts.length < 2) return '';
  const W = 520, H = 90, P = { l: 36, r: 8, t: 8, b: 18 };
  const v = pts.map((r) => r.p_up_5), lo = Math.min(...v), hi = Math.max(...v), span = Math.max(0.02, hi - lo);
  const x = (i) => P.l + (W - P.l - P.r) * i / (pts.length - 1), y = (p) => P.t + (H - P.t - P.b) * (1 - (p - lo) / span);
  const d = pts.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r.p_up_5).toFixed(1)}`).join('');
  const hits = pts.map((r, i) => `<rect x="${x(i) - 6}" y="${P.t}" width="12" height="${H - P.t - P.b}" fill="transparent" data-tip="${fmtDate(r.data_date)}: p_up_5 ${f3(r.p_up_5)} · hạng ${r.rank_all} · ${esc(r.regime)}"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Diễn biến p_up_5"><g class="axis">
    <line x1="${P.l}" x2="${W - P.r}" y1="${y(hi)}" y2="${y(hi)}" stroke-dasharray="2 3"/><text x="${P.l - 4}" y="${y(hi) + 4}" text-anchor="end">${hi.toFixed(2)}</text>
    <line x1="${P.l}" x2="${W - P.r}" y1="${y(lo)}" y2="${y(lo)}" stroke-dasharray="2 3"/><text x="${P.l - 4}" y="${y(lo) + 4}" text-anchor="end">${lo.toFixed(2)}</text></g>
    <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>${hits}
    <text x="${P.l}" y="${H - 4}">${fmtDate(pts[0].data_date)}</text><text x="${W - P.r}" y="${H - 4}" text-anchor="end">${fmtDate(pts.at(-1).data_date)}</text></svg>`;
}

async function lookup(tk) {
  tk = tk.trim().toUpperCase(); if (!/^[A-Z0-9]{3}$/.test(tk)) return;
  const [sc, sg] = await Promise.all([db.tickerScores(tk), db.tickerSignals(tk)]);
  if (!sc.length) { $('lookup').innerHTML = `<p class="mut">${esc(tk)} không có trong universe đủ điều kiện ở các ngày đã chạy.</p>`; return; }
  $('lookup').innerHTML = `<p><strong>${esc(tk)}</strong> — ${sc.length} ngày trong universe, ${sg.length} lần vào top 10.</p>${sparkline(sc)}
    <div class="wrap"><table class="tbl"><tr><th>Ngày</th><th class="num">Giá</th><th class="num">p_up_5</th><th class="num">Hạng</th><th class="num">value</th><th>Pool</th><th>Regime</th><th class="num">trend</th></tr>
    ${sc.slice(0, 20).map((r) => `<tr><td>${fmtDate(r.data_date)}</td><td class="num">${r.close?.toFixed(2) ?? '—'}</td><td class="num">${f3(r.p_up_5)}</td><td class="num">${r.rank_all}</td>
      <td class="num">${r.value_score?.toFixed(2)}</td><td>${r.value_top30 ? '✓' : ''}</td><td>${esc(r.regime)}</td><td class="num">${r.trend_score?.toFixed(2)}</td></tr>`).join('')}</table></div>`;
  $('lookup').querySelectorAll('[data-tip]').forEach((el) => { el.addEventListener('mousemove', (e) => showTip(e, esc(el.dataset.tip))); el.addEventListener('mouseleave', hideTip); });
}

async function loadDate(d) {
  const [run, gate, sig] = await Promise.all([db.run(d), db.gate(d), db.signals(d)]);
  renderStatus(run, gate); renderGate(gate); renderSignals(sig);
  history.replaceState(null, '', `?${DEMO && new URLSearchParams(location.search).has('demo') ? 'demo&' : ''}d=${d}`);
}

function loginError(msg) {
  const m = (msg || '').toLowerCase();
  if (m.includes('invalid login')) return 'Email hoặc mật khẩu không đúng.';
  if (m.includes('email not confirmed')) return 'Email chưa được xác nhận.';
  if (m.includes('rate limit')) return 'Thử quá nhiều lần. Đợi vài phút rồi thử lại.';
  return msg;
}

function showLogin() {
  $('login').hidden = false;
  $('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const { error } = await db.login($('email').value.trim(), $('password').value);
    if (error) { $('loginMsg').textContent = loginError(error.message); return; }
    location.reload();
  });
  $('forgot').addEventListener('click', async () => {
    const email = $('email').value.trim();
    if (!email) { $('loginMsg').textContent = 'Nhập email trước, rồi bấm Quên mật khẩu.'; return; }
    const { error } = await db.forgot(email);
    $('loginMsg').textContent = error ? loginError(error.message) : 'Đã gửi link đặt lại mật khẩu. Kiểm tra email (kể cả thư rác).';
  });
}

function showSetPassword() {
  $('login').hidden = true;
  $('setpw').hidden = false;
  $('setpwForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    if ($('pw1').value !== $('pw2').value) { $('setpwMsg').textContent = 'Hai mật khẩu không khớp.'; return; }
    const { error } = await db.setPassword($('pw1').value);
    if (error) { $('setpwMsg').textContent = error.message; return; }
    history.replaceState(null, '', location.pathname + location.search);
    location.reload();
  });
}

async function main() {
  try {
    const recoveryFlow = !DEMO && /type=(recovery|invite)/.test(location.hash);
    const session = await db.init();
    if (recoveryFlow && session) { showSetPassword(); return; }
    if (!session) { showLogin(); return; }
    $('user').textContent = DEMO ? 'Chế độ demo (dữ liệu mẫu 01–10/07/2026)' : session.user.email;
    if (!DEMO) { $('logout').hidden = false; $('logout').onclick = () => db.logout(); }
    const runs = await db.runs();
    if (!runs.length) { $('err').hidden = false; $('err').textContent = 'Chưa có lần chạy nào trong database.'; return; }
    $('content').hidden = false;
    const want = new URLSearchParams(location.search).get('d');
    $('dateSel').innerHTML = runs.map((r) => `<option value="${r.data_date}">${fmtDate(r.data_date)}</option>`).join('');
    $('dateSel').value = runs.some((r) => r.data_date === want) ? want : runs[0].data_date;
    $('dateSel').onchange = (e) => loadDate(e.target.value);
    const [rec, daily] = await Promise.all([db.track(), db.trackDaily(), loadDate($('dateSel').value)]);
    renderTrack(rec, daily);
    $('lookupForm').addEventListener('submit', (e) => { e.preventDefault(); lookup($('tickerIn').value); });
  } catch (e) {
    $('err').hidden = false; $('err').textContent = `Lỗi tải dữ liệu: ${e.message}`; console.error(e);
  }
}
main();
