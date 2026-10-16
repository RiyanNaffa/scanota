"""app/extraction/service.py – Receipt extraction service.

Orchestrates: preprocess -> extract (LLM) -> validate -> return result.
"""
from __future__ import annotations

from typing import Any

from app.extraction.client import ExtractionClient
from app.extraction.preprocess import preprocess_image
from app.validation.pipeline import ValidationResult, validate_extraction


def extract_and_validate(
    image_bytes: bytes,
    catalog: list[dict[str, Any]],
    price_stats: dict[str, Any] | None = None,
    extraction_client: ExtractionClient | None = None,
) -> tuple[dict, ValidationResult]:
    """Preprocess image, extract with LLM, validate extraction.

    Returns:
        (raw_extraction_dict, ValidationResult)
    """
    if extraction_client is None:
        extraction_client = ExtractionClient()

    # Preprocess (CLAHE, deskew, resize)
    processed_bytes = preprocess_image(image_bytes)

    # Extract
    extraction_result = extraction_client.extract(processed_bytes)
    raw_dict = extraction_result.to_extraction_dict()

    # Validate
    validation = validate_extraction(raw_dict, catalog, price_stats or {})

    return raw_dict, validation
