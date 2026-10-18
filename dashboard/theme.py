"""dashboard/theme.py – Dark theme in the scanota palette (CSS only, no animations).

Palette: #000000 background, #3e432e surface, #616f39 border and secondary, #a7d129 accent.
Two extra colours exist only for meaning: amber for "watch" and red for "act now".
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

PALETTE = {
    "black": "#000000",
    "surface": "#3e432e",
    "olive": "#616f39",
    "lime": "#a7d129",
    "text": "#f1f5e4",
    "muted": "#b7bf9a",
    "warn": "#d9a441",
    "bad": "#e5675a",
}

# Material Symbols used by the pages (Streamlit renders the :material/name: shortcode)
ICON = {
    "overview": ":material/dashboard:",
    "scan": ":material/photo_camera:",
    "review": ":material/fact_check:",
    "restock": ":material/inventory_2:",
    "ask": ":material/chat:",
    "transactions": ":material/receipt_long:",
    "upload": ":material/upload_file:",
    "check": ":material/check_circle:",
    "warning": ":material/warning:",
    "error": ":material/error:",
    "info": ":material/info:",
    "clear": ":material/restart_alt:",
    "skip": ":material/skip_next:",
    "save": ":material/save:",
    "send": ":material/send:",
    "sql": ":material/code:",
}

_CSS = """
<style>
:root {
  --bg: __black__; --surface: __surface__; --olive: __olive__; --lime: __lime__;
  --text: __text__; --muted: __muted__; --warn: __warn__; --bad: __bad__;
  --line: rgba(97, 111, 57, 0.55); --card: rgba(62, 67, 46, 0.40);
}
.stApp { background: var(--bg); }
.block-container { padding-top: 2.2rem; max-width: 1280px; }

/* Streamlit chrome: no Deploy button (the app is hosted on a VM) */
.stAppDeployButton, [data-testid="stAppDeployButton"], .stDeployButton { display: none !important; }

/* Sidebar: same black as the page, a hairline border instead of a second fill */
section[data-testid="stSidebar"] { background: var(--bg); border-right: 1px solid var(--line); }
/* Brand in the sidebar header, left of the collapse button. It is drawn here, not with
   st.logo, because st.logo puts a second copy in the page header that overlaps the sidebar. */
[data-testid="stSidebarHeader"] { display: flex; align-items: center; justify-content: space-between; }
[data-testid="stSidebarHeader"]::before {
  content: ""; flex: 0 0 150px; height: 34px; margin-left: 4px;
  background: url("__LOGO__") no-repeat left center / contain;
}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {
  border-radius: 8px; padding: 0.45rem 0.7rem; margin: 0.1rem 0;
}
section[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover { background: rgba(97, 111, 57, 0.28); }
section[data-testid="stSidebar"] img.flag {
  width: 26px; height: auto; display: block; border-radius: 3px; margin: 0 auto;
  box-shadow: 0 0 0 1px rgba(241, 245, 228, 0.25);
}
/* The language card: a bordered, padded, rounded box with the sidebar's own background */
.st-key-lang_card { padding: 14px 14px 10px; border-radius: 12px; background: transparent; }

/* Headings */
h1 { font-weight: 700; letter-spacing: -0.01em; }
h1 span, h2 span, h3 span { vertical-align: middle; }
[data-testid="stCaptionContainer"] { color: var(--muted); }

/* Bordered containers: olive hairline and rounded corners, no fill. A fill made the page and the
   sidebar look like square patches, because Streamlit wraps every block in this element. */
[data-testid="stVerticalBlockBorderWrapper"] { border-color: var(--line) !important; border-radius: 10px; }
/* Metrics are their own padded, rounded cards */
[data-testid="stMetric"] {
  background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
}
[data-testid="stMetricValue"] { color: var(--lime); font-size: clamp(1.2rem, 2.1vw, 1.8rem); }
[data-testid="stMetricValue"] > div { white-space: normal; overflow-wrap: anywhere; text-overflow: clip; }
[data-testid="stMetricLabel"] { color: var(--muted); }

/* Buttons */
.stButton > button, .stDownloadButton > button {
  border-radius: 8px; border: 1px solid var(--olive); background: transparent;
}
.stButton > button:hover { border-color: var(--lime); color: var(--lime); }
.stButton > button[kind="primary"] {
  background: var(--lime); color: #000000; border-color: var(--lime); font-weight: 600;
}
.stButton > button[kind="primary"]:hover { filter: brightness(1.08); color: #000000; }
.stButton > button:disabled { opacity: 0.45; }
[data-testid^="stBaseButton-segmented_control"] { border-radius: 8px !important; }

/* Inputs, tables, progress */
[data-testid="stFileUploaderDropzone"] { border: 1px dashed var(--olive); border-radius: 10px; }
[data-testid="stCameraInput"] > div { border-radius: 10px; overflow: hidden; }
[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
[data-testid="stProgress"] > div > div > div { background-color: var(--lime); }

/* Alerts in the palette instead of the default blue, green, yellow and red */
[data-testid="stAlertContainer"] { border-radius: 10px; border: 1px solid var(--line); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) { background: rgba(97, 111, 57, 0.22); }
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
  background: rgba(167, 209, 41, 0.12); border-color: var(--lime);
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
  background: rgba(217, 164, 65, 0.12); border-color: var(--warn);
}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
  background: rgba(229, 103, 90, 0.12); border-color: var(--bad);
}

/* Status pills */
.pill {
  display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 0.78rem;
  font-weight: 600; border: 1px solid; white-space: nowrap;
}
.pill-good { color: var(--lime); border-color: var(--lime); background: rgba(167, 209, 41, 0.12); }
.pill-warn { color: var(--warn); border-color: var(--warn); background: rgba(217, 164, 65, 0.12); }
.pill-bad  { color: var(--bad);  border-color: var(--bad);  background: rgba(229, 103, 90, 0.12); }
.pill-mute { color: var(--muted); border-color: var(--olive); background: rgba(97, 111, 57, 0.15); }

/* API status, with room above it */
.status-line {
  display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 0.85rem;
  margin-top: 1.25rem; padding-left: 4px;
}
.status-dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.issue { display: flex; gap: 8px; align-items: baseline; margin: 4px 0; }
.issue small { color: var(--muted); }
</style>
"""


def _logo_data_uri() -> str:
    svg = (Path(__file__).parent / "assets" / "logo.svg").read_bytes()
    return "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")


def inject_css() -> None:
    css = _CSS.replace("__LOGO__", _logo_data_uri())
    for name, value in PALETTE.items():
        css = css.replace(f"__{name}__", value)
    st.markdown(css, unsafe_allow_html=True)


_PILL = {"good": "pill-good", "warn": "pill-warn", "bad": "pill-bad", "mute": "pill-mute"}


def pill(kind: str, text: str) -> str:
    """HTML for a small coloured status label; kind is good, warn, bad or mute."""
    return f'<span class="pill {_PILL.get(kind, "pill-mute")}">{text}</span>'


def status_dot(online: bool, text: str) -> str:
    color = PALETTE["lime"] if online else PALETTE["bad"]
    return (
        f'<div class="status-line"><span class="status-dot" style="background:{color}"></span>'
        f"{text}</div>"
    )
