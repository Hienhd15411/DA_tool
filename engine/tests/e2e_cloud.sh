#!/usr/bin/env bash
# Test e2e luồng cloud-run trên Supabase giả lập + Postgres local.
# Cần: Postgres đang chạy (DSN), migration đã apply. Mô phỏng: seed tới 30/06/2026, mỗi ngày 01–10/07 thả 1 file vào inbox.
set -euo pipefail
ENGINE="$(cd "$(dirname "$0")/.." && pwd)"
DSN="${DSN:?đặt DSN, ví dụ: host=/var/tmp/pgtest port=54329 user=postgres}"
WORK="${WORK:-$(mktemp -d)}"; PORT="${PORT:-54321}"
echo "WORK=$WORK"
rm -rf "$WORK"; mkdir -p "$WORK/store" "$WORK/feed"
cp -r "$ENGINE/vnq" "$ENGINE/config.yaml" "$ENGINE/models" "$WORK/"
mkdir -p "$WORK/data/seed"
python3 - "$ENGINE" "$WORK" <<'EOF'
import sys, pandas as pd
eng, w = sys.argv[1], sys.argv[2]
p = pd.read_parquet(f'{eng}/data/seed/panel.parquet'); v = pd.read_parquet(f'{eng}/data/seed/vnindex.parquet')
p[p.date < '2026-07-01'].to_parquet(f'{w}/data/seed/panel.parquet', index=False)
v[v.date < '2026-07-01'].to_parquet(f'{w}/data/seed/vnindex.parquet', index=False)
import shutil; shutil.copy(f'{eng}/data/seed/industry.csv', f'{w}/data/seed/industry.csv')
for d in sorted(p[p.date >= '2026-07-01'].date.unique()):
    pd.concat([p[p.date == d], v[v.date == d]]).to_csv(f'{w}/feed/{pd.Timestamp(d):%Y-%m-%d}.csv', index=False)
EOF
python3 "$ENGINE/tests/mock_supabase.py" --port "$PORT" --storage "$WORK/store" --dsn "$DSN" & MOCK=$!
trap 'kill $MOCK 2>/dev/null' EXIT; sleep 1
export SUPABASE_URL="http://127.0.0.1:$PORT" SUPABASE_SERVICE_ROLE_KEY=service-test-key VNQ_ROOT="$WORK"
cd "$WORK"
python3 -m vnq storage bootstrap 2>&1 | tail -1
for f in feed/*.csv; do
  mkdir -p store/vnq-data/inbox; cp "$f" store/vnq-data/inbox/           # = người dùng upload file lên Storage/inbox
  rm -rf data/panel.parquet data/vnindex.parquet state reports            # mỗi lần chạy là runner sạch như GitHub Actions
  python3 -m vnq cloud-run 2>&1 | grep -E "publish 20|Báo cáo|Error|Traceback" | sed 's/^.*INFO //' | cut -c1-200
done
echo "--- storage:"; find store -type f | sed "s#$WORK/##" | sort | head -40
