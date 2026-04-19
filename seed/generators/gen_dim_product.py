from datetime import date, timedelta
from .utils import bulk_insert

BRANDS = ["Local", "Generic", "Samsung", "Xiaomi", "Uniqlo", "Zara", "Adidas", "Nike",
          "L'Oreal", "Innisfree", "Unilever", "P&G", "Philips", "Asus", "Dell",
          "Vinamilk", "TH True Milk", "No Brand"]


def run(conn, cfg, rng):
    n = cfg["volumes"]["products"]
    start = date.fromisoformat(cfg["dates"]["start"])

    # Lấy cat4 (leaf) từ dim_category đã seed
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH leaf AS (
              SELECT c4.category_id AS c4_id, c4.category_name AS c4_name,
                     c3.category_id AS c3_id, c3.category_name AS c3_name,
                     c2.category_id AS c2_id, c2.category_name AS c2_name,
                     c1.category_id AS c1_id, c1.category_name AS c1_name
              FROM shopee.dim_category c4
              JOIN shopee.dim_category c3 ON c4.parent_id = c3.category_id
              JOIN shopee.dim_category c2 ON c3.parent_id = c2.category_id
              JOIN shopee.dim_category c1 ON c2.parent_id = c1.category_id
              WHERE c4.level = 4
            )
            SELECT c4_id,c4_name,c3_id,c3_name,c2_id,c2_name,c1_id,c1_name FROM leaf
            """
        )
        cats = cur.fetchall()
        cur.execute("SELECT seller_id FROM shopee.dim_seller")
        seller_ids = [r[0] for r in cur.fetchall()]

    # price bands tuỳ cat1 — rough realistic
    price_bands = {
        "Điện Tử": (200_000, 20_000_000),
        "Thời Trang Nữ": (80_000, 800_000),
        "Thời Trang Nam": (100_000, 900_000),
        "Nhà Cửa & Đời Sống": (50_000, 3_000_000),
        "Sắc Đẹp": (60_000, 1_200_000),
        "Mẹ & Bé": (80_000, 1_500_000),
        "Thể Thao": (100_000, 2_500_000),
        "Bách Hoá": (15_000, 500_000),
        "Sức Khỏe": (50_000, 3_000_000),
        "Sách & Văn Phòng Phẩm": (20_000, 400_000),
    }

    rows = []
    for pid in range(1, n + 1):
        c4_id, c4_name, c3_id, c3_name, c2_id, c2_name, c1_id, c1_name = rng.choice(cats)
        lo, hi = price_bands.get(c1_name, (50_000, 1_000_000))
        # log-uniform ish
        price = int(rng.triangular(lo, hi, lo + (hi - lo) * 0.3))
        price = round(price, -3)  # nghìn đồng
        launch = start - timedelta(days=rng.randint(1, 720))
        seller_id = rng.choice(seller_ids)
        name = f"{rng.choice(BRANDS)} {c4_name} #{pid}"
        rows.append((
            pid, name[:200], seller_id,
            rng.choice(BRANDS),
            price,
            launch,
            c1_id, c1_name,
            c2_id, c2_name,
            c3_id, c3_name,
            c4_id, c4_name,
            rng.random() > 0.05,  # 95% active
        ))

    with conn.cursor() as cur:
        n_ins = bulk_insert(
            cur, "shopee.dim_product",
            ["product_id","product_name","seller_id","brand","list_price","launch_date",
             "cat1_id","cat1_name","cat2_id","cat2_name","cat3_id","cat3_name",
             "cat4_id","cat4_name","is_active"],
            rows, on_conflict="(product_id) DO NOTHING", page_size=2000,
        )
    conn.commit()
    return n_ins
