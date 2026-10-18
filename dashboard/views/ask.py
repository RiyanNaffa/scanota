"""dashboard/views/ask.py – Ask questions about the sales data (read-only text-to-SQL)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

import dashboard.api_client as api
from dashboard.i18n import get_lang, t
from dashboard.theme import ICON

st.title(f"{ICON['ask']} {t('ask.title')}")
st.caption(t("ask.subtitle"))

state = st.session_state
state.setdefault("chat_history", [])


def _ask(question: str) -> None:
    with st.spinner(t("ask.spinner")):
        result = api.chat(question, get_lang())
    state["chat_history"].append({"question": question, "result": result})


st.caption(t("ask.examples"))
examples = [t("ask.example.1"), t("ask.example.2"), t("ask.example.3")]
for col, example in zip(st.columns(3), examples, strict=True):
    if col.button(example, key=f"example_{example}", use_container_width=True):
        _ask(example)

with st.form("chat_form", clear_on_submit=True):
    question = st.text_input(t("ask.input"), placeholder=t("ask.placeholder"))
    submitted = st.form_submit_button(t("ask.submit"), type="primary", icon=ICON["send"])
if submitted and question.strip():
    _ask(question.strip())

for entry in reversed(state["chat_history"]):
    result = entry["result"]
    with st.container(border=True):
        st.markdown(f"**{entry['question']}**")
        if isinstance(result, dict) and "error" not in result:
            st.markdown(result.get("answer") or t("ask.no_answer"))
            if result.get("rows"):
                st.dataframe(
                    pd.DataFrame(result["rows"], columns=result.get("columns") or None),
                    hide_index=True,
                    use_container_width=True,
                )
            with st.expander(f"{ICON['sql']} {t('ask.sql')}"):
                st.code(result.get("sql", ""), language="sql")
        else:
            message = result.get("error") if isinstance(result, dict) else str(result)
            st.error(message or t("ask.failed"), icon=ICON["error"])
