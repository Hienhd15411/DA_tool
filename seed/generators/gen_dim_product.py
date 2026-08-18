"""Generate dim_product — brand map đúng theo cat1, tên sản phẩm realistic."""
from datetime import date, timedelta
from .utils import bulk_insert


# Brand theo cat1 — tránh "Nike" bán "đồ mẹ và bé". Dựa trên Shopee VN thực tế.
BRANDS_BY_CAT1 = {
    "Điện Tử": [
        "Samsung", "Xiaomi", "Apple", "Oppo", "Vivo", "Realme", "Honor",
        "Asus", "Dell", "HP", "Lenovo", "Acer", "MSI",
        "Philips", "Sony", "JBL", "Anker", "Baseus", "Ugreen",
    ],
    "Thời Trang Nữ": [
        "Uniqlo", "Zara", "H&M", "Mango", "Routine", "Canifa", "NEM",
        "IVY Moda", "Eva de Eva", "Format", "YODY", "Juno", "Vascara",
    ],
    "Thời Trang Nam": [
        "Uniqlo", "Zara", "H&M", "Adidas", "Nike", "Puma", "Owen",
        "Routine", "Canifa", "YODY", "Aristino", "John Henry", "M2",
    ],
    "Nhà Cửa & Đời Sống": [
        "Philips", "Panasonic", "Sunhouse", "Lock&Lock", "Elmich",
        "Inochi", "Tefal", "Bluestone", "Kangaroo", "Happy Cook", "IKEA",
    ],
    "Sắc Đẹp": [
        "L'Oreal", "Innisfree", "The Face Shop", "Laneige", "Maybelline",
        "MAC", "Dove", "Nivea", "Olay", "Pond's", "Senka", "La Roche-Posay",
        "Eucerin", "Cocoon", "Bioderma",
    ],
    "Mẹ & Bé": [
        "Vinamilk", "Abbott", "Dutch Lady", "Meiji", "Nan", "Similac",
        "Pampers", "Huggies", "Bobby", "Merries", "Moony", "Goo.N",
        "Fisher-Price", "Pigeon",
    ],
    "Thể Thao": [
        "Nike", "Adidas", "Puma", "Under Armour", "Reebok", "New Balance",
        "Decathlon", "Asics", "Li-Ning",
    ],
    "Bách Hoá": [
        "Vinamilk", "TH True Milk", "Nestle", "Acecook", "Masan",
        "Coca-Cola", "Pepsi", "Lipton", "Heineken", "Tiger", "Unilever",
        "P&G", "Lay's", "Orion",
    ],
    "Sức Khỏe": [
        "Blackmores", "Abbott", "Pharmacity", "Mediplantex", "Traphaco",
        "Nature's Bounty", "DHC", "Omron", "Kobayashi", "Herbalife",
    ],
    "Sách & Văn Phòng Phẩm": [
        "Thiên Long", "Pentel", "Stabilo", "Deli", "Campus", "Hồng Hà",
        "First News", "Alpha Books", "NXB Trẻ", "NXB Kim Đồng", "Nhã Nam",
    ],
}

DEFAULT_BRANDS = ["Local", "Generic", "No Brand"]

# Colours dùng nhiều trong tên sản phẩm
COLORS_FASHION = ["Đen", "Trắng", "Xám", "Be", "Xanh Navy", "Xanh Dương",
                  "Đỏ", "Hồng", "Vàng", "Nâu", "Xanh Rêu", "Trắng Kem"]
COLORS_TECH = ["Đen", "Trắng", "Bạc", "Xanh", "Tím", "Vàng Gold", "Graphite"]

SIZES_CLOTHES = ["S", "M", "L", "XL", "XXL"]
SIZES_SHOES = ["36", "37", "38", "39", "40", "41", "42", "43"]
STORAGES_PHONE = ["64GB", "128GB", "256GB", "512GB"]
STORAGES_LAPTOP = ["256GB SSD", "512GB SSD", "1TB SSD"]
RAM_LAPTOP = ["8GB", "16GB", "32GB"]


