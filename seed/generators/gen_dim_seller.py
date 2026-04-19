from datetime import date, timedelta
from faker import Faker
from .utils import VN_CITIES, bulk_insert, date_key

SHOP_SUFFIXES = ["Store", "Official", "Shop", "Mart", "Boutique", "House", "Hub"]


def run(conn, cfg, rng):
    faker = Faker("vi_VN")
    Faker.seed(cfg["seed"] + 1)

    n = cfg["volumes"]["sellers"]
    start = date.fromisoformat(cfg["dates"]["start"])

    types = [("normal", 0.70), ("preferred", 0.22), ("mall", 0.08)]
    tnames, tweights = zip(*types)

    rows = []
    for sid in range(1, n + 1):
        city, prov, *_ = rng.choices(
            VN_CITIES,
            weights=[8 if c[3] else 1 for c in VN_CITIES],
            k=1,
        )[0]
        join_day = start - timedelta(days=rng.randint(1, 1200))
        shop_type = rng.choices(tnames, weights=tweights, k=1)[0]
        is_official = shop_type == "mall" or rng.random() < 0.05
        shop_name = f"{faker.company().split(' ')[0]} {rng.choice(SHOP_SUFFIXES)}"
        rows.append((
            sid, shop_name[:150], shop_type,
            city, prov,
            date_key(join_day),
            is_official,
        ))

    with conn.cursor() as cur:
        n_ins = bulk_insert(
            cur, "shopee.dim_seller",
            ["seller_id","shop_name","shop_type","seller_city",
             "seller_province","join_date_key","is_official"],
            rows, on_conflict="(seller_id) DO NOTHING", page_size=2000,
        )
    conn.commit()
    return n_ins
