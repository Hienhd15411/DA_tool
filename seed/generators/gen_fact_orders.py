"""Generate fact_orders + fact_order_items together (tightly coupled).

Logic biz:
- Mỗi ngày ~1500 đơn (6000 vào sale day).
- Mỗi đơn 1-5 items (mean 2).
- subtotal = sum(line_total).
- Discounts: 65% đơn có voucher/discount.
- Status flow: completed (70%), cancelled (8%), returned (3%), shipping (12%), others (7%).
- Edge cases: cancelled_with_paid, completed_no_delivered, rounding lost.
"""
from __future__ import annotations
import string
from datetime import date, datetime, timedelta, timezone
from typing import Any
from tqdm import tqdm
from .utils import (
    bulk_insert, chunked, date_key, daterange,
    peak_hour_distribution, pick_weighted,
)


def _gen_order_sn(rng, created_at: datetime) -> str:
    tail = "".join(rng.choices(string.ascii_uppercase + string.digits, k=10))
    return f"{created_at.strftime('%y%m%d')}{tail}"


def _status_flow(rng, anomalies) -> str:
    return pick_weighted(rng, [
        ("completed", 0.70),
        ("cancelled", 0.08),
        ("returned",  0.03),
        ("shipping",  0.08),
        ("to_ship",   0.04),
        ("pending",   0.04),
        ("refunded",  0.03),
    ])


