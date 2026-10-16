"""app/extraction/schema.py – Pydantic models for OCR extraction results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, field_validator

from app.validation.money import parse_rupiah


class ExtractedItem(BaseModel):
    item_name_raw: str
    qty: float | None = None
    unit: str | None = None
    unit_price: int | None = None
    line_total: int | None = None

    @field_validator("unit_price", "line_total", mode="before")
    @classmethod
    def parse_money(cls, v: Any) -> int | None:
        if v is None:
            return None
        try:
            return parse_rupiah(v)
        except (ValueError, TypeError):
            return None


class ExtractionResult(BaseModel):
    date: str | None = None
    customer: str | None = None
    items: list[ExtractedItem] = []
    total: int | None = None
    notes: str | None = None

    @field_validator("total", mode="before")
    @classmethod
    def parse_total(cls, v: Any) -> int | None:
        if v is None:
            return None
        try:
            return parse_rupiah(v)
        except (ValueError, TypeError):
            return None

    def to_extraction_dict(self) -> dict:
        """Convert to the internal extraction dict format used by the validation pipeline."""
        return {
            "date": self.date,
            "customer": self.customer,
            "items": [
                {
                    "item_name_raw": item.item_name_raw,
                    "qty": item.qty,
                    "unit": item.unit,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                }
                for item in self.items
            ],
            "total": self.total,
        }