def make_product_name(rng, brand: str, c4_name: str) -> str:
    """Sinh tên sản phẩm realistic theo loại cat4. Không dùng # id vô nghĩa."""
    low = c4_name.lower()

    # Smartphone
    if any(kw in low for kw in ["iphone", "samsung", "xiaomi", "oppo", "smartphone"]):
        variant = rng.choice(["Pro", "Pro Max", "Plus", "Ultra", "Lite", "Mini", "SE", ""]).strip()
        storage = rng.choice(STORAGES_PHONE)
        color = rng.choice(COLORS_TECH)
        tag = " " + variant if variant else ""
        return f"{brand} {c4_name}{tag} {storage} - {color}"

    # Laptop
    if "laptop" in low or any(kw in low for kw in ["dell", "hp", "lenovo", "asus", "acer"]):
        line = rng.choice(["Inspiron", "Pavilion", "ThinkPad", "Aspire", "IdeaPad", "ROG Strix", "Nitro", "Vivobook"])
        ram = rng.choice(RAM_LAPTOP)
        ssd = rng.choice(STORAGES_LAPTOP)
        return f"{brand} {line} {ram} {ssd}"

    # Tai nghe / Earbuds / Âm thanh
    if any(kw in low for kw in ["tai nghe", "earbuds", "loa"]):
        model = rng.choice(["Pro", "Sport", "Mini", "Plus", "Air", "Bass"])
        color = rng.choice(COLORS_TECH)
        return f"{brand} {c4_name} {model} - {color}"

    # Phụ kiện điện thoại
    if any(kw in low for kw in ["ốp lưng", "sạc", "cáp"]):
        color = rng.choice(COLORS_TECH)
        return f"{brand} {c4_name} - {color}"

    # Giày dép
    if any(kw in low for kw in ["giày", "dép"]):
        size = rng.choice(SIZES_SHOES)
        color = rng.choice(COLORS_FASHION)
        return f"{brand} {c4_name} {color} - Size {size}"

    # Quần áo
    if any(kw in low for kw in ["áo", "quần", "đầm", "sơ mi", "jeans", "kaki", "legging", "tank"]):
        size = rng.choice(SIZES_CLOTHES)
        color = rng.choice(COLORS_FASHION)
        return f"{brand} {c4_name} {color} Size {size}"

    # Son / Kem / Mỹ phẩm
    if any(kw in low for kw in ["son", "kem dưỡng", "kem chống", "serum", "cushion", "kem nền", "tẩy trang"]):
        shade = rng.choice(["Natural", "Pink Nude", "Red Velvet", "Coral", "Rose", "SPF50", "Intense", "Glow"])
        size = rng.choice(["3.5g", "10ml", "30ml", "50ml", "100ml"])
        return f"{brand} {c4_name} {shade} {size}"

    # Sữa rửa mặt
    if "sữa rửa mặt" in low:
        size = rng.choice(["100ml", "150ml", "200ml"])
        return f"{brand} {c4_name} {size}"

    # Sữa bột / sữa tươi
    if "sữa" in low:
        size = rng.choice(["400g", "900g", "1.5kg", "Hộp 6 x 180ml", "Lốc 4 hộp"])
        return f"{brand} {c4_name} {size}"

    # Tã
    if "tã" in low:
        size = rng.choice(["Size S - 64 miếng", "Size M - 54 miếng", "Size L - 48 miếng", "Size XL - 42 miếng"])
        return f"{brand} {c4_name} {size}"

    # Nồi chảo
    if any(kw in low for kw in ["nồi", "chảo"]):
        size = rng.choice(["24cm", "26cm", "28cm", "30cm", "3.5L", "5L"])
        return f"{brand} {c4_name} {size}"

    # Dao / thớt / tô chén
    if any(kw in low for kw in ["dao", "thớt", "tô", "chén"]):
        return f"{brand} {c4_name} bộ {rng.choice([3, 5, 6, 10])} món"

    # Máy hút bụi / lau nhà
    if any(kw in low for kw in ["máy hút bụi", "cây lau nhà"]):
        return f"{brand} {c4_name} {rng.choice(['cao cấp', 'thông minh', 'đa năng'])}"

    # Giường tủ
    if "giường" in low or "tủ" in low:
        size = rng.choice(["1m4", "1m6", "1m8", "2m"])
        return f"{brand} {c4_name} {size}"

    # Tạ tay / Thảm yoga / Dây kháng
    if any(kw in low for kw in ["tạ tay", "thảm yoga", "dây kháng"]):
        spec = rng.choice(["5kg", "10kg", "6mm", "8mm", "cường độ cao"])
        return f"{brand} {c4_name} {spec}"

    # Thực phẩm khô / đồ uống
    if any(kw in low for kw in ["mì gói", "phở khô"]):
        return f"{brand} {c4_name} {rng.choice(['thùng 30 gói', 'lốc 5 gói', 'gói 75g'])}"
    if any(kw in low for kw in ["nước ngọt", "nước suối", "cà phê đóng chai"]):
        size = rng.choice(["330ml", "500ml", "1.5L", "lốc 6"])
        return f"{brand} {c4_name} {size}"

    # Vitamin / Thiết bị y tế
    if "vitamin" in low:
        return f"{brand} {c4_name} lọ {rng.choice([30, 60, 100, 120])} viên"
    if any(kw in low for kw in ["máy đo", "nhiệt kế"]):
        return f"{brand} {c4_name} {rng.choice(['điện tử', 'thông minh'])}"

    # Sách — không prefix brand
    if "sách" in low:
        return c4_name

    # Bút / sổ
    if any(kw in low for kw in ["bút", "sổ"]):
        return f"{brand} {c4_name} {rng.choice(['hộp 12', 'vỉ 10', 'bộ 5'])}"

    # Fallback — brand + cat4 + colour (không dùng #id)
    color = rng.choice(COLORS_FASHION)
    return f"{brand} {c4_name} - {color}"


