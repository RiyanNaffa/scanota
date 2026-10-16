"""dashboard/pages/4_Tanya_Data.py – Chat with data page."""
from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Tanya Data – scanota", layout="wide")

import dashboard.api_client as api
from dashboard.theme import inject_css

inject_css()
st.title("💬 Tanya Data")
st.markdown("Ajukan pertanyaan dalam bahasa Indonesia tentang data penjualan.")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.form("chat_form", clear_on_submit=True):
    question = st.text_input("Pertanyaan Anda:", placeholder="Contoh: Produk apa yang paling laris bulan ini?")
    submitted = st.form_submit_button("Tanya")

if submitted and question:
    with st.spinner("Sedang mencari jawaban..."):
        result = api.chat(question)
    st.session_state.chat_history.append({"question": question, "result": result})

for entry in reversed(st.session_state.chat_history):
    q = entry["question"]
    r = entry["result"]

    st.markdown(f"**❓ {q}**")
    if isinstance(r, dict) and "error" not in r:
        st.markdown(r.get("answer", "Tidak ada jawaban."))
        if r.get("rows"):
            import pandas as pd
            cols = r.get("columns", [])
            rows = r.get("rows", [])
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df, use_container_width=True)
        with st.expander("Lihat query SQL"):
            st.code(r.get("sql", ""), language="sql")
    else:
        st.error(r.get("error", "Gagal mendapatkan jawaban.") if isinstance(r, dict) else str(r))
    st.divider()
