"""Sessions sampled — ~10% DAU + guest sessions."""
from datetime import date
from tqdm import tqdm
from .utils import bulk_insert, daterange, date_key

SOURCES   = ["organic","paid","social","direct","affiliate"]
LANDINGS  = ["home","category","product","search","campaign"]
DEVICES   = ["android","ios","web"]


def run(conn, cfg, rng):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])

    with conn.cursor() as cur:
        cur.execute("SELECT customer_id FROM shopee.dim_customer")
        cust_ids = [r[0] for r in cur.fetchall()]

    sample = cust_ids[: int(len(cust_ids) * 0.30)]  # subset for realistic sampling

    rows = []
    sid = 1
    for d in tqdm(list(daterange(start, end)), desc="traffic"):
        dk = date_key(d)
        # sessions per day
        n_sessions = int(len(sample) * rng.uniform(0.15, 0.35))
        for _ in range(n_sessions):
            cid = rng.choice(sample) if rng.random() < 0.75 else None  # 25% guest
            src = rng.choices(SOURCES, weights=[45, 25, 10, 15, 5], k=1)[0]
            landing = rng.choices(LANDINGS, weights=[30, 20, 25, 15, 10], k=1)[0]
            pv = rng.randint(1, 30)
            dur = pv * rng.randint(20, 90)
            has_order = cid is not None and rng.random() < 0.04
            rows.append((sid, cid, dk, rng.choice(DEVICES), src, landing,
                         pv, dur, has_order))
            sid += 1
            if len(rows) >= 50000:
                _flush(conn, rows)
                rows.clear()

    _flush(conn, rows)
    return sid - 1


def _flush(conn, rows):
    with conn.cursor() as cur:
        bulk_insert(
            cur, "shopee.fact_traffic_session",
            ["session_id","customer_id","date_key","device_type",
             "traffic_source","landing_page_type","pageviews",
             "duration_seconds","has_order"],
            rows, on_conflict="(session_id) DO NOTHING", page_size=5000,
        )
    conn.commit()
