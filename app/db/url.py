"""app/db/url.py – Turn a plain Postgres URL into a SQLAlchemy URL for the psycopg 3 driver."""
from __future__ import annotations


def to_sqlalchemy_url(url: str) -> str:
    """Make a libpq-style URL usable by SQLAlchemy with the psycopg 3 driver.

    A bare postgresql:// URL makes SQLAlchemy import psycopg2, but only psycopg 3 is installed
    (see app/requirements.txt). The .env keeps the plain form so psql and libpq tools still work;
    a URL that already names a driver (postgresql+psycopg://, postgresql+asyncpg://) is untouched.
    """
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url
