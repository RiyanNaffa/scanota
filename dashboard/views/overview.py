"""dashboard/views/overview.py – Sales overview."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import dashboard.api_client as api
from dashboard.helpers import fmt_rupiah
from dashboard.i18n import get_lang, t
from dashboard.theme import ICON

st.title(f"{ICON['overview']} {t('overview.title')}")
st.caption(t("overview.subtitle"))

col_from, col_to = st.columns(2)
date_from = col_from.date_input(t("common.from"), value=None)
date_to = col_to.date_input(t("common.to"), value=None)

data = api.summary(
    date_from=date_from.isoformat() if date_from else None,
    date_to=date_to.isoformat() if date_to else None,
)

if not isinstance(data, dict) or "error" in data:
    st.warning(t("overview.load_error"))
    if isinstance(data, dict):
        st.error(data.get("error", t("common.error")))
    st.stop()

k1, k2, k3, k4 = st.columns(4)
k1.metric(t("overview.kpi.sales"), fmt_rupiah(data.get("total_sales", 0)))
k2.metric(t("overview.kpi.online"), data.get("online_count", 0))
k3.metric(t("overview.kpi.offline"), data.get("offline_count", 0))
k4.metric(t("overview.kpi.review"), data.get("needs_review_count", 0))

left, right = st.columns([3, 2])

daily = data.get("daily_series") or []
if daily:
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot_table(index="date", columns="channel", values="total", fill_value=0)
    with left.container(border=True):
        st.subheader(t("overview.daily"))
        st.line_chart(pivot, color=["#a7d129", "#616f39"][: len(pivot.columns)], height=300)

top = data.get("top_products") or []
if top:
    df_top = pd.DataFrame(top).rename(
        columns={"name": t("common.product"), "revenue": t("overview.top.revenue")}
    )
    with right.container(border=True):
        st.subheader(t("overview.top"))
        st.dataframe(
            df_top,
            hide_index=True,
            use_container_width=True,
            height=300,
            column_config={
                t("overview.top.revenue"): st.column_config.NumberColumn(format="Rp %d"),
            },
        )

restock = api.restock(lang=get_lang())
if isinstance(restock, list) and restock:
    st.subheader(f"{ICON['restock']} {t('overview.restock')}")
    cols = st.columns(3)
    for col, item in zip(cols, restock[:3], strict=False):
        with col.container(border=True):
            st.markdown(f"**{item['name']}**")
            st.caption(item.get("reason", "-"))
