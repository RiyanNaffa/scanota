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
    """Run the query now; the written answer is fetched below, after the result is on screen."""
    lang = get_lang()
    with st.spinner(t("ask.spinner")):
        result = api.chat(question, lang, answer=False)
    ok = isinstance(result, dict) and "error" not in result
    state["chat_history"].append(
        {
            "question": question,
            "lang": lang,
            "result": result,
            "answer": None,
            "answer_state": "pending" if ok else "none",  # pending | done | unavailable | none
        }
    )


def _show_answer(slot, answer: str | None) -> None:
    if answer:
        slot.markdown(answer)
    else:
        slot.caption(t("ask.answer_unavailable"))


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

awaiting: list[tuple[dict, object]] = []  # entries whose written answer is still to be fetched
for entry in reversed(state["chat_history"]):
    result = entry["result"]
    with st.container(border=True):
        st.markdown(f"**{entry['question']}**")
        if isinstance(result, dict) and "error" not in result:
            answer_slot = st.container()  # filled last, so the rows and the SQL appear first
            if entry["answer_state"] == "pending":
                awaiting.append((entry, answer_slot))
            elif entry["answer_state"] == "unavailable":
                _show_answer(answer_slot, None)
            else:
                _show_answer(answer_slot, entry["answer"] or t("ask.no_answer"))
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

# The model's wording is the slow part. Everything above is already on screen while it is fetched,
# and if the model is slow or down the page keeps the table and the SQL instead of failing.
for entry, slot in awaiting:
    result = entry["result"]
    with slot, st.spinner(t("ask.answer_loading")):
        reply = api.chat_answer(
            entry["question"], result.get("columns") or [], result.get("rows") or [], entry["lang"]
        )
    answer = reply.get("answer") if isinstance(reply, dict) else None
    entry["answer"] = answer
    entry["answer_state"] = "done" if answer else "unavailable"
    _show_answer(slot, answer)
