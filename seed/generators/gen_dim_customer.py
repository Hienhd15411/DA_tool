from datetime import date, timedelta
from faker import Faker
from .utils import VN_CITIES, bulk_insert, date_key


def run(conn, cfg, rng):
    faker = Faker("vi_VN")
    Faker.seed(cfg["seed"])

    n = cfg["volumes"]["customers"]
    start = date.fromisoformat(cfg["dates"]["start"])

    tiers = [("bronze", 0.55), ("silver", 0.28), ("gold", 0.13), ("platinum", 0.04)]
    tier_names, tier_weights = zip(*tiers)

    rows = []
    for cid in range(1, n + 1):
        city, prov, *_ = rng.choices(
            VN_CITIES,
            weights=[5 if c[3] else 1 for c in VN_CITIES],
            k=1,
        )[0]
        gender = rng.choices(["female","male","other"], weights=[55, 42, 3], k=1)[0]
        birth_year = rng.randint(1975, 2006)
        # signup giữa 2 năm trước start đến start
        signup_day = start - timedelta(days=rng.randint(1, 730))
        device = rng.choices(["android","ios","web"], weights=[60, 30, 10], k=1)[0]
        tier = rng.choices(tier_names, weights=tier_weights, k=1)[0]
        rows.append((
            cid,
            faker.name(),
            gender,
            birth_year,
            date_key(signup_day),
            city, prov,
            device,
            tier,
        ))

    with conn.cursor() as cur:
        inserted = bulk_insert(
            cur, "shopee.dim_customer",
            ["customer_id","customer_name","gender","birth_year",
             "signup_date_key","city","province","preferred_device","tier"],
            rows, on_conflict="(customer_id) DO NOTHING", page_size=2000,
        )
    conn.commit()
    return inserted
