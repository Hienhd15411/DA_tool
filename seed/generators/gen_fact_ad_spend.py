"""Daily ad spend per campaign per channel."""
from datetime import date
from tqdm import tqdm
from .utils import bulk_insert, daterange, date_key

CHANNELS = ["search","display","affiliate","kol"]


def run(conn, cfg, rng):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])

    with conn.cursor() as cur:
        cur.execute(
            """SELECT campaign_id, start_date_key, end_date_key, campaign_type
               FROM shopee.dim_campaign"""
        )
        campaigns = cur.fetchall()

    rows = []
    sid = 1
    for d in tqdm(list(daterange(start, end)), desc="ad_spend"):
        dk = date_key(d)
        for cid, s, e, ctype in campaigns:
            if not (s <= dk <= e):
                continue
            # budget theo type
            base = {"mega_sale": 2_000_000, "payday_sale": 800_000,
                    "flash_sale": 500_000, "category_sale": 600_000,
                    "voucher_only": 200_000}.get(ctype, 300_000)
            for ch in CHANNELS:
                spend = round(base * rng.uniform(0.4, 1.2), 0)
                impressions = int(spend / rng.uniform(2, 5))  # CPM 2-5k
                clicks = int(impressions * rng.uniform(0.01, 0.05))
                rows.append((sid, dk, cid, ch, spend, impressions, clicks))
                sid += 1

    with conn.cursor() as cur:
        n = bulk_insert(
            cur, "shopee.fact_ad_spend",
            ["ad_spend_id","date_key","campaign_id","channel",
             "spend_amount","impressions","clicks"],
            rows, on_conflict="(ad_spend_id) DO NOTHING", page_size=5000,
        )
    conn.commit()
    return n
