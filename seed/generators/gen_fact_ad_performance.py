"""Aggregate daily ad performance: derive từ fact_orders có campaign + cat1."""
from tqdm import tqdm
from .utils import bulk_insert


def run(conn, cfg, rng):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT o.order_date_key, o.campaign_id, p.cat1_id,
                   COUNT(DISTINCT o.order_id) AS orders,
                   SUM(o.total_amount) AS gmv
            FROM shopee.fact_orders o
            JOIN shopee.fact_order_items i ON i.order_id = o.order_id
            JOIN shopee.dim_product p ON p.product_id = i.product_id
            WHERE o.campaign_id IS NOT NULL AND o.payment_status='paid'
            GROUP BY o.order_date_key, o.campaign_id, p.cat1_id
            """
        )
        aggs = cur.fetchall()

    rows = []
    for dk, cid, cat1, orders, gmv in tqdm(aggs, desc="ad_perf"):
        impressions = int(orders * rng.uniform(80, 200))
        clicks = int(impressions * rng.uniform(0.02, 0.06))
        rows.append((dk, cid, cat1, impressions, clicks, orders, gmv))

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_ad_performance_daily",
            ["date_key","campaign_id","cat1_id","impressions","clicks",
             "orders_attributed","gmv_attributed"],
            rows, on_conflict="(date_key,campaign_id,cat1_id) DO NOTHING",
            page_size=5000,
        )
    conn.commit()
    return n
