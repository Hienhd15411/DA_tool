#!/usr/bin/env bash
# Kiểm tra bản web đang chạy trên Netlify khớp commit mới nhất (chờ tối đa ~3 phút cho deploy).
set -u
URL=${1:-https://hienhd.netlify.app}
for i in $(seq 1 18); do
  js=$(curl -fsS "$URL/app.js?nc=$RANDOM") || { echo "không tải được app.js"; sleep 10; continue; }
  if grep -q "db.opt(" <<<"$js"; then echo "OK: production có bản sửa (db.opt)"; break; fi
  echo "chưa thấy bản mới, thử lại ($i)"; sleep 10
done
echo "HTTP index: $(curl -s -o /dev/null -w '%{http_code}' "$URL/")"
curl -fsS "$URL/" | grep -o 'id="plan"\|id="live"\|id="tn06rTable"' | sort -u
curl -fsS "$URL/config.js" | sed -E 's/(eyJ[A-Za-z0-9_-]{6})[A-Za-z0-9._-]+/\1…/g' | head -5
