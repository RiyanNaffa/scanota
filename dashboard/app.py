"""dashboard/app.py – Streamlit entry point: page setup, navigation and the sidebar.

Pages live in dashboard/views/. They are registered with st.navigation (not the pages/ folder) so
titles and icons can follow the language chosen in the sidebar.
"""

from __future__ import annotations

import streamlit as st

# set_page_config must be the first Streamlit call
st.set_page_config(
    page_title="scanota",
    page_icon=":material/receipt_long:",
    layout="wide",
    initial_sidebar_state="expanded",
)

import dashboard.api_client as api  # noqa: E402
from dashboard.i18n import language_switch, t  # noqa: E402
from dashboard.theme import ICON, inject_css, status_dot  # noqa: E402

inject_css()

pages = [
    st.Page("views/overview.py", title=t("nav.overview"), icon=ICON["overview"], default=True),
    st.Page("views/scan.py", title=t("nav.scan"), icon=ICON["scan"], url_path="scan"),
    st.Page("views/review.py", title=t("nav.review"), icon=ICON["review"], url_path="review"),
    st.Page("views/restock.py", title=t("nav.restock"), icon=ICON["restock"], url_path="restock"),
    st.Page("views/ask.py", title=t("nav.ask"), icon=ICON["ask"], url_path="ask"),
    st.Page(
        "views/transactions.py",
        title=t("nav.transactions"),
        icon=ICON["transactions"],
        url_path="transactions",
    ),
]
current = st.navigation(pages, position="hidden")

with st.sidebar:
    for i, page in enumerate(pages):
        with st.container(key=f"nav_{i}"):
            st.page_link(page, icon=page.icon)
        if page.title == current.title:  # Streamlit gives the active link no attribute to style
            st.markdown(
                f"<style>.st-key-nav_{i} [data-testid='stPageLink-NavLink'] {{"
                "background: rgba(167, 209, 41, 0.14); box-shadow: inset 0 0 0 1px rgba(97, 111, 57, 0.55);"
                "}</style>",
                unsafe_allow_html=True,
            )
    st.write("")
    with st.container(border=True, key="lang_card"):
        language_switch()
    health = api.health()
    online = isinstance(health, dict) and health.get("status") == "ok"
    st.markdown(
        status_dot(online, t("sidebar.api_online" if online else "sidebar.api_offline")),
        unsafe_allow_html=True,
    )

current.run()
