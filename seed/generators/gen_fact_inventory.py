"""Weekly snapshot stock qty for ~20% product sample (not all SKU for size reason)."""
from datetime import date, timedelta
from tqdm import tqdm
from .utils import bulk_insert, date_key


def run(conn, cfg, rng):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])

    # iterate mỗi thứ Hai
    d = start - timedelta(days=start.isoweekday() - 1)
    mondays = []
    while d <= end:
        if d >= start:
            mondays.append(d)
        d += timedelta(days=7)

    with conn.cursor() as cur:
        cur.execute("SELECT product_id, seller_id FROM shopee.dim_product WHERE is_active")
        prods = cur.fetchall()

    # ~20% sample
    sample = rng.sample(prods, k=int(len(prods) * 0.5))

    rows = []
    for monday in tqdm(mondays, desc="inventory"):
        dk = date_key(monday)
        for pid, sid in sample:
            if rng.random() < 0.05:
                qty = 0
                in_stock = False
            else:
                qty = rng.randint(1, 500)
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
