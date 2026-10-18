"""dashboard/views/scan.py – Scan receipts from uploaded files or the device camera.

Both inputs read from the visitor's own device through the browser: nothing is taken from the
server's file system. The camera widget is only created once "Camera" is chosen, so the browser
does not ask for camera permission on visitors who just upload. Each image is scanned once:
finished scans are kept by image hash, so a rerun caused by anything else, such as switching
language, never sends a receipt to the model again.
"""

from __future__ import annotations

import streamlit as st

import dashboard.api_client as api
from dashboard.helpers import MAX_UPLOAD_MB, build_queue
from dashboard.i18n import t
from dashboard.theme import ICON, pill
from dashboard.widgets import clear_restock_cache, render_issues, status_pill

st.title(f"{ICON['scan']} {t('scan.title')}")
st.caption(t("scan.subtitle"))

state = st.session_state
state.setdefault("scan_nonce", 0)  # bumping it gives the widgets new keys, which empties them
state.setdefault("scan_done", {})  # image hash -> {"name", "data", "result"}
nonce = state["scan_nonce"]

SOURCES = {
    "upload": f"{ICON['upload']} {t('scan.tab.upload')}",
    "camera": f"{ICON['scan']} {t('scan.tab.camera')}",
}
source = (
    st.segmented_control(
        t("scan.source"),
        options=list(SOURCES),
        default="upload",
        format_func=SOURCES.get,
        label_visibility="collapsed",
        key="scan_source",
    )
    or "upload"
)

chosen: list[dict] = []
if source == "upload":
    uploads = st.file_uploader(
        t("scan.upload.label"),
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key=f"upload_{nonce}",
    )
    st.caption(t("scan.upload.note", mb=MAX_UPLOAD_MB))
    chosen = [{"name": u.name, "data": u.getvalue(), "type": u.type} for u in uploads or []]
else:
    photo = st.camera_input(t("scan.camera.label"), key=f"camera_{nonce}")
    st.caption(t("scan.camera.note"))
    if photo is not None:
        chosen = [{"name": "camera.jpg", "data": photo.getvalue(), "type": "image/jpeg"}]

# Not yet scanned, one entry per distinct image
queue = build_queue(chosen, state["scan_done"])

with st.container(key="actions_scan"):
    button_scan, button_clear = st.columns(2)
if button_scan.button(
    t("scan.button", n=len(queue)),
    type="primary",
    icon=ICON["scan"],
    disabled=not queue,
    use_container_width=True,
):
    for item in queue:
        with st.spinner(t("scan.running", name=item["name"])):
            result = api.ingest_receipt(item["data"], item["name"], item["type"] or "image/jpeg")
        state["scan_done"][item["key"]] = {
            "name": item["name"],
            "data": item["data"],
            "result": result,
        }
    queue = []
    clear_restock_cache()  # new sales change the forecast
if button_clear.button(
    t("scan.clear"),
    icon=ICON["clear"],
    disabled=not (chosen or state["scan_done"]),
    use_container_width=True,
):
    state["scan_nonce"] += 1
    state["scan_done"] = {}
    st.rerun()

if queue:
    st.subheader(t("scan.queue"))
    for item in queue:
        with st.container(border=True):
            col_image, col_body = st.columns([1, 4])
            col_image.image(item["data"], use_container_width=True)
            col_body.markdown(f"**{item['name']}**")
            col_body.markdown(pill("mute", t("scan.pending")), unsafe_allow_html=True)
elif not state["scan_done"]:
    st.info(t("scan.none_pending"), icon=ICON["info"])

if state["scan_done"]:
    st.subheader(t("scan.results"))
    for entry in reversed(list(state["scan_done"].values())):
        result = entry["result"]
        with st.container(border=True):
            col_image, col_body = st.columns([1, 3])
            col_image.image(entry["data"], use_container_width=True)
            with col_body:
                st.markdown(f"**{entry['name']}**")
                if not isinstance(result, dict) or "error" in result:
                    message = result.get("error") if isinstance(result, dict) else None
                    st.error(message or t("scan.failed"), icon=ICON["error"])
                    continue
                st.markdown(status_pill(result.get("status", "")), unsafe_allow_html=True)
                confidence = float(result.get("confidence") or 0)
                st.progress(confidence, text=t("scan.confidence", pct=f"{confidence:.0%}"))
                issues = result.get("issues") or []
                if issues:
                    st.markdown(f"**{t('scan.issues')}**")
                    render_issues(issues)
                else:
                    st.caption(f"{ICON['check']} {t('scan.no_issues')}")
                if result.get("status") == "needs_review":
                    st.caption(t("scan.to_review"))
                st.caption(t("scan.tx_id", id=result.get("id")))
