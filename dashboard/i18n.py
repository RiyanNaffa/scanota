"""dashboard/i18n.py – Language state and the sidebar language switch (Streamlit side of strings.py)."""

from __future__ import annotations

import streamlit as st

from dashboard.strings import DEFAULT_LANG, LANGS, translate


def get_lang() -> str:
    """Current language: the session choice, else ?lang= from the URL, else Indonesian."""
    lang = st.session_state.get("lang")
    if lang not in LANGS:
        from_url = st.query_params.get("lang")
        lang = from_url if from_url in LANGS else DEFAULT_LANG
        st.session_state["lang"] = lang
    return lang


def _choose(lang: str) -> None:
    st.session_state["lang"] = lang
    st.query_params["lang"] = lang  # keeps the choice across a browser refresh and in bookmarks


def t(key: str, **values: object) -> str:
    return translate(get_lang(), key, **values)


def language_switch() -> None:
    """Two equal buttons, ID and EN. The flag is drawn by CSS inside each button (see theme.py), so
    it is always centred with the label, and the two columns are kept side by side on a phone."""
    st.caption(t("sidebar.language"))
    current = get_lang()
    for column, lang in zip(st.columns(2), LANGS, strict=True):
        column.button(
            lang.upper(),
            key=f"lang_{lang}",
            use_container_width=True,
            type="primary" if lang == current else "secondary",
            on_click=_choose,
            args=(lang,),
        )
