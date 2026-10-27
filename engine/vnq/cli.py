"""VNQ — tool tín hiệu cổ phiếu VN hằng ngày.
  python -m vnq daily            # cập nhật dữ liệu → QC → feature → chấm điểm → gate → quyết toán → báo cáo
  python -m vnq update           # chỉ cập nhật dữ liệu (inbox / vnstock)
  python -m vnq train --version tn08 --note "..."   # train version mới (không bao giờ đè version cũ)
  python -m vnq status           # xem gate, dữ liệu, tín hiệu đang mở
  python -m vnq cloud-run        # (GitHub Actions) Storage pull → daily → publish Postgres → Storage push
  python -m vnq publish          # đẩy kết quả lần chạy gần nhất lên Supabase
  python -m vnq storage pull|push|bootstrap
"""
import argparse, logging, json, sys, datetime as dt
import pandas as pd
from pathlib import Path
from . import config, data, features, model, backtest, tracker, report, snapshot, paper

log = logging.getLogger('vnq')


def setup_log(cfg):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s',
                        handlers=[logging.FileHandler(Path(cfg['paths']['state']) / 'run.log', encoding='utf-8'), logging.StreamHandler()])


def cmd_update(cfg):
    if cfg['data_source'] == 'vnstock':
        log.info('vnstock fetch: %s', data.fetch_vnstock(cfg))
    reps = data.ingest_inbox(cfg)
    if not reps: log.info('inbox trống — không có dữ liệu mới')
    return reps


def cmd_daily(cfg, skip_update=False, asof=None, today=None):
    run_ts = dt.datetime.now().strftime('%Y-%m-%d %H:%M')
    reps = [] if skip_update else cmd_update(cfg)
    q = data.qc(cfg, today=today)
    log.info('QC: %s', q)
    if q['blocking']:
        raise SystemExit(f'QC chặn: {q}')
    quarantine = set(q['jumps_gt_16pct_last60d'])
    for r in reps: quarantine |= set(r['quarantine'])
    quarantine_jumps = set(q['jumps_gt_16pct_last60d'])
    qfile = Path(cfg['paths']['state']) / 'quarantine.json'
    old = set(json.load(open(qfile))) if qfile.exists() else set()
    cleared = {t for r in reps for t in r['replaced_history'] + r['revalidated']}
    quarantine = (quarantine | old) - cleared - {t for r in reps for t in r['replaced_history']}
    quarantine |= quarantine_jumps   # bước giá bất thường vẫn bị loại cho tới khi dữ liệu được sửa
    json.dump(sorted(quarantine), open(qfile, 'w'))

    panel = pd.read_parquet(cfg['paths']['panel'])
    if asof: panel = panel[panel.date <= asof]  # mô phỏng: không thấy dữ liệu sau asof
    e = features.build(cfg, panel=panel)
    fz = model.Frozen(cfg)
    sc = fz.score(e)
    full = sc if not asof else fz.score(features.build(cfg))   # gate/settle dùng toàn bộ dữ liệu đã có nhãn
    full = full if not asof else full[full.date <= pd.Timestamp(asof)]
    g = backtest.gate(cfg, full)
    trk = tracker.settle(cfg, full)

    d0 = sc.date.max(); dates = sorted(sc.date.unique())
    today_df = sc[sc.date == d0]; prev = sc[sc.date == dates[-2]] if len(dates) > 1 else None
    L = cfg['ledger']
    sel = backtest.pick(today_df, 'p_up_5', L['topk'], L['max_per_industry'], exclude=quarantine)
    md, tab = report.build(cfg, today_df, prev, sel, g, q, tracker.summary(trk), config.pending_confirmations(cfg),
                           quarantine, d0, run_ts)
    tracker.append(cfg, tab, d0, g['strategy_pass'])
    # ---- snapshot dự báo toàn universe (giữ nguyên dự báo đã ghi) → quyết toán → chấm live ----
    snap = snapshot.load(cfg)
    have = set(pd.to_datetime(snap.data_date)) if len(snap) else set()
    back = [d for d in sorted(full.date.unique()) if d >= pd.Timestamp(L['test_start']) and d < d0 and d not in have]
    if back:
        picks = {d: set(backtest.pick(full[full.date == d], 'p_up_5', L['topk'], L['max_per_industry']).get('ticker', []))
                 for d in back}
        snapshot.record(cfg, full, picks, 'backfill')
    now_ict = dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
    if d0.date() == now_ict.date() and now_ict.time() < dt.time(15, 30):
        log.warning('Phiên %s chưa đóng cửa (%s ICT) → không ghi snapshot live', d0.date(), now_ict.strftime('%H:%M'))
    else:
        snapshot.record(cfg, sc, {d0: set(sel.ticker) if len(sel) else set()}, 'live', quarantine)
    nfill = snapshot.fill_descriptive(cfg, full)
    if nfill: log.info('Snapshot: điền regime/trend/ngành cho %d dòng cũ', nfill)
    snap = snapshot.settle(cfg, full)
    live = snapshot.evaluate(cfg, snap)
    log.info('Live eval: %s', snapshot.summary(live))
    log.info('Danh mục mô phỏng TN06-R: %s', paper.run(cfg, snap, panel, full, L['test_start']))
    out = Path(cfg['paths']['reports']); stem = f'signals_{d0:%Y-%m-%d}'
    (out / f'{stem}.md').write_text(md, encoding='utf-8')
    (out / f'{stem}.html').write_text(report.to_html(md, f'Tín hiệu {d0:%d/%m/%Y}'), encoding='utf-8')
    tab.to_csv(out / f'{stem}.csv', index=False, encoding='utf-8-sig')
    (out / 'latest.html').write_text(report.to_html(md, f'Tín hiệu {d0:%d/%m/%Y}'), encoding='utf-8')
    # ---- output có cấu trúc cho publish (Supabase) ----
    sco = today_df.copy()
    sco['rank_all'] = sco.p_up_5.rank(ascending=False, method='min').astype(int)
    sco[['date', 'ticker', 'industry', 'close', 'p_up_5', 'p_lr', 'rank_all', 'value_score', 'value_mode', 'value_top30',
         'trend_score', 'regime', 'atr14_pct', 'liq20', 'near_ceiling', 'near_floor', 'exch', 'exch_src']] \
        .to_csv(out / f'scores_{d0:%Y-%m-%d}.csv', index=False, encoding='utf-8')
    warnings_ = ([f"Dữ liệu cũ {q['stale_days']} ngày (mới nhất {q['last_date']})"] if q['stale'] else []) + \
        ([f"Mã bị loại do nghi lệch điều chỉnh quyền: {', '.join(sorted(quarantine))}"] if quarantine else []) + \
        config.pending_confirmations(cfg)
    last = dict(data_date=f'{d0:%Y-%m-%d}', run_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                model_version=cfg['model_version'], n_eligible=int(len(today_df)), n_pool=int(today_df.value_top30.sum()),
                regime_universe=today_df.regime.value_counts().to_dict(),
                regime_pool=today_df[today_df.value_top30].regime.value_counts().to_dict(),
                qc=q, warnings=warnings_, quarantine=sorted(quarantine), ingest=reps, gate_pass=bool(g['strategy_pass']),
                report_md=f'{stem}.md', report_html=f'{stem}.html')
    json.dump(last, open(Path(cfg['paths']['state']) / 'last_run.json', 'w'), ensure_ascii=False, indent=1, default=str)
    log.info('Báo cáo: %s (gate %s)', out / f'{stem}.html', 'ĐẠT' if g['strategy_pass'] else 'CHƯA ĐẠT')
    return md


