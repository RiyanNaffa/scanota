"""dashboard/i18n.py – Language state and the sidebar language switch (Streamlit side of strings.py)."""

from __future__ import annotations

import streamlit as st

from dashboard.helpers import flag_data_uri
from dashboard.strings import DEFAULT_LANG, LANGS, translate

_LABELS = {"id": "ID", "en": "EN"}


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
    """Two buttons with a flag each; the active one is highlighted."""
    st.caption(t("sidebar.language"))
    current = get_lang()
    cols = st.columns([1, 2, 1, 2], vertical_alignment="center")
    for slot, lang in zip((0, 2), LANGS, strict=True):
        cols[slot].markdown(
            f'<img class="flag" src="{flag_data_uri(lang)}" alt="{_LABELS[lang]}">',
            unsafe_allow_html=True,
        )
        cols[slot + 1].button(
            _LABELS[lang],
            key=f"lang_{lang}",
            use_container_width=True,
            type="primary" if lang == current else "secondary",
            on_click=_choose,
            args=(lang,),
        )
