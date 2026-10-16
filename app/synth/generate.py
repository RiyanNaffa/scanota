"""app/synth/generate.py – Generate deterministic synthetic transaction CSVs.

Writes to data/sample_transactions/:
    products.csv, aliases.csv,
    offline_history.csv (78 weeks, ~75% offline),
    online_orders.csv (CSV webhook format).

Run: python -m app.synth.generate
"""

from __future__ import annotations

import csv
import hashlib
import os
import random
from datetime import date, timedelta

from app.synth.catalog import CATALOG

# Deterministic seed
RNG_SEED = 42
WEEKS = 78
OFFLINE_RATIO = 0.75

OUTPUT_DIR = os.path.join("data", "sample_transactions")

CONTRACTORS = [
    "CV Maju Konstruksi",
    "Budi Santoso",
    "Toko Bangunan Jaya",
    "Pak Herman",
    "CV Berkah Bersama",
    "Hendra Wijaya",
]
WALK_INS = ["Pembeli Umum", "Pelanggan Toko", None, None]


def _weekly_demand(base: float, week: int, total_weeks: int, rng: random.Random) -> float:
    """Intermittent demand with weekly seasonality, month-end bump, mild trend."""
    # Trend: +10% over the full period
    trend = 1.0 + 0.10 * (week / total_weeks)
    # Weekly seasonality: bump on weeks 1 and 3 of each 4-week month
    week_of_month = week % 4
    seasonality = 1.2 if week_of_month in (0, 2) else 1.0
    # Month-end bump (last week of every 4-week period)
    month_end = 1.3 if week_of_month == 3 else 1.0
    expected = base * trend * seasonality * month_end
    # Intermittency: Poisson-like, ~30% zero weeks
    if rng.random() < 0.3:
        return 0.0
    # Sample from Poisson (approximated as bounded normal)
    raw = max(0.0, rng.gauss(expected, expected * 0.3))
    return raw


def _price_variation(base_price: int, rng: random.Random) -> int:
    """Add ±5% price variation."""
    factor = 1.0 + rng.uniform(-0.05, 0.05)
    return max(1, round(base_price * factor))


def generate_data() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    rng = random.Random(RNG_SEED)

    # End date: last Sunday (week boundary)
    today = date.today()
    days_since_sunday = today.weekday() + 1  # Monday=0 ... Sunday=6, so +1 for Sunday=0
    end_date = today - timedelta(days=days_since_sunday % 7)
    start_date = end_date - timedelta(weeks=WEEKS)

    # ---- products.csv ----
    with open(os.path.join(OUTPUT_DIR, "products.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            ["sku_id", "name", "category", "unit", "cost_price", "current_stock", "lead_time_days"]
        )
        for item in CATALOG:
            w.writerow(
                [
                    item.sku_id,
                    item.name,
                    item.category,
                    item.unit,
                    item.price,
                    item.initial_stock,
                    item.lead_time_days,
                ]
            )

    # ---- aliases.csv ----
    with open(os.path.join(OUTPUT_DIR, "aliases.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["alias_raw", "sku_id"])
        for item in CATALOG:
            for alias in item.aliases:
                w.writerow([alias, item.sku_id])

    # ---- Generate weekly transactions ----
    offline_rows = []
    online_rows = []
    order_counter = 1

    for week_idx in range(WEEKS):
        week_start = start_date + timedelta(weeks=week_idx)

        for item in CATALOG:
            demand = _weekly_demand(item.base_weekly_demand, week_idx, WEEKS, rng)
            if demand == 0:
                continue

            # Decide channel
            is_online = rng.random() > OFFLINE_RATIO

            if is_online:
                # One online order for this SKU-week
                qty = max(1, round(demand))
                unit_price = _price_variation(item.price, rng)
                external_ref = f"ORD-{week_start.year}-{order_counter:06d}"
                order_counter += 1
                customer = rng.choice(CONTRACTORS)
                tx_date = week_start + timedelta(days=rng.randint(0, 6))
                online_rows.append(
                    {
                        "external_ref": external_ref,
                        "date": tx_date.isoformat(),
                        "customer": customer,
                        "item_name": rng.choice(item.aliases),
                        "qty": qty,
                        "unit": item.unit,
                        "unit_price": unit_price,
                    }
                )
            else:
                # 1-3 offline transactions spread across the week
                num_tx = rng.randint(1, 3)
                remaining = demand
                for tx_i in range(num_tx):
                    if remaining <= 0:
                        break
                    qty = max(1, round(remaining / (num_tx - tx_i)))
                    unit_price = _price_variation(item.price, rng)
                    tx_date = week_start + timedelta(days=rng.randint(0, 6))
                    customer = rng.choice(CONTRACTORS + WALK_INS)
                    alias_used = rng.choice(item.aliases)
                    # Unique ref for offline
                    ref_hash = hashlib.md5(
                        f"{tx_date}{item.sku_id}{tx_i}{week_idx}".encode()
                    ).hexdigest()[:8]
                    offline_rows.append(
                        {
                            "date": tx_date.isoformat(),
                            "customer": customer or "",
                            "item_name": alias_used,
                            "sku_id": item.sku_id,
                            "qty": qty,
                            "unit": item.unit,
                            "unit_price": unit_price,
                            "line_total": qty * unit_price,
                            "source": "seed",
                            "seed_ref": ref_hash,
                        }
                    )
                    remaining -= qty

    # ---- offline_history.csv ----
    with open(
        os.path.join(OUTPUT_DIR, "offline_history.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow(
            [
                "date",
                "customer",
                "item_name",
                "sku_id",
                "qty",
                "unit",
                "unit_price",
                "line_total",
                "source",
                "seed_ref",
            ]
        )
        for row in sorted(offline_rows, key=lambda r: r["date"]):
            w.writerow(
                [
                    row["date"],
                    row["customer"],
                    row["item_name"],
                    row["sku_id"],
                    row["qty"],
                    row["unit"],
                    row["unit_price"],
                    row["line_total"],
                    row["source"],
                    row["seed_ref"],
                ]
            )

    # ---- online_orders.csv ----
    with open(
        os.path.join(OUTPUT_DIR, "online_orders.csv"), "w", newline="", encoding="utf-8"
    ) as f:
        w = csv.writer(f)
        w.writerow(["external_ref", "date", "customer", "item_name", "qty", "unit", "unit_price"])
        for row in sorted(online_rows, key=lambda r: r["date"]):
            w.writerow(
                [
                    row["external_ref"],
                    row["date"],
                    row["customer"],
                    row["item_name"],
                    row["qty"],
                    row["unit"],
                    row["unit_price"],
                ]
            )

    print(f"Generated {len(offline_rows)} offline rows and {len(online_rows)} online rows")
    print(f"Period: {start_date} to {end_date} ({WEEKS} weeks)")
    print(f"Files written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    generate_data()
