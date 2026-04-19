"""Derived từ fact_orders: đơn có shipped_at → tạo shipment row."""
from datetime import timedelta
from tqdm import tqdm
from .utils import bulk_insert


def run(conn, cfg, rng):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT order_id, shipping_provider, shipped_at, delivered_at,
                   ship_from_city, ship_to_city, ship_to_province
            FROM shopee.fact_orders
            WHERE shipped_at IS NOT NULL
            """
        )
        orders = cur.fetchall()

    rows = []
    shipment_id = 1
    for order_id, carrier, shipped_at, delivered_at, from_city, to_city, to_prov in tqdm(orders, desc="shipment"):
        # SLA theo route: intra-city 24h, liên tỉnh 48h, liên miền 72h
        if from_city == to_city:
            sla = 24
        elif from_city in ("TP HCM","Hà Nội") and to_city in ("TP HCM","Hà Nội"):
            sla = 72  # liên miền
        else:
            sla = 48

        pickup = shipped_at
        if delivered_at is not None:
            actual_hours = int((delivered_at - pickup).total_seconds() / 3600)
            # thêm noise đôi khi âm -> skip anomaly cho shipment
            if actual_hours < 1:
                actual_hours = rng.randint(1, sla)
            is_on_time = actual_hours <= sla
        else:
            actual_hours = None
            is_on_time = None

        # carrier fallback
        c = carrier or rng.choice(cfg["shopee_context"]["carriers"])

        rows.append((
            shipment_id, order_id, c, pickup, delivered_at,
            sla, actual_hours, is_on_time,
            round(rng.uniform(0.3, 5.0), 2),
        ))
        shipment_id += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_shipment",
            ["shipment_id","order_id","carrier","pickup_at","delivered_at",
             "sla_committed_hours","actual_hours","is_on_time","weight_kg"],
            rows, on_conflict="(shipment_id) DO NOTHING", page_size=5000,
        )
    conn.commit()
    return n
