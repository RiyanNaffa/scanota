"""dashboard/views/review.py – Check the receipts the system flagged, then confirm them."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import dashboard.api_client as api
from dashboard.helpers import fmt_rupiah
from dashboard.i18n import t
from dashboard.theme import ICON
from dashboard.widgets import render_issues, status_pill

st.title(f"{ICON['review']} {t('review.title')}")
st.caption(t("review.subtitle"))

state = st.session_state
state.setdefault("review_skipped", set())
flash = state.pop("review_flash", None)  # message that must survive the rerun after a confirm
if flash:
    st.success(flash, icon=ICON["check"])

items = api.review_list(limit=50)
if not isinstance(items, list) or not items:
    st.info(t("review.none"), icon=ICON["info"])
    st.stop()

visible = [i for i in items if i["id"] not in state["review_skipped"]]
if not visible:
    st.info(t("review.all_skipped"), icon=ICON["info"])
    st.stop()
st.caption(t("review.waiting", n=len(visible)))


def _label(tx: dict) -> str:
    return (
        f"#{tx['id']} | {tx.get('tx_date', '')} | {tx.get('channel', '')} | "
        f"{fmt_rupiah(tx.get('total'))}"
    )


by_id = {i["id"]: i for i in visible}
selected_id = st.selectbox(
    t("review.select"), options=list(by_id), format_func=lambda tid: _label(by_id[tid])
)

tx = api.transaction_detail(selected_id)
if not isinstance(tx, dict) or "error" in tx:
    st.error(t("common.error"), icon=ICON["error"])
    st.stop()

col_photo, col_detail = st.columns([1, 2])
with col_photo.container(border=True):
    st.markdown(f"**{t('review.photo')}**")
    if tx.get("receipt_image_path"):
        image = api.receipt_image(selected_id)
        if image:
            st.image(image, use_container_width=True)
        else:
            st.caption(t("review.image_unavailable"))
    else:
        st.caption(t("review.no_image"))

with col_detail:
    with st.container(border=True):
        st.markdown(
            f"**{t('review.detail')}**  {status_pill(tx.get('status', 'needs_review'))}",
            unsafe_allow_html=True,
        )
        d1, d2, d3 = st.columns(3)
        d1.metric(t("common.date"), str(tx.get("tx_date") or "-"))
        d2.metric(t("common.customer"), tx.get("customer") or "-")
        d3.metric(t("common.total"), fmt_rupiah(tx.get("total")))

        issues = tx.get("issues") or []
        if isinstance(issues, list) and issues:
            st.markdown(f"**{t('review.issues')}**")
            render_issues([i for i in issues if isinstance(i, dict)])

    tx_items = tx.get("items") or []
    if tx_items:
        st.markdown(f"**{t('review.items')}**")
        df = pd.DataFrame(tx_items)[
            ["item_name_raw", "qty", "unit", "unit_price", "line_total", "sku_id"]
        ]
        df.columns = [
            t("review.col.name"),
            t("review.col.qty"),
            t("common.unit"),
            t("review.col.unit_price"),
            t("review.col.line_total"),
            t("review.col.sku"),
        ]
        st.dataframe(df, hide_index=True, use_container_width=True)

    confirm, skip, _ = st.columns([3, 2, 4])
    if confirm.button(
        t("review.confirm"), type="primary", icon=ICON["check"], use_container_width=True
    ):
        body = {
            "tx_date": tx.get("tx_date"),
            "customer": tx.get("customer"),
            "total": tx.get("total"),
            "items": [
                {
                    "item_name_raw": it.get("item_name_raw"),
                    "sku_id": it.get("sku_id"),
                    "qty": it.get("qty"),
                    "unit": it.get("unit"),
                    "unit_price": it.get("unit_price"),
                    "line_total": it.get("line_total"),
                }
                for it in tx_items
            ],
            "save_aliases": True,
            "force": True,
        }
        result = api.confirm_transaction(selected_id, body)
        if isinstance(result, dict) and "error" not in result:
            state["review_flash"] = t("review.confirmed")
            st.rerun()
        else:
            st.error(str(result), icon=ICON["error"])
    if skip.button(t("review.skip"), icon=ICON["skip"], use_container_width=True):
        state["review_skipped"].add(selected_id)
        st.rerun()
