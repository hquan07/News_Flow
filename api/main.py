from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os

from api.config import get_settings
from api.database import lifespan_db
from api.routers import articles, overview, trending, sources, alerts, entities

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


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/", tags=["Root"])
async def root():
    # Serve dashboard if it exists
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard",
    }


# Mount static files for dashboard
static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/dashboard", tags=["Dashboard"])
async def dashboard():
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"error": "Dashboard not found. Place index.html in /static/"}