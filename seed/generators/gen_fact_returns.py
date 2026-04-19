"""Đơn `returned` -> tạo return row."""
from datetime import timedelta
from tqdm import tqdm
from .utils import bulk_insert

REASONS = ["item_damaged","wrong_item","not_as_described","size_issue",
           "customer_change_mind","quality_poor","late_delivery"]


def run(conn, cfg, rng):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.order_id, o.delivered_at, o.subtotal,
                   ARRAY_AGG(i.order_item_id) AS items
            FROM shopee.fact_orders o
            JOIN shopee.fact_order_items i ON i.order_id = o.order_id
            WHERE o.order_status IN ('returned','refunded')
            GROUP BY o.order_id, o.delivered_at, o.subtotal
            """
        )
        orders = cur.fetchall()

    rows = []
    rid = 1
    for order_id, delivered_at, subtotal, item_ids in tqdm(orders, desc="returns"):
        # 80% return 1 item, 20% return cả đơn
        if rng.random() < 0.8 and item_ids:
            oi_id = rng.choice(item_ids)
            refund = round(float(subtotal) * rng.uniform(0.2, 0.9), 2)
        else:
            oi_id = None
            refund = float(subtotal)

        base = delivered_at or rng.choice(orders)[1]
        if base is None:
            continue
        requested_at = base + timedelta(days=rng.randint(1, 10))
        status = rng.choices(
            ["approved","completed","rejected","requested"],
            weights=[30, 50, 10, 10], k=1,
        )[0]
        completed_at = None
        if status == "completed":
            completed_at = requested_at + timedelta(days=rng.randint(2, 14))

        rows.append((rid, order_id, oi_id, rng.choice(REASONS),
                     status, refund, requested_at, completed_at))
        rid += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_returns",
            ["return_id","order_id","order_item_id","return_reason",
             "return_status","refund_amount","requested_at","completed_at"],
            rows, on_conflict="(return_id) DO NOTHING", page_size=2000,
        )
    conn.commit()
    return n
