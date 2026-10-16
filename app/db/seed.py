"""app/db/seed.py – Load synthetic data into the database.

Idempotent: uses ON CONFLICT DO NOTHING / DO UPDATE and skips existing external_refs.

Run: python -m app.db.seed
"""
from __future__ import annotations

import csv
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed")

DATA_DIR = os.path.join("data", "sample_transactions")


def seed() -> None:
    # Import here so the module can be loaded without a DB connection at import time
    from app.db.repository import (
        add_alias,
        create_transaction,
        get_catalog_aliases,
        get_price_stats,
        get_transaction_by_external_ref,
        upsert_product,
    )
    from app.db.session import SessionLocal
    from app.validation.pipeline import validate_extraction

    db = SessionLocal()
    try:
        _seed_products(db, upsert_product, add_alias)
        db.commit()
        logger.info("Products and aliases seeded.")

        _seed_transactions(db, get_catalog_aliases, get_price_stats, create_transaction,
                           get_transaction_by_external_ref, validate_extraction)
    finally:
        db.close()


def _seed_products(db, upsert_product, add_alias) -> None:
    products_path = os.path.join(DATA_DIR, "products.csv")
    if not os.path.exists(products_path):
        logger.warning("products.csv not found, skipping. Run `python -m app.synth.generate` first.")
        return

    with open(products_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            upsert_product(db, {
                "sku_id": row["sku_id"],
                "name": row["name"],
                "category": row["category"],
                "unit": row["unit"],
                "cost_price": int(row["cost_price"]) if row["cost_price"] else None,
                "current_stock": float(row["current_stock"]),
                "lead_time_days": int(row["lead_time_days"]),
            })

    aliases_path = os.path.join(DATA_DIR, "aliases.csv")
    if os.path.exists(aliases_path):
        with open(aliases_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                add_alias(db, row["alias_raw"], row["sku_id"], source="seed")

    db.commit()


def _seed_transactions(
    db, get_catalog_aliases, get_price_stats, create_transaction,
    get_transaction_by_external_ref, validate_extraction,
) -> None:
    catalog = get_catalog_aliases(db)
    price_stats = get_price_stats(db)

    online_count = 0
    offline_count = 0
    skipped = 0

    # ---- Online orders ----
    online_path = os.path.join(DATA_DIR, "online_orders.csv")
    if os.path.exists(online_path):
        with open(online_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Group by external_ref
        orders: dict[str, dict] = {}
        for row in rows:
            ref = row["external_ref"]
            if ref not in orders:
                orders[ref] = {
                    "external_ref": ref,
                    "date": row["date"],
                    "customer": row["customer"] or None,
                    "items": [],
                }
            qty = float(row["qty"])
            unit_price = int(row["unit_price"])
            orders[ref]["items"].append({
                "item_name_raw": row["item_name"],
                "qty": qty,
                "unit": row.get("unit"),
                "unit_price": unit_price,
                "line_total": round(qty) * unit_price,
            })

        for ref, order in orders.items():
            if get_transaction_by_external_ref(db, ref):
                skipped += 1
                continue
            order["total"] = sum(it["line_total"] for it in order["items"])
            extraction = {
                "date": order["date"],
                "customer": order["customer"],
                "items": order["items"],
                "total": order["total"],
            }
            result = validate_extraction(extraction, catalog, price_stats)
            create_transaction(
                db,
                tx_date=order["date"],
                channel="online",
                customer=order["customer"],
                total=order["total"],
                source="seed",
                status=result.status,
                confidence=result.confidence,
                issues=result.issues,
                external_ref=ref,
                items=[
                    {
                        "item_name_raw": iwm.item_name_raw,
                        "sku_id": iwm.sku_id,
                        "qty": iwm.qty,
                        "unit": iwm.unit,
                        "unit_price": iwm.unit_price,
                        "line_total": iwm.line_total,
                        "match_score": iwm.match_score,
                    }
                    for iwm in result.items_with_matches
                ],
            )
            online_count += 1

    # ---- Offline history ----
    offline_path = os.path.join(DATA_DIR, "offline_history.csv")
    if os.path.exists(offline_path):
        with open(offline_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        # Group by seed_ref (each seed_ref = one transaction)
        tx_groups: dict[str, list] = {}
        tx_meta: dict[str, dict] = {}
        for row in rows:
            ref = f"SEED-OFFLINE-{row['seed_ref']}"
            tx_groups.setdefault(ref, []).append(row)
            tx_meta[ref] = {"date": row["date"], "customer": row["customer"] or None}

        for ref, group in tx_groups.items():
            if get_transaction_by_external_ref(db, ref):
                skipped += 1
                continue
            items = [
                {
                    "item_name_raw": r["item_name"],
                    "qty": float(r["qty"]),
                    "unit": r["unit"],
                    "unit_price": int(r["unit_price"]),
                    "line_total": int(r["line_total"]),
                }
                for r in group
            ]
            total = sum(it["line_total"] for it in items)
            extraction = {
                "date": tx_meta[ref]["date"],
                "customer": tx_meta[ref]["customer"],
                "items": items,
                "total": total,
            }
            result = validate_extraction(extraction, catalog, price_stats)
            create_transaction(
                db,
                tx_date=tx_meta[ref]["date"],
                channel="offline",
                customer=tx_meta[ref]["customer"],
                total=total,
                source="seed",
                status=result.status,
                confidence=result.confidence,
                issues=result.issues,
                external_ref=ref,
                items=[
                    {
                        "item_name_raw": iwm.item_name_raw,
                        "sku_id": iwm.sku_id,
                        "qty": iwm.qty,
                        "unit": iwm.unit,
                        "unit_price": iwm.unit_price,
                        "line_total": iwm.line_total,
                        "match_score": iwm.match_score,
                    }
                    for iwm in result.items_with_matches
                ],
            )
            offline_count += 1

    logger.info(
        "Seed complete: online=%d, offline=%d, skipped=%d",
        online_count, offline_count, skipped,
    )


if __name__ == "__main__":
    seed()
