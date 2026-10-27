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
  uptrend: (d) => db.q('scores_daily', (t) => t.select('ticker,industry,close,p_up_5,trend_score,atr14_pct,value_top30,near_ceiling,near_floor').eq('data_date', d).eq('regime', 'Uptrend').order('trend_score', { ascending: false }).limit(10),
    (r) => r.filter((x) => x.data_date === d && x.regime === 'Uptrend').sort((a, b) => b.trend_score - a.trend_score).slice(0, 10)),
  track: () => db.q('v_track_record', (t) => t.select('*'), (r) => r),
  trackDaily: () => db.q('v_track_daily', (t) => t.select('*').order('data_date'), (r) => r),
  tickerPreds: (tk) => db.q('predictions_daily', (t) => t.select('data_date,close,p_up_5,rank_all,value_top30,regime,trend_score,tn07_pick,tn06r_signal,status,net').eq('ticker', tk).order('data_date', { ascending: false }).limit(120),
    (r) => r.filter((x) => x.ticker === tk).sort((a, b) => b.data_date.localeCompare(a.data_date)).slice(0, 120)),
  tickerScores: (tk) => db.q('scores_daily', (t) => t.select('data_date,p_up_5,rank_all,value_score,value_top30,regime,trend_score,close').eq('ticker', tk).order('data_date', { ascending: false }).limit(60),
    (r) => r.filter((x) => x.ticker === tk).sort((a, b) => b.data_date.localeCompare(a.data_date)).slice(0, 60)),
  tickerSignals: (tk) => db.q('signals', (t) => t.select('data_date,rank_sel,action,status,net,excess').eq('ticker', tk).order('data_date', { ascending: false }),
    (r) => r.filter((x) => x.ticker === tk).sort((a, b) => b.data_date.localeCompare(a.data_date))),
  paperTrades: () => db.q('paper_trades', (t) => t.select('*').order('signal_date', { ascending: false }), (r) => [...r].sort((a, b) => b.signal_date.localeCompare(a.signal_date))),
  paperNav: () => db.q('paper_nav', (t) => t.select('*').order('date'), (r) => [...r].sort((a, b) => a.date.localeCompare(b.date))),
  liveEval: () => db.q('live_eval_daily', (t) => t.select('*').order('data_date'), (r) => [...r].sort((a, b) => a.data_date.localeCompare(b.data_date))),
  tn06r: (d) => db.q('predictions_daily', (t) => t.select('ticker,close,rsi14,vol_ratio20,status,net').eq('data_date', d).eq('tn06r_signal', true).order('rsi14'),
    (r) => r.filter((x) => x.data_date === d && x.tn06r_signal).sort((a, b) => a.rsi14 - b.rsi14)),
  tn06rRegime: (d) => db.q('predictions_daily', (t) => t.select('tn06r_regime_on').eq('data_date', d).limit(1), (r) => r.filter((x) => x.data_date === d).slice(0, 1)),
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

