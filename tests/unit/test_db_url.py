"""tests/unit/test_db_url.py – Postgres URLs must select the installed psycopg 3 driver."""
from __future__ import annotations

import pytest
from sqlalchemy.engine import make_url

from app.db.url import to_sqlalchemy_url


@pytest.mark.parametrize("scheme", ["postgresql", "postgres"])
def test_plain_url_gets_psycopg3_driver(scheme):
    url = to_sqlalchemy_url(f"{scheme}://scanota:pw@db:5432/scanota")
    assert url == "postgresql+psycopg://scanota:pw@db:5432/scanota"
    assert make_url(url).get_dialect().driver == "psycopg"


def test_explicit_driver_is_untouched():
    url = "postgresql+asyncpg://u:p@db/x"
    assert to_sqlalchemy_url(url) == url


def test_non_postgres_url_is_untouched():
    assert to_sqlalchemy_url("sqlite:///x.db") == "sqlite:///x.db"


def test_password_containing_scheme_text_is_preserved():
    url = to_sqlalchemy_url("postgresql://u:postgresql://@db/x")
    assert url == "postgresql+psycopg://u:postgresql://@db/x"