def cmd_status(cfg):
    q = data.qc(cfg)
    gp = Path(cfg['paths']['state']) / 'gate.json'
    g = json.load(open(gp, encoding='utf-8')) if gp.exists() else None
    print(json.dumps(q, ensure_ascii=False, indent=1))
    if g:
        print('Gate:', 'ĐẠT' if g['strategy_pass'] else 'CHƯA ĐẠT', g['updated'])
        for k, v in g['checks'].items(): print(('  ✅ ' if v else '  ❌ ') + k)
    s = tracker.summary(tracker.load(cfg)); print('Tracker:', s)
    print('Chưa xác nhận:', *config.pending_confirmations(cfg), sep='\n  - ')


def main(argv=None):
    ap = argparse.ArgumentParser(prog='vnq', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--config')
    sp = ap.add_subparsers(dest='cmd', required=True)
    d = sp.add_parser('daily'); d.add_argument('--skip-update', action='store_true'); d.add_argument('--asof'); d.add_argument('--today')
    sp.add_parser('update'); sp.add_parser('status')
    sp.add_parser('publish')
    cr = sp.add_parser('cloud-run'); cr.add_argument('--skip-update', action='store_true'); cr.add_argument('--no-publish', action='store_true')
    so = sp.add_parser('storage'); so.add_argument('action', choices=['pull', 'push', 'bootstrap'])
    so.add_argument('--seed-dir', default=str(config.ROOT / 'data' / 'seed'))
    t = sp.add_parser('train'); t.add_argument('--version', required=True); t.add_argument('--note', default='')
    a = ap.parse_args(argv)
    cfg = config.load(a.config); setup_log(cfg)
    if a.cmd == 'daily': cmd_daily(cfg, a.skip_update, a.asof, a.today)
    elif a.cmd == 'update': cmd_update(cfg)
    elif a.cmd == 'status': cmd_status(cfg)
    elif a.cmd == 'publish':
        from . import supa; supa.publish(cfg, supa.Supa())
    elif a.cmd == 'storage':
        from . import supa; sb = supa.Supa()
        if a.action == 'pull': supa.pull(cfg, sb)
        elif a.action == 'push': supa.push(cfg, sb)
        else: supa.bootstrap(cfg, sb, a.seed_dir)
    elif a.cmd == 'cloud-run':
        from . import supa; sb = supa.Supa()
        moved = supa.pull(cfg, sb)
        cmd_daily(cfg, a.skip_update)
        if not a.no_publish: supa.publish(cfg, sb)
        supa.push(cfg, sb, inbox_done=[] if a.skip_update else moved)
    elif a.cmd == 'train':
        man = model.train(cfg, features.build(cfg), a.version, a.note)
        log.info('Đã train %s: %s. Muốn dùng: sửa model_version trong config.yaml', a.version, man['best'])


if __name__ == '__main__':
    main()
