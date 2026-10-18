"""app/main.py – FastAPI application factory."""

from __future__ import annotations

import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

# -------------------------------------------------------------------
# Structured logging
# -------------------------------------------------------------------
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("scanota")


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="scanota",
        description="Paper receipts and online invoices in one clean sales database.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Routers. Imported without try/except on purpose: a router that fails to import must stop
    # the app at startup. Swallowing the error used to hide a missing endpoint behind a healthy
    # /health.
    # ------------------------------------------------------------------
    from app.api.chat import router as chat_router
    from app.api.health import router as health_router
    from app.api.ingest import router as ingest_router
    from app.api.products import router as products_router
    from app.api.restock import router as restock_router
    from app.api.review import router as review_router
    from app.api.summary import router as summary_router
    from app.api.transactions import router as tx_router

    for router in (
        health_router,
        ingest_router,
        tx_router,
        review_router,
        products_router,
        summary_router,
        restock_router,
        chat_router,
    ):
        application.include_router(router)

    logger.info("scanota app created (env=%s)", settings.app_env)
    return application


app = create_app()
