"""tests/unit/test_dashboard_views.py – Every dashboard page renders, in both languages.

Needs Streamlit (the dashboard image has it; the API's CI install does not), so it is skipped
where Streamlit is missing. The API client is replaced by canned data: no network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

st = pytest.importorskip("streamlit")
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
    st.cache_data.clear()  # restock_cached keeps results for a minute; start every test clean
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
        lambda question, lang="id", answer=True: {
            "answer": f"ANSWER-{lang}" if answer else None,
            "sql": "SELECT 1",
            "rows": [[1]],
            "columns": ["n"],
        },
    )
    monkeypatch.setattr(
        api, "chat_answer", lambda question, columns, rows, lang="id": {"answer": f"ANSWER-{lang}"}
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


def test_ask_shows_the_query_result_before_it_asks_for_the_wording(monkeypatch):
    calls: list[str] = []

    def chat(question, lang="id", answer=True):
        calls.append(f"chat(answer={answer})")
        return {"answer": None, "sql": "SELECT 1", "rows": [[1]], "columns": ["n"]}

    def chat_answer(question, columns, rows, lang="id"):
        calls.append("chat_answer")
        return {"answer": "THE-WORDING"}

    monkeypatch.setattr(api, "chat", chat)
    monkeypatch.setattr(api, "chat_answer", chat_answer)
    at = _run("ask", "en")
    at.button[0].click().run()

    assert not at.exception
    assert calls == ["chat(answer=False)", "chat_answer"]  # the rows first, the wording second
    assert any("THE-WORDING" in m.value for m in at.markdown)
    assert at.code[0].value == "SELECT 1"


@pytest.mark.parametrize("reply", [{"answer": None}, {"error": "timed out"}])
def test_ask_keeps_the_table_and_sql_when_the_wording_is_unavailable(monkeypatch, reply):
    monkeypatch.setattr(api, "chat_answer", lambda question, columns, rows, lang="id": reply)
    at = _run("ask", "en")
    at.button[0].click().run()

    assert not at.exception
    assert at.code[0].value == "SELECT 1"  # the query is shown
    assert len(at.dataframe) == 1  # and so are the rows
    assert any("not available" in c.value for c in at.caption)  # with a note instead of an error
    assert not at.error


def test_ask_does_not_ask_for_the_wording_twice(monkeypatch):
    wordings: list[int] = []

    def chat_answer(question, columns, rows, lang="id"):
        wordings.append(1)
        return {"answer": "W"}

    monkeypatch.setattr(api, "chat_answer", chat_answer)
    at = _run("ask", "en")
    at.button[0].click().run()
    at.run()  # any later rerun of the page

    assert len(wordings) == 1


def test_restock_is_cached_for_a_minute_and_errors_are_not(monkeypatch):
    from dashboard.widgets import clear_restock_cache, restock_cached

    monkeypatch.setattr(api, "restock", lambda explain=None, lang="id": {"error": "down"})
    assert "error" in restock_cached("id")  # an outage is reported ...

    monkeypatch.setattr(api, "restock", lambda explain=None, lang="id": ["first"])
    assert restock_cached("id") == ["first"]  # ... and not remembered once the API is back

    monkeypatch.setattr(api, "restock", lambda explain=None, lang="id": ["second"])
    assert restock_cached("id") == ["first"]  # served from the cache
    clear_restock_cache()
    assert restock_cached("id") == ["second"]  # recomputed after a stock or sales change


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("app.py", "common.loading"),
        ("views/overview.py", "overview.loading"),
        ("views/scan.py", "scan.running"),
        ("views/review.py", "review.loading"),
        ("views/review.py", "review.loading_detail"),
        ("views/review.py", "review.saving"),
        ("views/restock.py", "restock.loading"),
        ("views/ask.py", "ask.spinner"),
        ("views/transactions.py", "tx.loading"),
    ],
)
def test_every_page_shows_a_loading_message_while_it_waits(path, message):
    """A spinner is too short-lived to catch in a test, so check it is wired into the page."""
    source = Path(f"dashboard/{path}").read_text(encoding="utf-8")

    assert "st.spinner" in source
    assert f't("{message}"' in source
