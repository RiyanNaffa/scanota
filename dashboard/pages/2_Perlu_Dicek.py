"""dashboard/pages/2_Perlu_Dicek.py – Review flagged transactions."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Perlu Dicek – scanota", layout="wide")

import dashboard.api_client as api
from dashboard.theme import fmt_rupiah, inject_css

inject_css()
st.title("⚠️ Perlu Dicek")

items = api.review_list(limit=50)

if not isinstance(items, list) or not items:
    st.info("Tidak ada transaksi yang perlu ditinjau. 🎉")
else:
    st.write(f"{len(items)} transaksi menunggu peninjauan.")

    selected_id = st.selectbox(
        "Pilih transaksi:",
        options=[t["id"] for t in items],
        format_func=lambda tid: next(
            (f"#{t['id']} | {t.get('tx_date','')} | {t.get('channel','')} | {fmt_rupiah(t.get('total'))}"
             for t in items if t["id"] == tid),
            str(tid),
        ),
    )

    if selected_id:
        tx = api.transaction_detail(selected_id)
        if isinstance(tx, dict) and "error" not in tx:
            col1, col2 = st.columns([1, 2])
            with col1:
                img_path = tx.get("receipt_image_path")
                if img_path:
                    try:
                        import httpx
                        import os
                        r = httpx.get(
                            f"{api.API_BASE_URL}/receipts/{selected_id}/image", timeout=10
                        )
                        if r.status_code == 200:
                            st.image(r.content, caption="Foto Nota", use_column_width=True)
                    except Exception:
                        st.caption("Gambar tidak tersedia.")
                else:
                    st.caption("Tidak ada gambar.")

            with col2:
                st.subheader("Detail Transaksi")
                st.write(f"Tanggal: **{tx.get('tx_date')}**")
                st.write(f"Pelanggan: **{tx.get('customer') or '-'}**")
                st.write(f"Total: **{fmt_rupiah(tx.get('total'))}**")

                issues = tx.get("issues") or []
                if issues:
                    st.warning("Masalah ditemukan:")
                    for iss in (issues if isinstance(issues, list) else []):
                        if isinstance(iss, dict):
                            icon = "🔴" if iss.get("severity") == "hard" else "🟡"
                            st.write(f"{icon} {iss.get('message', iss.get('code', ''))}")

                st.subheader("Item")
                tx_items = tx.get("items", [])
                if tx_items:
                    import pandas as pd
                    df = pd.DataFrame(tx_items)[["item_name_raw", "qty", "unit", "unit_price", "line_total", "sku_id"]]
                    df.columns = ["Nama Item", "Qty", "Satuan", "Harga Satuan", "Total Baris", "SKU"]
                    st.dataframe(df, use_container_width=True)

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("✅ Konfirmasi (tanpa perubahan)", type="primary"):
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
                            st.success("Transaksi dikonfirmasi!")
                            st.rerun()
                        else:
                            st.error(str(result))
                with col_b:
                    if st.button("⏭️ Lewati"):
                        st.info("Dilewati.")
