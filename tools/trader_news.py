"""Lấy tin chứng khoán (RSS CafeF / VnExpress) cho agent trader. Chỉ đọc tiêu đề + tóm tắt + link, in ra log.

Thử nhiều địa chỉ RSS; báo rõ nguồn nào lấy được. Lọc tin trong ~36 giờ gần nhất.
"""
import datetime as dt, html, re, sys
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

FEEDS = {
    'VnExpress · Chứng khoán': ['https://vnexpress.net/rss/kinh-doanh/chung-khoan.rss', 'https://vnexpress.net/rss/kinh-doanh.rss'],
    'CafeF · Thị trường CK': ['https://cafef.vn/thi-truong-chung-khoan.rss', 'https://cafef.vn/rss/thi-truong-chung-khoan.rss',
                             'https://cafef.vn/home.rss'],
    'CafeF · Doanh nghiệp': ['https://cafef.vn/doanh-nghiep.rss'],
    'CafeF · Vĩ mô': ['https://cafef.vn/vi-mo-dau-tu.rss', 'https://cafef.vn/kinh-te-vi-mo-dau-tu.rss'],
}
UA = {'User-Agent': 'Mozilla/5.0 (VNQ research; RSS reader)'}
now = dt.datetime.now(dt.timezone(dt.timedelta(hours=7)))
clean = lambda s: re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html.unescape(s or ''))).strip()
ok_any = False
for name, urls in FEEDS.items():
    for u in urls:
        try:
            r = requests.get(u, headers=UA, timeout=20)
            if r.status_code != 200 or b'<rss' not in r.content[:500].lower() and b'<feed' not in r.content[:500].lower():
                print(f'[{name}] {u} → HTTP {r.status_code}, không phải RSS'); continue
            items = ET.fromstring(r.content).iter('item')
            rows = []
            for it in items:
                t, link, desc, pub = (clean(it.findtext(k)) for k in ('title', 'link', 'description', 'pubDate'))
                try: when = parsedate_to_datetime(pub).astimezone(now.tzinfo)
                except Exception: when = None
                if when and (now - when).total_seconds() > 36 * 3600: continue
                rows.append((when, t, desc[:220], link))
            print(f'\n== NEWS [{name}] {u} · {len(rows)} tin trong 36 giờ ==')
            for w, t, dsc, link in rows[:25]:
                print(f'- {w:%d/%m %H:%M} | {t} | {dsc} | {link}' if w else f'- {t} | {dsc} | {link}')
            ok_any = True; break
        except Exception as e:
            print(f'[{name}] {u} → lỗi {type(e).__name__}: {str(e)[:120]}')
if not ok_any:
    print('KHÔNG lấy được nguồn tin nào — agent quyết định chỉ dựa trên dữ liệu hệ thống và ghi rõ trong sổ lệnh.')
