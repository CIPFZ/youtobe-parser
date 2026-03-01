"""FastAPI application entry point for the YouTube Parser service."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Parser",
    description="Private high-performance YouTube video parser & download service",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


frontend_dist = Path(__file__).resolve().parent.parent / "frontend_dist"
if frontend_dist.exists():
    logger.info("Serving frontend static files from %s", frontend_dist)

    @app.get("/", include_in_schema=False)
    async def spa_index() -> FileResponse:
        return FileResponse(frontend_dist / "index.html")

    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
