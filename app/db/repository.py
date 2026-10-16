"""app/db/repository.py – Data access functions.

All functions accept a SQLAlchemy Session and return plain Python dicts or None.
No ORM models – uses raw SQL via text() to stay aligned with the schema.sql.
"""

from __future__ import annotations

import datetime
import json
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.validation.matching import normalize

# -----------------------------------------------------------------------
# Products / catalog
# -----------------------------------------------------------------------


def get_catalog_aliases(db: Session) -> list[dict[str, Any]]:
    """Return all product aliases for matching."""
    rows = db.execute(text("SELECT alias_norm, sku_id FROM product_aliases")).fetchall()
    return [{"alias_norm": r[0], "sku_id": r[1]} for r in rows]


def get_products(db: Session) -> list[dict[str, Any]]:
    """Return all products."""
    rows = db.execute(
        text(
            "SELECT sku_id, name, category, unit, cost_price, "
            "current_stock, lead_time_days, created_at FROM products ORDER BY name"
        )
    ).fetchall()
    return [
        _row_to_dict(
            r,
            [
                "sku_id",
                "name",
                "category",
                "unit",
                "cost_price",
                "current_stock",
                "lead_time_days",
                "created_at",
            ],
        )
        for r in rows
    ]


def get_product(db: Session, sku_id: str) -> dict | None:
    row = db.execute(
        text(
            "SELECT sku_id, name, category, unit, cost_price, current_stock, "
            "lead_time_days, created_at FROM products WHERE sku_id = :sku_id"
        ),
        {"sku_id": sku_id},
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(
        row,
        [
            "sku_id",
            "name",
            "category",
            "unit",
            "cost_price",
            "current_stock",
            "lead_time_days",
            "created_at",
        ],
    )


def update_stock(db: Session, sku_id: str, current_stock: Decimal) -> bool:
    result = db.execute(
        text("UPDATE products SET current_stock = :stock WHERE sku_id = :sku_id"),
        {"stock": current_stock, "sku_id": sku_id},
    )
    db.commit()
    return result.rowcount > 0


def get_price_stats(db: Session) -> dict[str, dict[str, Any]]:
    """Return median unit_price and count per SKU from confirmed transactions."""
    rows = db.execute(
        text(
            """
            SELECT i.sku_id,
                   PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY i.unit_price) AS median,
                   COUNT(*) AS cnt
            FROM transaction_items i
            JOIN transactions t ON t.id = i.transaction_id
            WHERE t.status = 'confirmed' AND i.sku_id IS NOT NULL
            GROUP BY i.sku_id
            HAVING COUNT(*) >= 5
            """
        )
    ).fetchall()
    return {r[0]: {"median": float(r[1]), "count": int(r[2])} for r in rows}


def upsert_product(db: Session, product: dict[str, Any]) -> None:
    """Insert or update a product (used by seed)."""
    db.execute(
        text(
            """
            INSERT INTO products (sku_id, name, category, unit, cost_price, current_stock, lead_time_days)
            VALUES (:sku_id, :name, :category, :unit, :cost_price, :current_stock, :lead_time_days)
            ON CONFLICT (sku_id) DO UPDATE SET
                name = EXCLUDED.name,
                category = EXCLUDED.category,
                unit = EXCLUDED.unit,
                cost_price = EXCLUDED.cost_price,
                current_stock = EXCLUDED.current_stock,
                lead_time_days = EXCLUDED.lead_time_days
            """
        ),
        product,
    )


def add_alias(db: Session, alias_raw: str, sku_id: str, source: str = "seed") -> None:
    """Add a product alias; ignore if alias_norm already exists."""
    alias_norm_val = normalize(alias_raw)
    if not alias_norm_val:
        return
    db.execute(
        text(
            """
            INSERT INTO product_aliases (alias_norm, alias_raw, sku_id, source)
            VALUES (:alias_norm, :alias_raw, :sku_id, :source)
            ON CONFLICT (alias_norm) DO NOTHING
            """
        ),
        {
            "alias_norm": alias_norm_val,
            "alias_raw": alias_raw,
            "sku_id": sku_id,
            "source": source,
        },
    )


# -----------------------------------------------------------------------
# Transactions
# -----------------------------------------------------------------------


def create_transaction(
    db: Session,
    *,
    tx_date: str,
    channel: str,
    customer: str | None,
    total: int,
    source: str,
    status: str,
    confidence: float,
    issues: list,
    external_ref: str | None = None,
    receipt_image_path: str | None = None,
    raw_extraction: dict | None = None,
    items: list[dict],
) -> int:
    """Insert a transaction with its items in a single DB transaction. Returns id."""
    result = db.execute(
        text(
            """
            INSERT INTO transactions
                (tx_date, channel, customer, total, source, status, confidence,
                 issues, external_ref, receipt_image_path, raw_extraction)
            VALUES
                (:tx_date, :channel, :customer, :total, :source, :status, :confidence,
                 CAST(:issues AS jsonb), :external_ref, :receipt_image_path, CAST(:raw_extraction AS jsonb))
            RETURNING id
            """
        ),
        {
            "tx_date": tx_date,
            "channel": channel,
            "customer": customer,
            "total": total,
            "source": source,
            "status": status,
            "confidence": confidence,
            "issues": json.dumps([_issue_to_dict(i) for i in issues]),
            "external_ref": external_ref,
            "receipt_image_path": receipt_image_path,
            "raw_extraction": json.dumps(raw_extraction) if raw_extraction else None,
        },
    )
    tx_id = result.fetchone()[0]

    for item in items:
        db.execute(
            text(
                """
                INSERT INTO transaction_items
                    (transaction_id, item_name_raw, sku_id, qty, unit, unit_price, line_total, match_score)
                VALUES
                    (:transaction_id, :item_name_raw, :sku_id, :qty, :unit,
                     :unit_price, :line_total, :match_score)
                """
            ),
            {
                "transaction_id": tx_id,
                "item_name_raw": item.get("item_name_raw"),
                "sku_id": item.get("sku_id"),
                "qty": item.get("qty"),
                "unit": item.get("unit"),
                "unit_price": item.get("unit_price"),
                "line_total": item.get("line_total"),
                "match_score": item.get("match_score"),
            },
        )

    db.commit()
    return tx_id


def get_transaction_by_external_ref(db: Session, external_ref: str) -> dict | None:
    row = db.execute(
        text("SELECT id, status, confidence, issues FROM transactions WHERE external_ref = :ref"),
        {"ref": external_ref},
    ).fetchone()
    if not row:
        return None
    return {"id": row[0], "status": row[1], "confidence": row[2], "issues": row[3]}


def list_transactions(
    db: Session,
    *,
    channel: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    conditions = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if channel:
        conditions.append("channel = :channel")
        params["channel"] = channel
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if date_from:
        conditions.append("tx_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("tx_date <= :date_to")
        params["date_to"] = date_to

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    rows = db.execute(
        text(
            f"SELECT id, tx_date, channel, customer, total, source, status, "
            f"confidence, issues, external_ref, created_at "
            f"FROM transactions {where} "
            f"ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        ),
        params,
    ).fetchall()
    cols = [
        "id",
        "tx_date",
        "channel",
        "customer",
        "total",
        "source",
        "status",
        "confidence",
        "issues",
        "external_ref",
        "created_at",
    ]
    return [_row_to_dict(r, cols) for r in rows]


def get_transaction_with_items(db: Session, tx_id: int) -> dict | None:
    row = db.execute(
        text(
            "SELECT id, tx_date, channel, customer, total, source, status, "
            "confidence, issues, external_ref, receipt_image_path, raw_extraction, "
            "created_at, reviewed_at FROM transactions WHERE id = :id"
        ),
        {"id": tx_id},
    ).fetchone()
    if not row:
        return None
    tx = _row_to_dict(
        row,
        [
            "id",
            "tx_date",
            "channel",
            "customer",
            "total",
            "source",
            "status",
            "confidence",
            "issues",
            "external_ref",
            "receipt_image_path",
            "raw_extraction",
            "created_at",
            "reviewed_at",
        ],
    )
    items = db.execute(
        text(
            "SELECT id, item_name_raw, sku_id, qty, unit, unit_price, line_total, match_score "
            "FROM transaction_items WHERE transaction_id = :tx_id ORDER BY id"
        ),
        {"tx_id": tx_id},
    ).fetchall()
    tx["items"] = [
        _row_to_dict(
            r,
            [
                "id",
                "item_name_raw",
                "sku_id",
                "qty",
                "unit",
                "unit_price",
                "line_total",
                "match_score",
            ],
        )
        for r in items
    ]
    return tx


def get_review_transactions(db: Session, limit: int = 100, offset: int = 0) -> list[dict]:
    """Return transactions with status='needs_review'."""
    return list_transactions(db, status="needs_review", limit=limit, offset=offset)


def confirm_transaction(
    db: Session,
    tx_id: int,
    *,
    items: list[dict],
    tx_date: str,
    customer: str | None,
    total: int,
    issues: list,
    confidence: float,
    save_aliases: bool = False,
    force: bool = False,
) -> None:
    """Update transaction to confirmed with corrected data."""
    # Delete existing items and re-insert
    db.execute(
        text("DELETE FROM transaction_items WHERE transaction_id = :tx_id"),
        {"tx_id": tx_id},
    )
    db.execute(
        text(
            """
            UPDATE transactions SET
                tx_date = :tx_date,
                customer = :customer,
                total = :total,
                status = 'confirmed',
                confidence = :confidence,
                issues = CAST(:issues AS jsonb),
                reviewed_at = now()
            WHERE id = :id
            """
        ),
        {
            "tx_date": tx_date,
            "customer": customer,
            "total": total,
            "confidence": confidence,
            "issues": json.dumps([_issue_to_dict(i) for i in issues]),
            "id": tx_id,
        },
    )
    for item in items:
        db.execute(
            text(
                """
                INSERT INTO transaction_items
                    (transaction_id, item_name_raw, sku_id, qty, unit, unit_price, line_total, match_score)
                VALUES
                    (:transaction_id, :item_name_raw, :sku_id, :qty, :unit,
                     :unit_price, :line_total, :match_score)
                """
            ),
            {
                "transaction_id": tx_id,
                "item_name_raw": item.get("item_name_raw"),
                "sku_id": item.get("sku_id"),
                "qty": item.get("qty"),
                "unit": item.get("unit"),
                "unit_price": item.get("unit_price"),
                "line_total": item.get("line_total"),
                "match_score": item.get("match_score", None),
            },
        )
        if save_aliases and item.get("sku_id") and item.get("item_name_raw"):
            add_alias(db, item["item_name_raw"], item["sku_id"], source="user_correction")

    db.commit()


# -----------------------------------------------------------------------
# Summary KPIs
# -----------------------------------------------------------------------


def get_summary(
    db: Session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    conditions = ["t.status = 'confirmed'"]
    params: dict[str, Any] = {}
    if date_from:
        conditions.append("t.tx_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("t.tx_date <= :date_to")
        params["date_to"] = date_to
    where = "WHERE " + " AND ".join(conditions)

    # Total sales and counts
    kpi = db.execute(
        text(
            f"SELECT SUM(total), COUNT(*), "
            f"COUNT(*) FILTER (WHERE channel='online'), "
            f"COUNT(*) FILTER (WHERE channel='offline') "
            f"FROM transactions t {where}"
        ),
        params,
    ).fetchone()

    needs_review = db.execute(
        text("SELECT COUNT(*) FROM transactions WHERE status='needs_review'")
    ).scalar()

    # Daily series per channel (last 30 days if no filter)
    daily = db.execute(
        text(
            f"SELECT tx_date, channel, SUM(total) "
            f"FROM transactions t {where} "
            f"GROUP BY tx_date, channel ORDER BY tx_date"
        ),
        params,
    ).fetchall()

    # Top 10 products by revenue
    top = db.execute(
        text(
            f"SELECT p.name, SUM(i.line_total) as revenue "
            f"FROM transaction_items i "
            f"JOIN transactions t ON t.id = i.transaction_id "
            f"LEFT JOIN products p ON p.sku_id = i.sku_id "
            f"{where} "
            f"GROUP BY p.name ORDER BY revenue DESC LIMIT 10"
        ),
        params,
    ).fetchall()

    return {
        "total_sales": int(kpi[0] or 0),
        "total_transactions": int(kpi[1] or 0),
        "online_count": int(kpi[2] or 0),
        "offline_count": int(kpi[3] or 0),
        "needs_review_count": int(needs_review or 0),
        "daily_series": [{"date": str(r[0]), "channel": r[1], "total": int(r[2])} for r in daily],
        "top_products": [{"name": r[0] or "Unknown", "revenue": int(r[1])} for r in top],
    }


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _row_to_dict(row: Any, cols: list[str]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for i, col in enumerate(cols):
        val = row[i]
        if isinstance(val, datetime.date | datetime.datetime):
            val = val.isoformat()
        elif isinstance(val, Decimal):
            val = float(val)
        d[col] = val
    return d


def _issue_to_dict(issue: Any) -> dict:
    if isinstance(issue, dict):
        return issue
    return {
        "code": issue.code,
        "severity": issue.severity,
        "message": issue.message,
        "field": issue.field,
    }
