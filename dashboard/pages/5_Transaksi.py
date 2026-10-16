"""dashboard/pages/5_Transaksi.py – Transaction history page."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Transaksi – scanota", layout="wide")

import dashboard.api_client as api
from dashboard.theme import fmt_rupiah, inject_css, status_badge

inject_css()
st.title("📋 Transaksi")

col1, col2, col3, col4 = st.columns(4)
with col1:
    channel = st.selectbox("Channel", ["Semua", "online", "offline"])
with col2:
    status = st.selectbox("Status", ["Semua", "confirmed", "needs_review"])
with col3:
    date_from = st.date_input("Dari", value=None)
with col4:
    date_to = st.date_input("Sampai", value=None)

txs = api.transactions(
    channel=None if channel == "Semua" else channel,
    status=None if status == "Semua" else status,
    date_from=date_from.isoformat() if date_from else None,
    date_to=date_to.isoformat() if date_to else None,
    limit=200,
)

if not isinstance(txs, list):
    st.error("Gagal memuat data transaksi.")
elif not txs:
    st.info("Tidak ada transaksi ditemukan.")
else:
    st.write(f"Menampilkan {len(txs)} transaksi")
    import pandas as pd
    df = pd.DataFrame([
        {
            "ID": t["id"],
            "Tanggal": t.get("tx_date"),
            "Channel": t.get("channel"),
            "Sumber": t.get("source"),
            "Pelanggan": t.get("customer") or "-",
            "Total": fmt_rupiah(t.get("total")),
            "Status": t.get("status"),
            "Kepercayaan": f"{float(t.get('confidence', 0)):.0%}",
        }
        for t in txs
    ])
    st.dataframe(df, use_container_width=True)
