"""Shopee VN-like 4-level category tree."""
from .utils import bulk_insert

# (cat1, cat2, cat3, cat4_list)
TREE = [
    ("Thời Trang Nữ", "Áo", "Áo Thun",
        ["Áo Thun Basic", "Áo Thun Oversize", "Áo Thun Crop", "Áo Thun Graphic"]),
    ("Thời Trang Nữ", "Áo", "Áo Sơ Mi",
        ["Sơ Mi Công Sở", "Sơ Mi Lụa", "Sơ Mi Kẻ"]),
    ("Thời Trang Nữ", "Quần", "Quần Jeans",
        ["Jeans Skinny", "Jeans Baggy", "Jeans Mom"]),
    ("Thời Trang Nữ", "Đầm", "Đầm Dài",
        ["Đầm Maxi", "Đầm Công Sở"]),

    ("Thời Trang Nam", "Áo", "Áo Thun Nam",
        ["Áo Thun Basic Nam", "Áo Polo"]),
    ("Thời Trang Nam", "Áo", "Áo Sơ Mi Nam",
        ["Sơ Mi Trắng", "Sơ Mi Caro"]),
    ("Thời Trang Nam", "Quần", "Quần Dài",
        ["Quần Jeans Nam", "Quần Tây", "Quần Kaki"]),

    ("Điện Tử", "Điện Thoại", "Smartphone",
        ["iPhone", "Samsung", "Xiaomi", "Oppo"]),
    ("Điện Tử", "Điện Thoại", "Phụ Kiện",
        ["Ốp Lưng", "Sạc Dự Phòng", "Cáp Sạc"]),
    ("Điện Tử", "Laptop", "Laptop Văn Phòng",
        ["Dell", "HP", "Lenovo"]),
    ("Điện Tử", "Laptop", "Laptop Gaming",
        ["Asus ROG", "Acer Nitro"]),
    ("Điện Tử", "Âm Thanh", "Tai Nghe",
        ["Tai Nghe Bluetooth", "Tai Nghe Có Dây", "Earbuds"]),

    ("Nhà Cửa & Đời Sống", "Bếp", "Nồi Chảo",
        ["Nồi Chiên Không Dầu", "Chảo Chống Dính", "Nồi Cơm Điện"]),
    ("Nhà Cửa & Đời Sống", "Bếp", "Đồ Dùng Nấu Ăn",
        ["Dao Kéo", "Thớt", "Tô Chén"]),
    ("Nhà Cửa & Đời Sống", "Gia Dụng", "Vệ Sinh Nhà Cửa",
        ["Máy Hút Bụi", "Cây Lau Nhà", "Nước Giặt"]),
    ("Nhà Cửa & Đời Sống", "Nội Thất", "Giường Tủ",
        ["Giường Ngủ", "Tủ Quần Áo"]),

    ("Sắc Đẹp", "Chăm Sóc Da", "Kem Dưỡng",
        ["Kem Chống Nắng", "Kem Dưỡng Ẩm", "Serum"]),
    ("Sắc Đẹp", "Chăm Sóc Da", "Làm Sạch",
        ["Sữa Rửa Mặt", "Tẩy Trang"]),
    ("Sắc Đẹp", "Trang Điểm", "Son",
        ["Son Lì", "Son Tint", "Son Dưỡng"]),
    ("Sắc Đẹp", "Trang Điểm", "Nền",
        ["Kem Nền", "Cushion"]),

    ("Mẹ & Bé", "Sữa", "Sữa Bột",
        ["Sữa Bột Cho Trẻ 0-1", "Sữa Bột Cho Trẻ 1-3", "Sữa Bầu"]),
    ("Mẹ & Bé", "Tã", "Tã Dán",
        ["Tã Dán Sơ Sinh", "Tã Dán Trẻ Nhỏ"]),
    ("Mẹ & Bé", "Đồ Chơi", "Đồ Chơi Phát Triển",
        ["Đồ Chơi Gỗ", "Đồ Chơi Xếp Hình"]),

    ("Thể Thao", "Quần Áo", "Quần Áo Gym",
        ["Quần Legging", "Áo Tank Top"]),
    ("Thể Thao", "Dụng Cụ", "Tập Gym",
        ["Thảm Yoga", "Tạ Tay", "Dây Kháng Lực"]),

    ("Bách Hoá", "Thực Phẩm Khô", "Mì & Phở",
        ["Mì Gói", "Phở Khô"]),
    ("Bách Hoá", "Đồ Uống", "Nước Giải Khát",
        ["Nước Ngọt", "Nước Suối", "Cà Phê Đóng Chai"]),
    ("Bách Hoá", "Đồ Uống", "Sữa Tươi",
        ["Sữa Tươi Tiệt Trùng", "Sữa Chua Uống"]),

    ("Sức Khỏe", "Vitamin", "Vitamin Tổng Hợp",
        ["Vitamin C", "Vitamin D3"]),
    ("Sức Khỏe", "Thiết Bị Y Tế", "Đo Lường",
        ["Máy Đo Huyết Áp", "Nhiệt Kế"]),

    ("Sách & Văn Phòng Phẩm", "Sách", "Sách Kinh Doanh",
        ["Sách Marketing", "Sách Quản Trị"]),
    ("Sách & Văn Phòng Phẩm", "Văn Phòng", "Bút & Giấy",
        ["Bút Bi", "Sổ Tay"]),
]


def run(conn, cfg):
    rows = []
    cat_id = 1

    cat1_map: dict[str, int] = {}
    cat2_map: dict[tuple[str, str], int] = {}
    cat3_map: dict[tuple[str, str, str], int] = {}

    # Level 1
    seen_c1 = set()
    for c1, *_ in TREE:
        if c1 not in seen_c1:
            seen_c1.add(c1)
            cat1_map[c1] = cat_id
            rows.append((cat_id, c1, 1, None, c1))
            cat_id += 1

    # Level 2
    seen_c2 = set()
    for c1, c2, _, _ in TREE:
        key = (c1, c2)
        if key not in seen_c2:
            seen_c2.add(key)
            cat2_map[key] = cat_id
            rows.append((cat_id, c2, 2, cat1_map[c1], f"{c1} > {c2}"))
            cat_id += 1

    # Level 3
    seen_c3 = set()
    for c1, c2, c3, _ in TREE:
        key = (c1, c2, c3)
        if key not in seen_c3:
            seen_c3.add(key)
            cat3_map[key] = cat_id
            rows.append((cat_id, c3, 3, cat2_map[(c1, c2)], f"{c1} > {c2} > {c3}"))
            cat_id += 1

    # Level 4 (leaf)
    for c1, c2, c3, c4s in TREE:
        for c4 in c4s:
            rows.append((cat_id, c4, 4, cat3_map[(c1, c2, c3)], f"{c1} > {c2} > {c3} > {c4}"))
            cat_id += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.dim_category",
            ["category_id","category_name","level","parent_id","full_path"],
            rows, on_conflict="(category_id) DO NOTHING",
        )
    conn.commit()
    return n
