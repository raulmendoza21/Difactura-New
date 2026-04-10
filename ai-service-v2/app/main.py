"""Difactura document engine v2 — FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router as invoice_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Difactura v2 engine started")
    yield
    logger.info("Difactura v2 engine shutting down")


app = FastAPI(
    title="Difactura Motor Documental v2",
    description="Servicio v2 — extracción universal sin familias",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoice_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
