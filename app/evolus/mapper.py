"""app/evolus/mapper.py – Maps Evolus extractor response to ExtractionResult.

IMPORTANT: The actual response schema from Evolus is unknown (TO_CONFIRM).
This mapper is driven by a simple field-mapping config. A human must update
FIELD_MAP once the real Evolus response schema is known.

To adjust:
    1. Run a real Evolus extractor call and inspect the response JSON.
    2. Update FIELD_MAP keys to match actual field paths in the response.
    3. Test with app.evolus.mapper.map_evolus_response(sample_response).
"""
from __future__ import annotations

from typing import Any

from app.extraction.schema import ExtractedItem, ExtractionResult

# Field mapping: ExtractionResult field -> path in Evolus response
# Set to None for fields not present in the Evolus response.
FIELD_MAP = {
    "date": "date",           # TO_CONFIRM: adjust to actual path
    "customer": "customer",   # TO_CONFIRM
    "total": "total",         # TO_CONFIRM
    "notes": "notes",         # TO_CONFIRM
    # Items list path in response
    "items_key": "items",     # TO_CONFIRM: key that holds the items array
    "item_name_raw": "item_name_raw",  # TO_CONFIRM
    "qty": "qty",             # TO_CONFIRM
    "unit": "unit",           # TO_CONFIRM
    "unit_price": "unit_price",  # TO_CONFIRM
    "line_total": "line_total",  # TO_CONFIRM
}


def _get(d: dict, key: str) -> Any:
    """Safe nested get using dot notation."""
    parts = key.split(".")
    val = d
    for p in parts:
        if not isinstance(val, dict):
            return None
        val = val.get(p)
    return val


def map_evolus_response(response: dict[str, Any]) -> ExtractionResult:
    """Convert an Evolus extractor response to ExtractionResult.

    Args:
        response: The JSON response from the Evolus extractor API.

    Returns:
        ExtractionResult ready for the validation pipeline.
    """
    items_raw = _get(response, FIELD_MAP["items_key"]) or []
    items = []
    for item in items_raw:
        items.append(
            ExtractedItem(
                item_name_raw=_get(item, FIELD_MAP["item_name_raw"]) or "",
                qty=_get(item, FIELD_MAP["qty"]),
                unit=_get(item, FIELD_MAP["unit"]),
                unit_price=_get(item, FIELD_MAP["unit_price"]),
                line_total=_get(item, FIELD_MAP["line_total"]),
            )
        )

    return ExtractionResult(
        date=_get(response, FIELD_MAP["date"]),
        customer=_get(response, FIELD_MAP["customer"]),
        items=items,
        total=_get(response, FIELD_MAP["total"]),
        notes=_get(response, FIELD_MAP["notes"]),
    )
