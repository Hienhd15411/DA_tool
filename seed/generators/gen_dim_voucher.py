from datetime import date, timedelta
from .utils import bulk_insert, date_key


def run(conn, cfg, rng):
    n = cfg["volumes"]["vouchers"]
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])

    with conn.cursor() as cur:
        cur.execute("SELECT campaign_id FROM shopee.dim_campaign")
        campaign_ids = [r[0] for r in cur.fetchall()]

    rows = []
    for vid in range(1, n + 1):
        vtype = rng.choices(
            ["shop","platform","shipping"],
            weights=[55, 30, 15], k=1,
        )[0]
        dtype = rng.choices(["percent","fixed"], weights=[60, 40], k=1)[0]
        if dtype == "percent":
            value = rng.choice([5, 10, 15, 20, 25, 30, 40, 50])
            # min_order tối thiểu scale theo % voucher — tránh 50% voucher với min_order=0
            #   ≤15%: 0-300k · 20-30%: 100k-500k · ≥40%: 300k-1M
            if value <= 15:
                min_order = rng.choice([0, 100000, 200000, 300000])
            elif value <= 30:
                min_order = rng.choice([100000, 200000, 300000, 500000])
            else:
                min_order = rng.choice([300000, 500000, 1000000])
            max_disc = rng.choice([20000, 50000, 100000, 200000])
        else:
            value = rng.choice([10000, 20000, 30000, 50000, 100000])
            # Fixed: min_order ≥ 5× voucher value (tránh free-money case)
            min_order = rng.choice([
                max(0, value * 3),
                max(value * 5, 100000),
                max(value * 10, 200000),
            ])
            max_disc = value

        v_from = start + timedelta(days=rng.randint(-10, 10))
        v_to   = v_from + timedelta(days=rng.randint(3, 30))
        v_to   = min(v_to, end + timedelta(days=30))

        campaign_id = rng.choice(campaign_ids) if rng.random() < 0.7 and campaign_ids else None
        code = f"{vtype[:3].upper()}{vid:05d}"
        rows.append((
            vid, code, vtype, dtype, value, min_order, max_disc,
            date_key(v_from), date_key(v_to), campaign_id,
        ))

    with conn.cursor() as cur:
        n_ins = bulk_insert(
            cur, "shopee.dim_voucher",
            ["voucher_id","voucher_code","voucher_type","discount_type",
             "discount_value","min_order_value","max_discount",
             "valid_from_date_key","valid_to_date_key","campaign_id"],
            rows, on_conflict="(voucher_id) DO NOTHING", page_size=2000,
        )
    conn.commit()
    return n_ins
