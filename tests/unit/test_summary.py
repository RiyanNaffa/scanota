"""tests/unit/test_summary.py – get_summary builds valid SQL (runs against in-memory SQLite)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.repository import get_summary


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE transactions (id INTEGER PRIMARY KEY, tx_date TEXT, channel TEXT, "
                "total INTEGER, status TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE transaction_items (transaction_id INTEGER, sku_id TEXT, line_total INTEGER)"
            )
        )
        conn.execute(text("CREATE TABLE products (sku_id TEXT, name TEXT)"))
        conn.execute(text("INSERT INTO products VALUES ('PSR001', 'Pasir Beton 1 Kubik')"))
        conn.execute(
            text(
                "INSERT INTO transactions VALUES "
                "(1, '2026-06-07', 'offline', 1000, 'confirmed'), "
                "(2, '2026-07-01', 'online',  500, 'confirmed'), "
                "(3, '2026-07-02', 'online',  900, 'needs_review')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO transaction_items VALUES (1, 'PSR001', 1000), (2, 'PSR001', 500), "
                "(3, 'PSR001', 900)"
            )
        )
    with Session(engine) as session:
        yield session


def test_summary_without_filters(db):
    """Regression: the top-products query used to render 'WHERE AND t.status = ...'."""
    result = get_summary(db)

    assert result["total_sales"] == 1500
    assert result["total_transactions"] == 2
    assert result["needs_review_count"] == 1
    assert result["top_products"] == [{"name": "Pasir Beton 1 Kubik", "revenue": 1500}]


def test_summary_with_date_filters(db):
    result = get_summary(db, date_from="2026-07-01", date_to="2026-07-31")

    assert result["total_sales"] == 500
    assert result["top_products"] == [{"name": "Pasir Beton 1 Kubik", "revenue": 500}]


def test_summary_with_no_data_in_range(db):
    result = get_summary(db, date_from="2030-01-01")

    assert result["total_sales"] == 0
    assert result["top_products"] == []
