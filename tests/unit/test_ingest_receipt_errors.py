"""tests/unit/test_ingest_receipt_errors.py – A failed extraction is a 502 with a plain message."""
from __future__ import annotations

import io
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app import config
from app.api import ingest
from app.config import Settings
from app.extraction.client import ExtractionError


@pytest.fixture(autouse=True)
def _configured_llm(monkeypatch):
    monkeypatch.setattr(
        config, "_settings", Settings(_env_file=None, llm_base_url="http://llm.test/v1", llm_api_key="k")
    )


def _stub_offline(monkeypatch, fn):
    """The endpoint imports app.ingest.offline lazily; stub it so OpenCV is not needed here."""
    monkeypatch.setitem(sys.modules, "app.ingest.offline", SimpleNamespace(ingest_receipt_file=fn))


def _upload() -> UploadFile:
    return UploadFile(
        io.BytesIO(b"jpegbytes"), filename="nota.jpg", headers=Headers({"content-type": "image/jpeg"})
    )


async def test_extraction_error_becomes_502_without_provider_details(monkeypatch):
    async def boom(db, data, filename):
        raise ExtractionError("Error from provider self-dploy: 503 No available workers")

    _stub_offline(monkeypatch, boom)

    with pytest.raises(HTTPException) as info:
        await ingest.ingest_receipt(_upload(), db=None)

    assert info.value.status_code == 502
    assert info.value.detail == ingest.EXTRACTION_UNAVAILABLE
    assert "self-dploy" not in info.value.detail


async def test_success_is_passed_through(monkeypatch):
    async def ok(db, data, filename):
        return {"id": 7, "status": "confirmed"}

    _stub_offline(monkeypatch, ok)

    assert await ingest.ingest_receipt(_upload(), db=None) == {"id": 7, "status": "confirmed"}
