"""dashboard/helpers.py – Small pure helpers for the dashboard (no Streamlit import, testable in CI)."""

from __future__ import annotations

import base64
import hashlib

# Largest receipt photo, in MB. Must equal server.maxUploadSize in .streamlit/config.toml and
# MAX_UPLOAD_MB in the API settings (tests/unit/test_dashboard_i18n.py checks all three).
MAX_UPLOAD_MB = 10

# Flags are inline SVG, not emoji: Windows browsers draw flag emoji as the letters "ID" / "GB".
_FLAG_SVG = {
    "id": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 3 2">'
        '<rect width="3" height="1" fill="#CE1126"/><rect y="1" width="3" height="1" fill="#FFFFFF"/>'
        "</svg>"
    ),
    "en": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 30">'
        '<clipPath id="s"><path d="M0,0 v30 h60 v-30 z"/></clipPath>'
        '<clipPath id="t"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z"/></clipPath>'
        '<g clip-path="url(#s)"><path d="M0,0 v30 h60 v-30 z" fill="#012169"/>'
        '<path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/>'
        '<path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#t)" stroke="#C8102E" stroke-width="4"/>'
        '<path d="M30,0 v30 M0,15 h60" stroke="#fff" stroke-width="10"/>'
        '<path d="M30,0 v30 M0,15 h60" stroke="#C8102E" stroke-width="6"/></g></svg>'
    ),
}


def flag_data_uri(lang: str) -> str:
    svg = _FLAG_SVG.get(lang, _FLAG_SVG["id"])
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def fmt_rupiah(amount: float | int | None) -> str:
    """Rupiah with dots as thousands separators (the Indonesian convention, used in both languages)."""
    if amount is None:
        return "Rp -"
    return f"Rp {int(amount):,}".replace(",", ".")


def file_key(data: bytes) -> str:
    """Stable id of an image, so the same photo is never scanned twice on a Streamlit rerun."""
    return hashlib.sha256(data).hexdigest()


def build_queue(chosen: list[dict], done: set[str] | dict) -> list[dict]:
    """The images still to scan: each gets its hash as "key"; copies and finished ones are dropped."""
    queue: list[dict] = []
    seen: set[str] = set()
    for item in chosen:
        item["key"] = file_key(item["data"])
        if item["key"] not in done and item["key"] not in seen:
            seen.add(item["key"])
            queue.append(item)
    return queue