def run(conn, cfg, rng):
    start = date.fromisoformat(cfg["dates"]["start"])
    end   = date.fromisoformat(cfg["dates"]["end"])
    sale_days = {date.fromisoformat(s) for s in cfg["dates"]["sale_days"]}
    anomalies = cfg["anomalies"]
    carriers  = cfg["shopee_context"]["carriers"]
    devices   = cfg["shopee_context"]["devices"]
    payments  = cfg["shopee_context"]["payment"]

    with conn.cursor() as cur:
        cur.execute("SELECT customer_id, city, province, preferred_device FROM shopee.dim_customer")
        customers = cur.fetchall()
        cur.execute("""SELECT product_id, seller_id, list_price, cat1_name
                       FROM shopee.dim_product WHERE is_active""")
        products = cur.fetchall()
        cur.execute("""SELECT seller_id, seller_city FROM shopee.dim_seller""")
        seller_city = {sid: city for sid, city in cur.fetchall()}
        cur.execute("""SELECT campaign_id, start_date_key, end_date_key
                       FROM shopee.dim_campaign""")
        campaigns = cur.fetchall()

    customer_first_seen: dict[int, bool] = {}  # track first order flag

    order_id = 1
    item_id = 1
    cancel_reasons = [
        "out_of_stock", "customer_change_mind", "seller_no_response",
        "payment_failed", "address_error", "price_wrong"
    ]

    orders_rows: list[tuple[Any, ...]] = []
    items_rows:  list[tuple[Any, ...]] = []

    total_days = (end - start).days + 1
    pbar = tqdm(total=total_days, desc="fact_orders")

    for d in daterange(start, end):
        is_sale = d in sale_days or (d.day == d.month and d.day <= 5)
        daily_n = cfg["volumes"]["orders_per_day_sale"] if is_sale else cfg["volumes"]["orders_per_day_normal"]
        # add jitter
        daily_n = int(daily_n * rng.uniform(0.85, 1.15))
        # month trend: T3 giảm, T4 giảm thêm (dạy case A3)
        if d.month == 3:
            daily_n = int(daily_n * 0.88)
        if d.month == 4:
            daily_n = int(daily_n * 0.82)

        # campaign for this day
        dk = date_key(d)
        active_camps = [c[0] for c in campaigns if c[1] <= dk <= c[2]]

        for _ in range(daily_n):
            customer_id, cust_city, cust_prov, pref_device = rng.choice(customers)
            is_first = not customer_first_seen.get(customer_id, False)
            customer_first_seen[customer_id] = True

            # timestamp
            hour = peak_hour_distribution(rng)
            created_at = datetime(d.year, d.month, d.day, hour,
                                  rng.randint(0, 59), rng.randint(0, 59),
                                  tzinfo=timezone.utc)

            # status
            status = _status_flow(rng, anomalies)
            payment_method = rng.choices(payments, weights=[35, 30, 15, 10, 10], k=1)[0]
            device = pref_device if rng.random() < 0.7 else rng.choice(devices)

            # campaign attribution
            campaign_id = rng.choice(active_camps) if active_camps and rng.random() < 0.35 else None

            # items
            n_items = max(1, int(rng.gauss(cfg["volumes"]["items_per_order_mean"], 1.2)))
            n_items = min(n_items, 8)

            first_product = rng.choice(products)
            seller_id = first_product[1]
            # đơn này gộp từ 1 seller (simplified — Shopee multi-seller thường split order)
            seller_products = [p for p in products if p[1] == seller_id]
            if not seller_products:
                continue
            picked = [rng.choice(seller_products) for _ in range(n_items)]

            # build items + subtotal
            item_rows_local = []
            subtotal = 0.0
            for p in picked:
                pid, _, list_price, _ = p
                qty = rng.choices([1, 2, 3], weights=[75, 18, 7], k=1)[0]
                # chiết khấu mặc định của seller 0-20%
                item_discount_rate = rng.triangular(0, 0.20, 0.05)
                unit_price = float(list_price) * (1 - item_discount_rate)
                line_total = round(unit_price * qty, 2)
                item_discount = round(float(list_price) * qty - line_total, 2)
                item_rows_local.append((item_id, order_id, pid, seller_id, qty,
                                         round(unit_price, 2), item_discount, line_total))
                item_id += 1
                subtotal += line_total

            subtotal = round(subtotal, 2)

            # voucher & discount
            shop_discount = 0.0
            platform_voucher = 0.0
            shipping_fee = round(rng.uniform(15000, 40000), 0)
            shipping_discount = 0.0
            coin_used = 0.0
            if rng.random() < 0.35:
                shop_discount = round(subtotal * rng.uniform(0.02, 0.10), 0)
            if campaign_id and rng.random() < 0.6:
                platform_voucher = round(subtotal * rng.uniform(0.05, 0.15), 0)
            if rng.random() < 0.45:
                shipping_discount = round(shipping_fee * rng.uniform(0.3, 1.0), 0)
            if rng.random() < 0.20:
                coin_used = round(rng.uniform(1000, 10000), 0)

            total_amount = round(subtotal - shop_discount - platform_voucher
                                 + shipping_fee - shipping_discount - coin_used, 2)

            # anomaly: rounding lost
            if rng.random() < anomalies["amount_rounding_lost_pct"]:
                total_amount += rng.choice([-1, 1]) * rng.randint(1, 5)

            # timestamps by status
            paid_at = shipped_at = delivered_at = completed_at = cancelled_at = None
            cancel_reason = None
            payment_status = "paid"
            if status in ("completed", "returned", "refunded", "shipping"):
                paid_at = created_at + timedelta(minutes=rng.randint(1, 120))
                if status != "pending":
                    shipped_at = paid_at + timedelta(hours=rng.randint(8, 48))
            if status in ("completed", "returned"):
                delivered_at = shipped_at + timedelta(hours=rng.randint(12, 96))
                if status == "completed":
                    completed_at = delivered_at + timedelta(days=rng.randint(1, 5))
            if status == "cancelled":
                cancelled_at = created_at + timedelta(
                    hours=rng.choice([rng.uniform(0.1, 1), rng.uniform(1, 24), rng.uniform(24, 72)])
                )
                cancel_reason = rng.choice(cancel_reasons)
                if rng.random() < anomalies["cancelled_with_paid_at_pct"]:
                    paid_at = created_at + timedelta(minutes=rng.randint(1, 30))
                    payment_status = "refunded"
                else:
                    payment_status = "unpaid"
            if status == "refunded":
                payment_status = "refunded"
            if status == "completed" and rng.random() < anomalies["completed_no_delivered_pct"]:
                delivered_at = None
            if status == "pending":
                payment_status = "unpaid"
                paid_at = None
            if status == "to_ship":
                paid_at = created_at + timedelta(minutes=rng.randint(1, 60))

            # shipping
            carrier = None
            if status in ("to_ship", "shipping", "completed", "returned"):
                carrier = rng.choice(carriers)
            from_city = seller_city.get(seller_id) or rng.choice(["TP HCM", "Hà Nội"])

            order_sn = _gen_order_sn(rng, created_at)
            # ~0.3% đơn sn bị viết hoa/thường lẫn lộn để dạy data quality
            if rng.random() < 0.003:
                order_sn = order_sn.lower()

            orders_rows.append((
                order_id, order_sn, customer_id, seller_id, campaign_id,
                date_key(d), status, payment_method, payment_status,
                carrier, from_city, cust_city, cust_prov,
                device, n_items,
                subtotal, shop_discount, platform_voucher,
                shipping_fee, shipping_discount, coin_used, total_amount,
                is_first, cancel_reason,
                created_at, paid_at, shipped_at, delivered_at, completed_at, cancelled_at,
            ))
            items_rows.extend(item_rows_local)
            order_id += 1

        # flush mỗi ngày
        if len(orders_rows) >= 20000:
            _flush(conn, orders_rows, items_rows)
            orders_rows.clear()
            items_rows.clear()

        pbar.update(1)

    _flush(conn, orders_rows, items_rows)
    pbar.close()
    return order_id - 1


def _flush(conn, orders_rows, items_rows):
    with conn.cursor() as cur:
        bulk_insert(
            cur, "shopee.fact_orders",
            ["order_id","order_sn","customer_id","seller_id","campaign_id",
             "order_date_key","order_status","payment_method","payment_status",
             "shipping_provider","ship_from_city","ship_to_city","ship_to_province",
             "device_type","item_count","subtotal","shop_discount","platform_voucher",
             "shipping_fee","shipping_discount","coin_used","total_amount",
             "is_first_order","cancel_reason",
             "created_at","paid_at","shipped_at","delivered_at","completed_at","cancelled_at"],
            orders_rows, on_conflict="(order_id) DO NOTHING", page_size=2000,
        )
        bulk_insert(
            cur, "shopee.fact_order_items",
            ["order_item_id","order_id","product_id","seller_id","quantity",
             "unit_price","item_discount","line_total"],
            items_rows, on_conflict="(order_item_id) DO NOTHING", page_size=5000,
        )
    conn.commit()
