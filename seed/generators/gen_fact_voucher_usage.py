"""Đơn có platform_voucher > 0 → tạo voucher usage row."""
from datetime import timedelta
from tqdm import tqdm
from .utils import bulk_insert


def run(conn, cfg, rng):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT order_id, campaign_id, platform_voucher, created_at
            FROM shopee.fact_orders
            WHERE platform_voucher > 0
            """
        )
        orders = cur.fetchall()

        cur.execute("""SELECT voucher_id, campaign_id FROM shopee.dim_voucher""")
        v_by_camp: dict[int | None, list[int]] = {}
        all_v = []
        for vid, cid in cur.fetchall():
            v_by_camp.setdefault(cid, []).append(vid)
            all_v.append(vid)

    rows = []
    vid_seq = 1
    for order_id, campaign_id, disc, created_at in tqdm(orders, desc="voucher_usage"):
        pool = v_by_camp.get(campaign_id) or all_v
        if not pool:
            continue
        voucher_id = rng.choice(pool)
        used_at = created_at + timedelta(seconds=rng.randint(0, 120))
        rows.append((vid_seq, order_id, voucher_id, float(disc), used_at))
        vid_seq += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_voucher_usage",
            ["voucher_usage_id","order_id","voucher_id","discount_applied","used_at"],
            rows, on_conflict="(voucher_usage_id) DO NOTHING", page_size=5000,
        )
    conn.commit()
    return n
