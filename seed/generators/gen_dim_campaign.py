from datetime import date, timedelta
from .utils import bulk_insert, date_key


def run(conn, cfg, rng):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])

    campaigns = []
    cid = 1

    # Mega sales
    for dstr in cfg["dates"]["sale_days"]:
        d = date.fromisoformat(dstr)
        if start <= d <= end:
            campaigns.append((
                cid,
                f"{d.month}.{d.month} Mega Sale",
                "mega_sale",
                date_key(d - timedelta(days=3)),
                date_key(d + timedelta(days=1)),
                "marketing",
            ))
            cid += 1

    # Payday sales (ngày 25)
    cur_d = start.replace(day=1)
    while cur_d <= end:
        try:
            payday = cur_d.replace(day=25)
        except ValueError:
            payday = cur_d + timedelta(days=24)
        if start <= payday <= end:
            campaigns.append((
                cid, f"Payday {payday.strftime('%b')}",
                "payday_sale",
                date_key(payday - timedelta(days=1)),
                date_key(payday + timedelta(days=1)),
                "marketing",
            ))
            cid += 1
        # bump month
        nx = cur_d.month + 1
        ny = cur_d.year + (1 if nx > 12 else 0)
        cur_d = cur_d.replace(year=ny, month=(nx - 1) % 12 + 1, day=1)

    # Category sales random
    cat_names = ["Fashion Fest", "Beauty Week", "Electronic Fair",
                 "Home & Living Sale", "Mom & Baby Day", "Sports Week"]
    owners = ["category", "marketing", "seller_ops"]
    while cid <= cfg["volumes"]["ad_campaigns"]:
        s = start + timedelta(days=rng.randint(0, (end - start).days - 5))
        e = s + timedelta(days=rng.randint(2, 7))
        e = min(e, end)
        cname = f"{rng.choice(cat_names)} {s.strftime('%b')}"
        campaigns.append((
            cid, cname,
            rng.choice(["flash_sale","category_sale","voucher_only"]),
            date_key(s), date_key(e),
            rng.choice(owners),
        ))
        cid += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.dim_campaign",
            ["campaign_id","campaign_name","campaign_type",
             "start_date_key","end_date_key","owner_team"],
            campaigns, on_conflict="(campaign_id) DO NOTHING",
        )
    conn.commit()
    return n
