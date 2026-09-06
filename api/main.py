from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from api.config import get_settings
from api.database import lifespan_db
from api.routers import (
    articles,
    overview,
    trending,
    sources,
    alerts,
    entities,
    stream,
    sentiment,
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with lifespan_db():
        yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "NewsPulse — Realtime News Intelligence Platform API. "
        "Provides analytics endpoints for Vietnamese news data "
        "from VnExpress, Tuổi Trẻ, and Thanh Niên."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow dashboard tools (Metabase, Superset) and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
prefix = settings.API_V1_PREFIX
app.include_router(articles.router, prefix=prefix)
app.include_router(overview.router, prefix=prefix)
app.include_router(trending.router, prefix=prefix)
app.include_router(sources.router, prefix=prefix)
app.include_router(alerts.router, prefix=prefix)
app.include_router(entities.router, prefix=prefix)
app.include_router(sentiment.router, prefix=prefix)
app.include_router(stream.router, prefix=prefix)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
        "stream": "/api/v1/stream",
    }