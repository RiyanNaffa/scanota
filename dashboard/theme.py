"""dashboard/theme.py – CSS injection for scanota dark-green theme."""
from __future__ import annotations

import streamlit as st

PALETTE = {
    "surface": "#111B17",
    "raised": "#172420",
    "border": "#22332D",
    "text_secondary": "#8FA89D",
    "muted": "#5E766B",
    "accent": "#2ECC71",
    "hover": "#27AE60",
    "warning": "#F2B84B",
    "negative": "#EF6A5B",
    "info": "#5BC0DE",
}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        /* Cards */
        .scanota-card {{
            background: {PALETTE['surface']};
            border: 1px solid {PALETTE['border']};
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 12px;
        }}
        /* KPI cards */
        .kpi-value {{
            font-size: 2rem;
            font-weight: 700;
            color: {PALETTE['accent']};
        }}
        .kpi-label {{
            font-size: 0.85rem;
            color: {PALETTE['text_secondary']};
        }}
        /* Status badges */
        .badge-confirmed {{
            background: {PALETTE['accent']}22;
            color: {PALETTE['accent']};
            border: 1px solid {PALETTE['accent']};
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-review {{
            background: {PALETTE['warning']}22;
            color: {PALETTE['warning']};
            border: 1px solid {PALETTE['warning']};
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-order_now {{
            background: {PALETTE['negative']}22;
            color: {PALETTE['negative']};
            border: 1px solid {PALETTE['negative']};
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
        }}
        .badge-watch {{
            background: {PALETTE['warning']}22;
            color: {PALETTE['warning']};
            border: 1px solid {PALETTE['warning']};
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
        }}
        .badge-ok {{
            background: {PALETTE['accent']}22;
            color: {PALETTE['accent']};
            border: 1px solid {PALETTE['accent']};
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75rem;
        }}
        /* Tables */
        .dataframe td, .dataframe th {{
            border-color: {PALETTE['border']} !important;
        }}
        /* Sidebar */
        section[data-testid="stSidebar"] {{
            background: {PALETTE['surface']};
            border-right: 1px solid {PALETTE['border']};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt_rupiah(amount: float | int | None) -> str:
    """Format amount as Indonesian Rupiah string."""
    if amount is None:
        return "Rp -"
    return f"Rp {int(amount):,}".replace(",", ".")


def status_badge(status: str) -> str:
    css = "badge-confirmed" if status == "confirmed" else "badge-review"
    label = "Dikonfirmasi" if status == "confirmed" else "Perlu Dicek"
    return f'<span class="{css}">{label}</span>'


def action_badge(act: str) -> str:
    labels = {"order_now": "Pesan Sekarang", "watch": "Pantau", "ok": "Aman"}
    return f'<span class="badge-{act}">{labels.get(act, act)}</span>'
