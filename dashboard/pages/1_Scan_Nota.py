"""dashboard/pages/1_Scan_Nota.py – Receipt scanning page."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Scan Nota – scanota", layout="wide")

import dashboard.api_client as api
from dashboard.theme import inject_css, status_badge

inject_css()
st.title("📸 Scan Nota")

st.markdown("Upload foto nota/kwitansi untuk diekstrak secara otomatis.")

uploaded = st.file_uploader(
    "Pilih gambar nota (JPEG / PNG / WebP)",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if uploaded:
    for uf in uploaded:
        st.markdown(f"**{uf.name}**")
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(uf, width=300)
        with col2:
            with st.spinner("Mengekstrak..."):
                result = api.ingest_receipt(
                    uf.read(), uf.name, uf.type or "image/jpeg"
                )
            if isinstance(result, dict) and "error" not in result:
                badge = status_badge(result.get("status", ""))
                st.markdown(f"Status: {badge}", unsafe_allow_html=True)
                conf = result.get("confidence", 0)
                st.progress(conf, text=f"Kepercayaan: {conf:.0%}")
                issues = result.get("issues", [])
                if issues:
                    with st.expander("Masalah yang ditemukan"):
                        for iss in issues:
                            icon = "🔴" if iss.get("severity") == "hard" else "🟡"
                            st.write(f"{icon} [{iss.get('code')}] {iss.get('message')}")
                else:
                    st.success("Tidak ada masalah ditemukan.")
                tx_id = result.get("id")
                if tx_id:
                    st.caption(f"ID Transaksi: {tx_id}")
            else:
                st.error(
                    result.get("error", "Gagal mengekstrak nota.")
                    if isinstance(result, dict)
                    else "Gagal mengekstrak nota."
                )
        st.divider()
