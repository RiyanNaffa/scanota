"""dashboard/widgets.py – Pieces shared by several pages (issue list, status pill)."""

from __future__ import annotations

import html

import streamlit as st

import dashboard.api_client as api
from dashboard.i18n import t
from dashboard.strings import STRINGS
from dashboard.theme import pill


@st.cache_data(ttl=60, show_spinner=False)
def _restock(lang: str) -> list:
    data = api.restock(lang=lang)
    if not isinstance(data, list):
        raise RuntimeError("restock request failed")  # an exception is never cached
    return data


def restock_cached(lang: str) -> list | dict:
    """The restock list, kept for a minute. It takes seconds to compute and both the overview and
    the restock page need it. Errors are not cached: they come back as {"error": ...}."""
    try:
        return _restock(lang)
    except RuntimeError:
        return {"error": "restock request failed"}


@st.cache_data(ttl=10, show_spinner=False)
def api_online() -> bool:
    """Is the API reachable? Kept for 10 s so navigating between pages does not re-check each time."""
    health = api.health()
    return isinstance(health, dict) and health.get("status") == "ok"


def clear_restock_cache() -> None:
    """Call after anything that changes stock or sales, so the next view recomputes."""
    _restock.clear()


def status_pill(status: str) -> str:
    return pill("good" if status == "confirmed" else "warn", t(f"status.{status}"))


def render_issues(issues: list[dict]) -> None:
    """Validation issues: a coloured, translated label plus the engine's own detail line.

    The detail comes from the API in English and can contain text read from a receipt, so it is
    HTML-escaped before it is placed in markup.
    """
    for issue in issues:
        code = issue.get("code", "")
        label = t(f"issue.{code}") if f"issue.{code}" in STRINGS["id"] else code
        kind = "bad" if issue.get("severity") == "hard" else "warn"
        detail = html.escape(str(issue.get("message", "")))
        st.markdown(
            f'<div class="issue">{pill(kind, html.escape(label))}<small>{detail}</small></div>',
            unsafe_allow_html=True,
        )
