"""Weekly stock snapshot cho 50% active products.

Stock qty theo cat1 (realistic): điện tử giá cao → stock thấp hơn bách hoá giá rẻ.
"""
from datetime import date, timedelta
from tqdm import tqdm
from .utils import bulk_insert, date_key

# Stock range theo cat1 (min, max)
STOCK_RANGE = {
    "Điện Tử":             (0, 80),     # giá cao, giữ ít stock
    "Thời Trang Nữ":       (5, 200),
    "Thời Trang Nam":      (5, 200),
    "Nhà Cửa & Đời Sống":  (5, 150),
    "Sắc Đẹp":             (10, 300),
    "Mẹ & Bé":             (10, 250),
    "Thể Thao":            (5, 180),
    "Bách Hoá":            (20, 500),   # giá rẻ, stock lớn
    "Sức Khỏe":            (10, 200),
    "Sách & Văn Phòng Phẩm":(5, 150),
}


def run(conn, cfg, rng):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])

    d = start - timedelta(days=start.isoweekday() - 1)
    mondays = []
    while d <= end:
        if d >= start:
            mondays.append(d)
        d += timedelta(days=7)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT product_id, seller_id, cat1_name FROM shopee.dim_product WHERE is_active"
        )
        prods = cur.fetchall()

    # 50% sample
    sample = rng.sample(prods, k=int(len(prods) * 0.5))

    rows = []
    for monday in tqdm(mondays, desc="inventory"):
        dk = date_key(monday)
        for pid, sid, cat1 in sample:
            lo, hi = STOCK_RANGE.get(cat1, (1, 300))
            if rng.random() < 0.05:                  # 5% out of stock
                qty, in_stock = 0, False
            else:
                qty = rng.randint(max(lo, 1), hi)
                in_stock = True
            rows.append((dk, pid, sid, qty, in_stock))

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_inventory_weekly",
            ["snapshot_date_key","product_id","seller_id","stock_qty","is_in_stock"],
            rows,
            on_conflict="(snapshot_date_key,product_id) DO NOTHING",
            page_size=5000,
        )
    conn.commit()
    return n
