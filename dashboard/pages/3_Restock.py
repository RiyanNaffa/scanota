"""dashboard/pages/3_Restock.py – Restock recommendations page."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Restock – scanota", layout="wide")

import dashboard.api_client as api
from dashboard.theme import action_badge, fmt_rupiah, inject_css

inject_css()
st.title("📦 Restock")

with st.spinner("Memuat rekomendasi..."):
    items = api.restock()

if not isinstance(items, list):
    st.error("Gagal memuat data restock.")
elif not items:
    st.info("Tidak ada produk yang perlu dipesan minggu ini.")
else:
    # Summary
    order_now = [i for i in items if i.get("action") == "order_now"]
    watch = [i for i in items if i.get("action") == "watch"]
    at_risk = [i for i in items if i.get("shelf_life_risk")]
    m1, m2 = st.columns(2)
    m1.metric("Perlu Dipesan Sekarang", len(order_now))
    m2.metric("Berisiko Kedaluwarsa", len(at_risk))
    if at_risk:
        st.warning(
            "Stok produk berikut diperkirakan tidak habis sebelum masa simpannya berakhir: "
            + ", ".join(i["name"] for i in at_risk[:8])
            + ("..." if len(at_risk) > 8 else "")
            + ". Perkiraan ini dari kecepatan penjualan, bukan dari umur stok sebenarnya."
        )

    import pandas as pd

    df = pd.DataFrame([
        {
            "Produk": i["name"],
            "Kategori": i["category"],
            "Stok": i["current_stock"],
            "Satuan": i["unit"],
            "Perkiraan (2 minggu)": sum(i.get("forecast_next_2_weeks") or [0, 0]),
            "Hari Habis": f"{i['days_until_stockout']:.0f}" if i.get("days_until_stockout") else "∞",
            "Saran Pesan": i.get("suggested_order_qty", 0),
            "Masa Simpan (hari)": i.get("shelf_life_days") or "–",
            "Risiko Kedaluwarsa": {"high": "⚠️ Tinggi", "watch": "👀 Pantau"}.get(
                i.get("shelf_life_risk"), ""
            ),
            "Aksi": i.get("action", "ok"),
            "Alasan": i.get("reason", ""),
            "Model": i.get("model_used", ""),
        }
        for i in items
    ])

    st.dataframe(df.drop(columns=["Aksi", "Alasan", "Model"]), use_container_width=True)

    # Detail expanders
    for item in items[:15]:  # Show top 15
        act = item.get("action", "ok")
        with st.expander(f"{item['name']} — {act.upper()}"):
            st.write(item.get("reason", ""))
            if item.get("shelf_life_note"):
                st.warning(item["shelf_life_note"])
            if item.get("order_capped_by_shelf_life"):
                st.caption("Saran pesan dibatasi agar tidak melebihi yang bisa terjual sebelum masa simpan habis.")
            st.caption(
                f"Model: {item.get('model_used')} | WAPE: {item.get('wape_primary')} | z: {item.get('z')}"
            )

            # Forecast chart
            series = api.forecast_series(item["sku_id"])
            if isinstance(series, dict) and "history" in series:
                hist = pd.DataFrame(series["history"])
                fc = pd.DataFrame(series["forecast"])
                if not hist.empty:
                    hist.index = pd.to_datetime(hist["week"].str.split("/").str[0])
                    st.line_chart(hist.set_index(hist.index)["qty"], height=200)

            # Inline stock edit
            new_stock = st.number_input(
                f"Update stok {item['unit']}",
                value=float(item["current_stock"]),
                min_value=0.0,
                key=f"stock_{item['sku_id']}",
            )
            if st.button("Simpan Stok", key=f"save_{item['sku_id']}"):
                result = api.update_stock(item["sku_id"], new_stock)
                if isinstance(result, dict) and "error" not in result:
                    st.success("Stok diperbarui!")
                else:
                    st.error("Gagal memperbarui stok.")
