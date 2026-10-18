"""dashboard/views/transactions.py – Transaction history."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import dashboard.api_client as api
from dashboard.i18n import t
from dashboard.theme import ICON

st.title(f"{ICON['transactions']} {t('tx.title')}")
st.caption(t("tx.subtitle"))

ALL = "__all__"
c1, c2, c3, c4 = st.columns(4)
channel = c1.selectbox(
    t("common.channel"),
    [ALL, "online", "offline"],
    format_func=lambda v: t("common.all") if v == ALL else t(f"channel.{v}"),
)
status = c2.selectbox(
    t("common.status"),
    [ALL, "confirmed", "needs_review"],
    format_func=lambda v: t("common.all") if v == ALL else t(f"status.{v}"),
)
date_from = c3.date_input(t("common.from"), value=None)
date_to = c4.date_input(t("common.to"), value=None)

with st.spinner(t("tx.loading")):
    rows = api.transactions(
        channel=None if channel == ALL else channel,
        status=None if status == ALL else status,
        date_from=date_from.isoformat() if date_from else None,
        date_to=date_to.isoformat() if date_to else None,
        limit=200,
    )

if not isinstance(rows, list):
    st.error(t("tx.load_error"), icon=ICON["error"])
    st.stop()
if not rows:
    st.info(t("tx.none"), icon=ICON["info"])
    st.stop()

st.caption(t("tx.showing", n=len(rows)))
table = pd.DataFrame(
    [
        {
            t("tx.col.id"): r["id"],
            t("common.date"): r.get("tx_date"),
            t("common.channel"): t(f"channel.{r['channel']}") if r.get("channel") else "-",
            t("tx.col.source"): r.get("source"),
            t("common.customer"): r.get("customer") or "-",
            t("common.total"): r.get("total"),
            t("common.status"): t(f"status.{r['status']}") if r.get("status") else "-",
            t("tx.col.confidence"): float(r.get("confidence") or 0),
        }
        for r in rows
    ]
)
st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
    column_config={
        t("common.total"): st.column_config.NumberColumn(format="Rp %d"),
        t("tx.col.confidence"): st.column_config.ProgressColumn(
            min_value=0.0, max_value=1.0, format="percent"
        ),
    },
)
