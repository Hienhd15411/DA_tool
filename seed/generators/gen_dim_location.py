from .utils import VN_CITIES, bulk_insert


def run(conn, cfg):
    rows = [
        (i + 1, city, prov, region, is_major)
        for i, (city, prov, region, is_major) in enumerate(VN_CITIES)
    ]
    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.dim_location",
            ["location_id","city","province","region","is_major_city"],
            rows, on_conflict="(location_id) DO NOTHING",
        )
    conn.commit()
    return n