function renderUptrend(rows) {
  const head = '<tr><th>Mã</th><th>Ngành</th><th class="num">Đóng cửa</th><th class="num">p_up_5</th><th class="num">Trend</th><th class="num">ATR%</th><th>Cờ</th></tr>';
  const body = rows.map((r) => {
    const flags = [r.near_ceiling ? 'kịch trần' : '', r.near_floor ? 'kịch sàn' : '', r.value_top30 ? '' : 'ngoài value top 30%'].filter(Boolean).join(', ');
    return `<tr><td><b>${esc(r.ticker)}</b></td><td>${esc(r.industry || '')}</td><td class="num">${r.close ?? '—'}</td>
      <td class="num">${pct(r.p_up_5)}</td><td class="num">${f3(r.trend_score)}</td><td class="num">${pct(r.atr14_pct)}</td><td>${esc(flags || '—')}</td></tr>`;
  }).join('');
  $('upTable').innerHTML = `<thead>${head}</thead><tbody>${body || '<tr><td colspan="7" class="mut">Không có mã nào đang Uptrend trong ngày này.</td></tr>'}</tbody>`;
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

// ---------- dự báo vs thực tế (snapshot hằng ngày, quyết toán sau 5 phiên) ----------
const mean = (a) => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : null);
function liveChart(rows) {
  const W = 560, H = 190, P = { l: 52, r: 12, t: 10, b: 24 };
  let a = 0, b = 0;
  const pts = [{ a: 0, b: 0 }].concat(rows.map((r) => {
    if (r.tn07_net != null) a += r.tn07_net - r.market_net;
    if (r.tn06r_n > 0) b += r.tn06r_n * (r.tn06r_net - r.market_net) / 10;   // 10 slot: mỗi lệnh 10% vốn
    return { a, b, r };
  }));
  const mx = Math.max(0.01, ...pts.flatMap((p) => [Math.abs(p.a), Math.abs(p.b)]));
  const x = (i) => P.l + (pts.length === 1 ? 0 : i * (W - P.l - P.r) / (pts.length - 1));
  const y = (v) => P.t + (H - P.t - P.b) * (1 - (v + mx) / (2 * mx));
  const line = (k) => pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p[k]).toFixed(1)}`).join('');
  const liveIdx = rows.findIndex((r) => r.source === 'live');
  const mark = liveIdx >= 0 ? `<line x1="${x(liveIdx + 1)}" x2="${x(liveIdx + 1)}" y1="${P.t}" y2="${H - P.b}" stroke="var(--warnline)" stroke-dasharray="3 3"/>
    <text x="${x(liveIdx + 1) + 4}" y="${P.t + 10}">bắt đầu live</text>` : '';
  const hits = pts.slice(1).map((p, i) => `<rect x="${x(i + 1) - 4}" y="${P.t}" width="8" height="${H - P.t - P.b}" fill="transparent"
    data-tip="${fmtDate(p.r.data_date)} (${p.r.source}): TN07 top10 ${sgn(p.r.tn07_net)} · thị trường ${sgn(p.r.market_net)} · random ${sgn(p.r.pool_net)} · IC ${f3(p.r.ic)}${p.r.tn06r_n ? ` · TN06-R ${p.r.tn06r_n} lệnh ${sgn(p.r.tn06r_net)}` : ''}"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Lũy kế chênh lệch so với thị trường của TN07 và TN06-R theo ngày dự báo">
    <g class="axis">${[-mx, 0, mx].map((t) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(t)}" y2="${y(t)}" ${t === 0 ? '' : 'stroke-dasharray="2 3"'}/><text x="${P.l - 6}" y="${y(t) + 4}" text-anchor="end">${sgn(t, 1)}</text>`).join('')}</g>
    ${mark}<path d="${line('a')}" fill="none" stroke="var(--accent)" stroke-width="2"/>
    <path d="${line('b')}" fill="none" stroke="var(--good)" stroke-width="2"/>${hits}
    ${rows.length ? `<text x="${P.l}" y="${H - 6}">${fmtDate(rows[0].data_date)}</text><text x="${W - P.r}" y="${H - 6}" text-anchor="end">${fmtDate(rows.at(-1).data_date)}</text>` : ''}</svg>
    <p class="mut" style="font-size:12px;margin:4px 0 0"><span style="color:var(--accent)">━</span> TN07 top 10 trừ thị trường (lũy kế) &nbsp;
    <span style="color:var(--good)">━</span> TN06-R trừ thị trường, theo tỷ trọng 10%/lệnh (lũy kế) &nbsp;· trên 0 = thắng thị trường</p>`;
}

function renderLive(rows) {
  if (!rows.length) { $('live').innerHTML = '<p class="mut">Chưa có ngày dự báo nào đủ 5 phiên để so với thực tế.</p>'; return; }
  const t7 = rows.filter((r) => r.tn07_net != null), t6 = rows.filter((r) => r.tn06r_n > 0);
  const n6 = t6.reduce((s, r) => s + r.tn06r_n, 0);
  const w6 = (f) => (n6 ? t6.reduce((s, r) => s + r.tn06r_n * f(r), 0) / n6 : null);
  const ics = rows.map((r) => r.ic).filter((v) => v != null);
  const nLive = rows.filter((r) => r.source === 'live').length;
  const tile = (k, v, s) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div><div class="s">${s}</div></div>`;
  $('live').innerHTML = `<div class="band" style="margin-bottom:8px">
    ${tile('Ngày đã chấm', rows.length, `${nLive} live · ${rows.length - nLive} dựng lại`)}
    ${tile('IC TB (TN07)', f3(mean(ics)), `${pct(mean(ics.map((v) => (v > 0 ? 1 : 0))), 0)} số ngày IC > 0`)}
    ${tile('TN07 top 10 vs thị trường', sgn(mean(t7.map((r) => r.tn07_net - r.market_net))), `vs random ${sgn(mean(t7.map((r) => r.tn07_net - r.pool_net)))} / lệnh 5 phiên`)}
    ${tile('TN07 dự báo vs thực tế', `${pct(mean(t7.map((r) => r.pred_mean)), 0)} → ${pct(mean(t7.map((r) => r.tn07_hit)), 0)}`, 'p_up_5 TB top 10 → tỷ lệ đạt nhãn')}
    ${tile('TN06-R', n6 ? sgn(w6((r) => r.tn06r_net - r.market_net)) : '—', n6 ? `${n6} lệnh · lãi TB ${sgn(w6((r) => r.tn06r_net))} · vs thị trường` : 'chưa có lệnh nào được quyết toán')}
  </div>${liveChart(rows)}
  ${nLive < 20 ? `<p class="warn" style="margin:6px 0 0;padding:6px 8px;font-size:12px">Mới có ${nLive} ngày dự báo live đã quyết toán. Các ngày "dựng lại" dùng model/luật đã đóng băng chấm lại quá khứ — chỉ số live mới là bằng chứng sạch.</p>` : ''}
  <details><summary class="mut">Xem dạng bảng</summary><div class="wrap"><table class="tbl"><tr><th>Ngày dự báo</th><th>Nguồn</th><th class="num">IC</th><th class="num">TN07 top 10</th><th class="num">Random</th><th class="num">Thị trường</th><th class="num">Dự báo → hit</th><th class="num">TN06-R</th></tr>
    ${[...rows].reverse().map((r) => `<tr><td>${fmtDate(r.data_date)}</td><td>${r.source === 'live' ? 'live' : '<span class="mut">dựng lại</span>'}</td><td class="num">${f3(r.ic)}</td>
      <td class="num">${sgn(r.tn07_net)}</td><td class="num">${sgn(r.pool_net)}</td><td class="num">${sgn(r.market_net)}</td>
      <td class="num">${pct(r.pred_mean, 0)} → ${pct(r.tn07_hit, 0)}</td><td class="num">${r.tn06r_n ? `${r.tn06r_n} · ${sgn(r.tn06r_net)}` : '—'}</td></tr>`).join('')}</table></div></details>`;
  $('live').querySelectorAll('[data-tip]').forEach((el) => { el.addEventListener('mousemove', (e) => showTip(e, esc(el.dataset.tip))); el.addEventListener('mouseleave', hideTip); });
}

