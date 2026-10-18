"""dashboard/widgets.py – Pieces shared by several pages (issue list, status pill)."""

from __future__ import annotations

import html

import streamlit as st

from dashboard.i18n import t
from dashboard.strings import STRINGS
from dashboard.theme import pill


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
