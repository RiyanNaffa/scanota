"""tests/unit/test_dashboard_views.py – Every dashboard page renders, in both languages.

Needs Streamlit (the dashboard image has it; the API's CI install does not), so it is skipped
where Streamlit is missing. The API client is replaced by canned data: no network.
"""

from __future__ import annotations

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

import dashboard.api_client as api  # noqa: E402

RESTOCK = [
    {
        "sku_id": "SMN002",
        "name": "Semen Gresik 50kg",
        "category": "Semen",
        "unit": "sak",
        "current_stock": 120.0,
        "forecast_next_2_weeks": [7.0, 7.0],
        "model_used": "TSB",
        "days_until_stockout": 120.0,
        "reorder_point": 14.2,
        "suggested_order_qty": 0,
        "action": "ok",
        "reason": "REASON-TEXT",
        "z": 1.8,
        "shelf_life_days": 90,
        "shelf_life_risk": "high",
        "shelf_life_note": "NOTE-TEXT",
        "order_capped_by_shelf_life": False,
        "wape_primary": 0.6,
    }
]
SUMMARY = {
    "total_sales": 1250000,
    "online_count": 3,
    "offline_count": 9,
    "needs_review_count": 1,
    "daily_series": [{"date": "2026-10-01", "channel": "online", "total": 500000}],
    "top_products": [{"name": "Pasir Beton", "revenue": 350000}],
}
TRANSACTIONS = [
    {
        "id": 1,
        "tx_date": "2026-10-01",
        "channel": "offline",
        "source": "scan",
        "customer": None,
        "total": 134784,
        "status": "confirmed",
        "confidence": 0.95,
    }
]
REVIEW = [{"id": 7, "tx_date": "2026-10-02", "channel": "offline", "total": 9000}]
REVIEW_DETAIL = {
    "id": 7,
    "tx_date": "2026-10-02",
    "customer": "Pak Budi",
    "total": 9000,
    "status": "needs_review",
    "receipt_image_path": None,
    "issues": [
        {
            "code": "ITEM_UNMATCHED",
            "severity": "soft",
            "message": "Item 1 '<b>x</b>' could not be matched",
        }
    ],
    "items": [
        {
            "item_name_raw": "x",
            "qty": 1,
            "unit": "pcs",
            "unit_price": 9000,
            "line_total": 9000,
            "sku_id": None,
        }
    ],
}


@pytest.fixture(autouse=True)
def fake_api(monkeypatch):
    monkeypatch.setattr(api, "health", lambda: {"status": "ok"})
    monkeypatch.setattr(api, "summary", lambda **kw: SUMMARY)
    monkeypatch.setattr(api, "restock", lambda explain=None, lang="id": RESTOCK)
    monkeypatch.setattr(api, "forecast_series", lambda sku: {"history": [], "forecast": []})
    monkeypatch.setattr(api, "transactions", lambda **kw: TRANSACTIONS)
    monkeypatch.setattr(api, "review_list", lambda limit=100: REVIEW)
    monkeypatch.setattr(api, "transaction_detail", lambda tx_id: REVIEW_DETAIL)
    monkeypatch.setattr(api, "receipt_image", lambda tx_id: None)
    monkeypatch.setattr(
        api,
        "chat",
        lambda question, lang="id": {
            "answer": f"ANSWER-{lang}",
            "sql": "SELECT 1",
            "rows": [],
            "columns": [],
        },
    )


def _run(view: str, lang: str) -> AppTest:
    at = AppTest.from_file(f"dashboard/views/{view}.py", default_timeout=30)
    at.session_state["lang"] = lang
    return at.run()


@pytest.mark.parametrize("lang", ["id", "en"])
@pytest.mark.parametrize("view", ["overview", "scan", "review", "restock", "ask", "transactions"])
def test_every_view_renders_without_an_exception(view, lang):
    at = _run(view, lang)
    assert not at.exception, [e.value for e in at.exception]


def test_titles_follow_the_language():
    assert "Ringkasan" in _run("overview", "id").title[0].value
    assert "Overview" in _run("overview", "en").title[0].value


def test_restock_shows_the_shelf_life_warning_and_count():
    at = _run("restock", "en")
    metrics = {m.label: m.value for m in at.metric}

    assert metrics["Expiry risk"] == "1"
    assert any("Semen Gresik 50kg" in w.value for w in at.warning)  # risk summary names the product
    assert any("NOTE-TEXT" in w.value for w in at.warning)


def test_scan_page_starts_with_the_upload_source_and_nothing_to_scan():
    at = _run("scan", "id")

    assert not at.exception
    scan_button = next(b for b in at.button if "Scan 0 nota" in b.label)
    assert scan_button.proto.disabled  # nothing chosen yet, so nothing can be sent to the model


def test_review_escapes_text_that_came_from_a_receipt():
    at = _run("review", "en")
    markup = " ".join(m.value for m in at.markdown)

    assert "<b>x</b>" not in markup  # the item name from the receipt must not become HTML
    assert "&lt;b&gt;x&lt;/b&gt;" in markup


def test_ask_page_passes_the_language_to_the_api():
    at = _run("ask", "en")
    at.button[0].click().run()  # the first example question

    assert not at.exception
    assert any("ANSWER-en" in m.value for m in at.markdown)
