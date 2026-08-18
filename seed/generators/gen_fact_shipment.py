"""Derived từ fact_orders: đơn có shipped_at → tạo shipment row.

SLA theo region (VN realistic):
  • intra-city (cùng thành phố):           24h
  • intra-region (cùng miền N/C/S):        48h
  • cross-region (liên miền, VD HCM↔HN):   72h
"""
from tqdm import tqdm
from .utils import bulk_insert, VN_CITIES


# Build city → region map once
CITY_REGION = {city: region for city, _, region, _ in VN_CITIES}


def region_of(city: str) -> str:
    """Return 'north' / 'central' / 'south' / 'unknown'."""
    return CITY_REGION.get(city, "unknown")


def sla_hours(from_city: str, to_city: str) -> int:
    if from_city == to_city:
        return 24
    r_from = region_of(from_city)
    r_to   = region_of(to_city)
    if r_from == "unknown" or r_to == "unknown":
        return 48           # fallback
    if r_from == r_to:
        return 48           # cùng miền
    return 72               # liên miền


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
    for order_id, carrier, shipped_at, delivered_at, from_city, to_city, _to_prov in tqdm(orders, desc="shipment"):
        sla = sla_hours(from_city, to_city)

        pickup = shipped_at
        if delivered_at is not None:
            actual_hours = int((delivered_at - pickup).total_seconds() / 3600)
            if actual_hours < 1:
                # delivered trước shipped = data anomaly — gán ngẫu nhiên dưới SLA
                actual_hours = rng.randint(1, sla)
            is_on_time = actual_hours <= sla
        else:
            actual_hours = None
            is_on_time = None

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