// ---------- kế hoạch phiên tới: danh mục mô phỏng theo luật TN06-R ----------
const SKIP = { skipped_full: 'đủ 10 lệnh', skipped_industry: 'ngành đã có 3 mã', skipped_holding: 'đang giữ mã này', skipped_ceiling: 'mở cửa sát trần', skipped_no_price: 'không có giá' };
let capital = 100;
try { capital = Number(localStorage.getItem('vnq_capital')) || 100; } catch (e) { /* storage bị chặn */ }
function navChart(nav) {
  if (nav.length < 2) return '';
  const W = 560, H = 170, P = { l: 46, r: 12, t: 10, b: 22 };
  const vals = nav.flatMap((r) => [r.nav, r.vnindex_rel]).filter((v) => v != null);
  const lo = Math.min(...vals), hi = Math.max(...vals), span = Math.max(0.02, hi - lo);
  const x = (i) => P.l + (W - P.l - P.r) * i / (nav.length - 1), y = (v) => P.t + (H - P.t - P.b) * (1 - (v - lo) / span);
  const line = (k) => nav.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r[k]).toFixed(1)}`).join('');
  const hits = nav.map((r, i) => `<rect x="${x(i) - 3}" y="${P.t}" width="6" height="${H - P.t - P.b}" fill="transparent" data-tip="${fmtDate(r.date)}: danh mục ${sgn(r.nav - 1)} · VNINDEX ${sgn(r.vnindex_rel - 1)} · ${r.n_open} lệnh mở · tiền mặt ${pct(r.cash_pct, 0)}"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Giá trị danh mục mô phỏng so với VNINDEX">
    <g class="axis">${[lo, 1, hi].map((t) => `<line x1="${P.l}" x2="${W - P.r}" y1="${y(t)}" y2="${y(t)}" ${t === 1 ? '' : 'stroke-dasharray="2 3"'}/><text x="${P.l - 6}" y="${y(t) + 4}" text-anchor="end">${sgn(t - 1, 0)}</text>`).join('')}</g>
    <path d="${line('vnindex_rel')}" fill="none" stroke="var(--muted)" stroke-dasharray="4 3" stroke-width="1.5"/>
    <path d="${line('nav')}" fill="none" stroke="var(--accent)" stroke-width="2"/>${hits}
    <text x="${P.l}" y="${H - 5}">${fmtDate(nav[0].date)}</text><text x="${W - P.r}" y="${H - 5}" text-anchor="end">${fmtDate(nav.at(-1).date)}</text></svg>
    <p class="mut" style="font-size:12px;margin:2px 0 0"><span style="color:var(--accent)">━</span> danh mục mô phỏng (sau phí) &nbsp; ┅ VNINDEX</p>`;
}

function renderPlan(trades, nav) {
  if (!trades.length && !nav.length) { $('plan').innerHTML = '<p class="mut">Chưa có dữ liệu danh mục mô phỏng.</p>'; return; }
  const asof = trades[0]?.data_date || nav.at(-1)?.date;
  const last = nav.at(-1) || { nav: 1, cash_pct: 1, n_open: 0, vnindex_rel: 1 };
  const buy = trades.filter((t) => t.status === 'planned');
  const skipNow = trades.filter((t) => t.signal_date === asof && t.status.startsWith('skipped'));
  const open = trades.filter((t) => t.status === 'open');
  const sell = open.filter((t) => t.sessions_left <= 1), hold = open.filter((t) => t.sessions_left > 1);
  const closed = trades.filter((t) => t.status === 'closed');
  const money = (w) => `${(capital * w).toFixed(1)} tr`;
  const lot = (w, price) => (price ? `≈ ${Math.max(0, Math.floor(capital * 1e6 * w / (price * 1000) / 100) * 100).toLocaleString('vi-VN')} cp` : '');
  const box = (title, sub, inner) => `<div class="planbox"><h3>${title}</h3><p class="mut">${sub}</p>${inner}</div>`;
  const list = (rows, cols) => (rows.length ? `<table class="tbl">${rows.map(cols).join('')}</table>` : '<p class="mut">Không có.</p>');
  const wins = closed.filter((t) => t.pnl > 0).length;
  $('planSub').textContent = `tính đến dữ liệu ${fmtDate(asof)} · lệnh cho phiên giao dịch kế tiếp`;
  $('plan').innerHTML = `
    <div class="band" style="margin-bottom:10px">
      <div class="tile"><div class="k">Danh mục mô phỏng</div><div class="v">${sgn(last.nav - 1)}</div><div class="s">VNINDEX ${sgn(last.vnindex_rel - 1)} cùng kỳ từ ${fmtDate(nav[0]?.date || asof)}</div></div>
      <div class="tile"><div class="k">Đang giữ</div><div class="v">${open.length}/10 lệnh</div><div class="s">tiền mặt ${pct(last.cash_pct, 0)}</div></div>
      <div class="tile"><div class="k">Lệnh đã đóng</div><div class="v">${closed.length}</div><div class="s">${closed.length ? `thắng ${pct(wins / closed.length, 0)} · TB ${sgn(mean(closed.map((t) => t.pnl)))}/lệnh` : '—'}</div></div>
      <div class="tile"><div class="k">Vốn để quy đổi</div><div class="v"><input id="capIn" type="number" min="1" step="10" value="${capital}" style="width:90px"> tr</div><div class="s">chỉ để tính số tiền / số cổ phiếu</div></div>
    </div>
    <div class="plangrid">
      ${box('① Vào lệnh phiên tới', 'Giá mở cửa · mỗi mã 10% NAV · bỏ nếu mở cửa sát trần',
        list(buy, (t) => `<tr><td><b>${esc(t.ticker)}</b><br><span class="mut">${esc(t.industry || '')}</span></td><td class="num">${money(0.1 * last.nav)}<br><span class="mut">${lot(0.1 * last.nav, t.signal_close)}</span></td><td class="num">RSI ${t.rsi14?.toFixed(0)}<br><span class="mut">tham chiếu ${t.signal_close?.toFixed(2) ?? '—'}</span></td></tr>`)
        + (skipNow.length ? `<p class="mut" style="font-size:12px">Tín hiệu bị bỏ: ${skipNow.map((t) => `${esc(t.ticker)} (${SKIP[t.status] || t.status})`).join(', ')}</p>` : ''))}
      ${box('② Thoát lệnh phiên tới', 'Bán 100% lệnh đó ở giá đóng cửa (ATC) · kẹt sàn thì bán phiên sau',
        list(sell, (t) => `<tr><td><b>${esc(t.ticker)}</b><br><span class="mut">vào ${fmtDate(t.entry_date)}</span></td><td class="num">bán 100%<br><span class="mut">giá vào ${t.entry_price?.toFixed(2)}</span></td><td class="num">${sgn(t.pnl)}<br><span class="mut">tạm tính</span></td></tr>`))}
      ${box('③ Đang giữ', 'Chưa đủ 5 phiên · không làm gì',
        list(hold, (t) => `<tr><td><b>${esc(t.ticker)}</b><br><span class="mut">vào ${fmtDate(t.entry_date)}</span></td><td class="num">còn ${t.sessions_left} phiên<br><span class="mut">đã giữ ${t.held_sessions}</span></td><td class="num">${sgn(t.pnl)}<br><span class="mut">tạm tính</span></td></tr>`))}
    </div>
    ${navChart(nav)}
    <details><summary class="mut">Lịch sử lệnh đã đóng (${closed.length})</summary><div class="wrap"><table class="tbl"><tr><th>Tín hiệu</th><th>Mã</th><th>Vào</th><th class="num">Giá vào</th><th>Ra</th><th class="num">Giá ra</th><th class="num">Lãi/lỗ sau phí</th><th>Nguồn</th></tr>
      ${closed.map((t) => `<tr><td>${fmtDate(t.signal_date)}</td><td><b>${esc(t.ticker)}</b></td><td>${fmtDate(t.entry_date)}</td><td class="num">${t.entry_price?.toFixed(2)}</td><td>${fmtDate(t.exit_date)}</td><td class="num">${t.exit_price?.toFixed(2)}</td><td class="num">${sgn(t.pnl)}</td><td>${t.source === 'live' ? 'live' : '<span class="mut">dựng lại</span>'}</td></tr>`).join('')}</table></div></details>`;
  $('plan').querySelectorAll('[data-tip]').forEach((el) => { el.addEventListener('mousemove', (e) => showTip(e, esc(el.dataset.tip))); el.addEventListener('mouseleave', hideTip); });
  $('capIn').addEventListener('change', (e) => { capital = Math.max(1, Number(e.target.value) || 100); try { localStorage.setItem('vnq_capital', capital); } catch (er) { /* bỏ qua */ } renderPlan(trades, nav); });
}

function renderTn06r(rows, reg) {
  const on = reg[0]?.tn06r_regime_on;
  const state = on == null ? '' : on ? 'Tầng 1 BẬT: VNINDEX dưới EMA50 (thị trường đang điều chỉnh).' : 'Tầng 1 TẮT: VNINDEX trên EMA50 → hệ không mở vị thế mới.';
  const head = '<tr><th>Mã</th><th class="num">Đóng cửa</th><th class="num">RSI14</th><th class="num">Vol / TB20</th><th>Vào (dự kiến)</th><th>Ra (dự kiến)</th><th class="num">Tỷ trọng</th><th>Kết quả 5p</th></tr>';
  const body = rows.map((r) => `<tr><td><b>${esc(r.ticker)}</b></td><td class="num">${r.close ?? '—'}</td><td class="num">${r.rsi14?.toFixed(1) ?? '—'}</td>
    <td class="num">${r.vol_ratio20?.toFixed(2) ?? '—'}×</td><td>giá mở cửa phiên sau</td><td>đóng cửa sau 5 phiên</td><td class="num">10%</td>
    <td>${r.status === 'settled' ? sgn(r.net) : r.status === 'unfilled_ceiling' ? 'không khớp (trần)' : '<span class="mut">đang mở</span>'}</td></tr>`).join('');
  $('tn06rState').textContent = state;
  $('tn06rTable').innerHTML = `<thead>${head}</thead><tbody>${body || `<tr><td colspan="8" class="mut">Không có tín hiệu TN06-R trong ngày này.</td></tr>`}</tbody>`;
}

function sparkline(rows) {
  const pts = [...rows].reverse(); if (pts.length < 2) return '';
  const W = 520, H = 90, P = { l: 36, r: 8, t: 8, b: 18 };
  const v = pts.map((r) => r.p_up_5), lo = Math.min(...v), hi = Math.max(...v), span = Math.max(0.02, hi - lo);
  const x = (i) => P.l + (W - P.l - P.r) * i / (pts.length - 1), y = (p) => P.t + (H - P.t - P.b) * (1 - (p - lo) / span);
  const d = pts.map((r, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(r.p_up_5).toFixed(1)}`).join('');
  const hits = pts.map((r, i) => `<rect x="${x(i) - 6}" y="${P.t}" width="12" height="${H - P.t - P.b}" fill="transparent" data-tip="${fmtDate(r.data_date)}: p_up_5 ${f3(r.p_up_5)} · hạng ${r.rank_all}${r.status === 'settled' ? ` · thực tế 5p ${sgn(r.net)}` : ''}"/>`).join('');
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Diễn biến p_up_5"><g class="axis">
    <line x1="${P.l}" x2="${W - P.r}" y1="${y(hi)}" y2="${y(hi)}" stroke-dasharray="2 3"/><text x="${P.l - 4}" y="${y(hi) + 4}" text-anchor="end">${hi.toFixed(2)}</text>
    <line x1="${P.l}" x2="${W - P.r}" y1="${y(lo)}" y2="${y(lo)}" stroke-dasharray="2 3"/><text x="${P.l - 4}" y="${y(lo) + 4}" text-anchor="end">${lo.toFixed(2)}</text></g>
    <path d="${d}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round"/>${hits}
    <text x="${P.l}" y="${H - 4}">${fmtDate(pts[0].data_date)}</text><text x="${W - P.r}" y="${H - 4}" text-anchor="end">${fmtDate(pts.at(-1).data_date)}</text></svg>`;
}

async function lookup(tk) {
  tk = tk.trim().toUpperCase(); if (!/^[A-Z0-9]{3}$/.test(tk)) return;
  // lịch sử điểm: snapshot dự báo hằng ngày (đủ mọi phiên); regime/trend/value chỉ có ở các ngày job đã publish scores_daily
  const [pr, sc, sg] = await Promise.all([db.tickerPreds(tk), db.tickerScores(tk), db.tickerSignals(tk)]);
  const extra = Object.fromEntries(sc.map((r) => [r.data_date, r]));
  const rows = pr.length ? pr.map((r) => ({ ...extra[r.data_date], ...Object.fromEntries(Object.entries(r).filter(([, v]) => v != null)) })) : sc;
  if (!rows.length) { $('lookup').innerHTML = `<p class="mut">${esc(tk)} không có trong universe đủ điều kiện ở các ngày đã chạy.</p>`; return; }
  const settled = rows.filter((r) => r.status === 'settled');
  const res = (r) => (r.status === 'settled' ? sgn(r.net) : r.status === 'unfilled_ceiling' ? 'trần' : r.status === 'open' ? '<span class="mut">chờ</span>' : '—');
  $('lookup').innerHTML = `<p><strong>${esc(tk)}</strong> — ${rows.length} phiên trong universe, ${sg.length} lần vào top 10${settled.length ? ` · thực tế 5 phiên TB sau phí: ${sgn(mean(settled.map((r) => r.net)))}` : ''}.</p>${sparkline(rows)}
    <div class="wrap"><table class="tbl"><tr><th>Ngày</th><th class="num">Giá</th><th class="num">p_up_5</th><th class="num">Hạng</th><th>Pool</th><th>Top 10</th><th>TN06-R</th><th class="num">Thực tế 5p</th><th>Regime</th><th class="num">trend</th></tr>
    ${rows.slice(0, 30).map((r) => `<tr><td>${fmtDate(r.data_date)}</td><td class="num">${r.close?.toFixed(2) ?? '—'}</td><td class="num">${f3(r.p_up_5)}</td><td class="num">${r.rank_all ?? '—'}</td>
      <td>${r.value_top30 ? '✓' : ''}</td><td>${r.tn07_pick ? '✓' : ''}</td><td>${r.tn06r_signal ? '✓' : ''}</td><td class="num">${res(r)}</td>
      <td>${esc(r.regime ?? '—')}</td><td class="num">${r.trend_score?.toFixed(2) ?? '—'}</td></tr>`).join('')}</table></div>
    ${rows.length > 30 ? `<p class="mut" style="font-size:12px">Bảng hiện 30 phiên gần nhất; biểu đồ hiện ${rows.length} phiên.</p>` : ''}`;
  $('lookup').querySelectorAll('[data-tip]').forEach((el) => { el.addEventListener('mousemove', (e) => showTip(e, esc(el.dataset.tip))); el.addEventListener('mouseleave', hideTip); });
}

async function loadDate(d) {
  const [run, gate, sig, up, t6, reg] = await Promise.all([db.run(d), db.gate(d), db.signals(d), db.uptrend(d), db.tn06r(d), db.tn06rRegime(d)]);
  renderStatus(run, gate); renderGate(gate); renderSignals(sig); renderUptrend(up); renderTn06r(t6, reg);
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
    const [rec, daily, live, ptr, pnav] = await Promise.all([db.track(), db.trackDaily(), db.liveEval(), db.paperTrades(), db.paperNav(), loadDate($('dateSel').value)]);
    renderTrack(rec, daily); renderLive(live); renderPlan(ptr, pnav);
    $('lookupForm').addEventListener('submit', (e) => { e.preventDefault(); lookup($('tickerIn').value); });
  } catch (e) {
    $('err').hidden = false; $('err').textContent = `Lỗi tải dữ liệu: ${e.message}`; console.error(e);
  }
}
main();