def run(conn, cfg, rng):
    n = cfg["volumes"]["products"]
    start = date.fromisoformat(cfg["dates"]["start"])

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

    # Price bands theo cat1
    price_bands = {
        "Điện Tử":             (200_000, 20_000_000),
        "Thời Trang Nữ":       (80_000,   800_000),
        "Thời Trang Nam":      (100_000,  900_000),
        "Nhà Cửa & Đời Sống":  (50_000, 3_000_000),
        "Sắc Đẹp":             (60_000, 1_200_000),
        "Mẹ & Bé":             (80_000, 1_500_000),
        "Thể Thao":            (100_000, 2_500_000),
        "Bách Hoá":            (15_000,   500_000),
        "Sức Khỏe":            (50_000, 3_000_000),
        "Sách & Văn Phòng Phẩm":(20_000,  400_000),
    }

    # Mỗi seller có 1 cat1 chính (để cùng shop không bán lộn xộn mọi ngành).
    # 80% sản phẩm của seller match cat1 chính, 20% lấn sang cat1 khác.
    cat1_names = list({c[7] for c in cats})
    seller_primary_cat1 = {sid: rng.choice(cat1_names) for sid in seller_ids}

    rows = []
    for pid in range(1, n + 1):
        # Pick seller trước; pick cat4 phù hợp với primary cat1 của seller (80%)
        seller_id = rng.choice(seller_ids)
        primary = seller_primary_cat1[seller_id]
        if rng.random() < 0.80:
            candidates = [c for c in cats if c[7] == primary] or cats
        else:
            candidates = cats
        c4_id, c4_name, c3_id, c3_name, c2_id, c2_name, c1_id, c1_name = rng.choice(candidates)

        # Brand đúng theo cat1
        brand_pool = BRANDS_BY_CAT1.get(c1_name, DEFAULT_BRANDS)
        # 8% sản phẩm không có brand (local/generic)
        if rng.random() < 0.08:
            brand = rng.choice(DEFAULT_BRANDS)
        else:
            brand = rng.choice(brand_pool)

        # Price
        lo, hi = price_bands.get(c1_name, (50_000, 1_000_000))
        price = int(rng.triangular(lo, hi, lo + (hi - lo) * 0.3))
        price = round(price, -3)  # nghìn đồng

        # Name realistic
        name = make_product_name(rng, brand, c4_name)

        launch = start - timedelta(days=rng.randint(1, 720))
        is_active = rng.random() > 0.05  # 95% active

        rows.append((
            pid, name[:200], seller_id,
            brand,                         # ← brand ở cột bằng brand trong name
            price,
            launch,
            c1_id, c1_name,
            c2_id, c2_name,
            c3_id, c3_name,
            c4_id, c4_name,
            is_active,
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
