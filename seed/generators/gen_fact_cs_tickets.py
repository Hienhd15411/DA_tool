"""CS tickets on a % of orders."""
from datetime import timedelta
from tqdm import tqdm
from .utils import bulk_insert

CATEGORIES = ["shipping","quality","refund","voucher","account","other"]
PRIORITIES = ["low","med","high","urgent"]
STATUSES   = ["resolved","closed","in_progress","open"]


def run(conn, cfg, rng):
    rate = cfg["volumes"]["tickets_rate"]
    with conn.cursor() as cur:
        cur.execute(
            """SELECT order_id, customer_id, seller_id, created_at
               FROM shopee.fact_orders
               WHERE order_status IN ('completed','shipping','returned','refunded')"""
        )
        orders = cur.fetchall()

    rows = []
    tid = 1
    for order_id, customer_id, seller_id, created_at in tqdm(orders, desc="tickets"):
        if rng.random() > rate:
            continue
        cat = rng.choices(
            CATEGORIES,
            weights=[35, 20, 18, 10, 5, 12],
            k=1,
        )[0]
        prio = rng.choices(PRIORITIES, weights=[30, 45, 20, 5], k=1)[0]
        status = rng.choices(STATUSES, weights=[50, 30, 15, 5], k=1)[0]
        created = created_at + timedelta(days=rng.randint(1, 7))
        resolved = None
        if status in ("resolved","closed"):
            resolved = created + timedelta(hours=rng.randint(2, 120))
        rows.append((tid, order_id, customer_id, seller_id, cat, prio, status,
                     created, resolved))
        tid += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_customer_service_ticket",
            ["ticket_id","order_id","customer_id","seller_id","category",
             "priority","status","created_at","resolved_at"],
            rows, on_conflict="(ticket_id) DO NOTHING", page_size=2000,
        )
    conn.commit()
    return n
