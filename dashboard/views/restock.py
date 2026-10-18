"""dashboard/views/restock.py – What to reorder, and which stock may outlast its shelf life."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import dashboard.api_client as api
from dashboard.i18n import get_lang, t
from dashboard.theme import ICON, pill
from dashboard.widgets import clear_restock_cache, restock_cached

st.title(f"{ICON['restock']} {t('restock.title')}")
st.caption(t("restock.subtitle"))

if flash := st.session_state.pop("restock_flash", None):
    st.success(flash, icon=ICON["check"])

with st.spinner(t("restock.loading")):
    items = restock_cached(get_lang())
if not isinstance(items, list):
    st.error(t("restock.load_error"), icon=ICON["error"])
    st.stop()
if not items:
    st.info(t("restock.none"), icon=ICON["info"])
    st.stop()

order_now = [i for i in items if i.get("action") == "order_now"]
at_risk = [i for i in items if i.get("shelf_life_risk")]

m1, m2 = st.columns(2)
m1.metric(t("restock.need_order"), len(order_now))
m2.metric(t("restock.at_risk"), len(at_risk))
if at_risk:
    names = ", ".join(i["name"] for i in at_risk[:8]) + ("..." if len(at_risk) > 8 else "")
    st.warning(t("restock.risk_warning", names=names), icon=ICON["warning"])

risk_text = {"high": t("restock.risk.high"), "watch": t("restock.risk.watch")}


def action_text(action: str) -> str:
    return t(f"action.{action}")


table = pd.DataFrame(
    [
        {
            t("common.product"): i["name"],
            t("common.category"): i["category"],
            t("common.stock"): i["current_stock"],
            t("common.unit"): i["unit"],
            t("restock.col.forecast"): sum(i.get("forecast_next_2_weeks") or [0, 0]),
            t("restock.col.days_left"): i.get("days_until_stockout"),
            t("restock.col.order"): i.get("suggested_order_qty", 0),
            t("restock.col.action"): t(f"action.{i.get('action', 'ok')}"),
            t("restock.col.shelf"): str(i["shelf_life_days"]) if i.get("shelf_life_days") else "–",
            t("restock.col.risk"): risk_text.get(i.get("shelf_life_risk"), ""),
        }
        for i in items
    ]
)
st.dataframe(
    table,
    hide_index=True,
    use_container_width=True,
    column_config={
        t("restock.col.forecast"): st.column_config.NumberColumn(format="%.1f"),
        t("restock.col.days_left"): st.column_config.NumberColumn(format="%d"),
    },
)

# ---- one product in detail ----
st.subheader(t("restock.details"))
by_sku = {i["sku_id"]: i for i in items}
sku = st.selectbox(
    t("restock.pick"),
    options=list(by_sku),
    format_func=lambda s: f"{by_sku[s]['name']} - {action_text(by_sku[s].get('action', 'ok'))}",
)
item = by_sku[sku]

left, right = st.columns([3, 2])
with left.container(border=True):
    kind = {"order_now": "bad", "watch": "warn"}.get(item.get("action"), "good")
    st.markdown(pill(kind, t(f"action.{item.get('action', 'ok')}")), unsafe_allow_html=True)
    st.write(item.get("reason", ""))
    if item.get("shelf_life_note"):
        st.warning(item["shelf_life_note"], icon=ICON["warning"])
    if item.get("order_capped_by_shelf_life"):
        st.caption(t("restock.capped"))
    st.caption(
        t(
            "restock.model",
            model=item.get("model_used"),
            wape="-" if item.get("wape_primary") is None else f"{item['wape_primary']:.2f}",
            z=item.get("z"),
        )
    )

    new_stock = st.number_input(
        t("restock.update_stock", unit=item["unit"]),
        value=float(item["current_stock"]),
        min_value=0.0,
        key=f"stock_{sku}",
    )
    if st.button(t("restock.save"), icon=ICON["save"], key=f"save_{sku}"):
        result = api.update_stock(sku, new_stock)
        if isinstance(result, dict) and "error" not in result:
            clear_restock_cache()  # the forecast and the table must see the new stock
            st.session_state["restock_flash"] = t("restock.saved")
            st.rerun()
        else:
            st.error(t("restock.save_failed"), icon=ICON["error"])

series = api.forecast_series(sku)
if isinstance(series, dict) and series.get("history"):

    def _week_start(label: str) -> pd.Timestamp:
        return pd.Timestamp(str(label).split("/")[0])

    history = pd.DataFrame(series["history"]).tail(52)
    history["week"] = history["week"].map(_week_start)
    forecast = pd.DataFrame(series.get("forecast") or [])
    frames = [history.set_index("week")["qty"].rename(t("restock.chart.actual"))]
    if not forecast.empty:
        forecast["week"] = forecast["week"].map(_week_start)
        frames.append(forecast.set_index("week")["qty"].rename(t("restock.chart.forecast")))
    with right.container(border=True):
        st.markdown(f"**{t('restock.chart.title')}**")
        st.line_chart(
            pd.concat(frames, axis=1), color=["#a7d129", "#d9a441"][: len(frames)], height=280
        )
