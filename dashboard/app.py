"""dashboard/app.py – Streamlit entry point (Ringkasan / Dashboard)."""
from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="scanota",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard.theme import fmt_rupiah, inject_css  # noqa: E402

inject_css()

import dashboard.api_client as api  # noqa: E402

st.sidebar.title("📦 scanota")
st.sidebar.markdown("---")

# Health indicator
h = api.health()
if isinstance(h, dict) and h.get("status") == "ok":
    st.sidebar.success("API: Online")
else:
    st.sidebar.error("API: Tidak terhubung")

st.sidebar.markdown(
    """
**Navigasi:**
- 📊 Ringkasan (halaman ini)
- 📸 Scan Nota → halaman terpisah
- ⚠️ Perlu Dicek → halaman terpisah
- 📦 Restock → halaman terpisah
- 💬 Tanya Data → halaman terpisah
- 📋 Transaksi → halaman terpisah
"""
)

# ---- Date filters ----
st.title("📊 Ringkasan")
col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("Dari tanggal", value=None)
with col2:
    date_to = st.date_input("Sampai tanggal", value=None)

data = api.summary(
    date_from=date_from.isoformat() if date_from else None,
    date_to=date_to.isoformat() if date_to else None,
)

if isinstance(data, dict) and "error" not in data:
    # KPI cards
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Penjualan", fmt_rupiah(data.get("total_sales", 0)))
    k2.metric("Transaksi Online", str(data.get("online_count", 0)))
    k3.metric("Transaksi Offline", str(data.get("offline_count", 0)))
    k4.metric("Perlu Dicek", str(data.get("needs_review_count", 0)))

    # Daily sales chart
    daily = data.get("daily_series", [])
    if daily:
        import pandas as pd
        df = pd.DataFrame(daily)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            pivot = df.pivot_table(index="date", columns="channel", values="total", fill_value=0)
            st.subheader("Penjualan Harian per Channel")
            st.line_chart(pivot)

    # Top products
    top = data.get("top_products", [])
    if top:
        import pandas as pd
        st.subheader("Produk Terlaris")
        df_top = pd.DataFrame(top)
        df_top["revenue"] = df_top["revenue"].apply(fmt_rupiah)
        st.dataframe(df_top.rename(columns={"name": "Produk", "revenue": "Pendapatan"}), use_container_width=True)

    # Restock top 3
    restock = api.restock()
    if isinstance(restock, list) and restock:
        st.subheader("⚠️ Restock Minggu Ini (Top 3)")
        for item in restock[:3]:
            st.markdown(
                f'<div class="scanota-card"><b>{item["name"]}</b> — '
                f'{item.get("reason", "-")}</div>',
                unsafe_allow_html=True,
            )
else:
    st.warning(
        "Tidak dapat memuat data ringkasan. "
        "Pastikan API berjalan dan data sudah di-seed."
    )
    if isinstance(data, dict):
        st.error(data.get("error", "Unknown error"))
