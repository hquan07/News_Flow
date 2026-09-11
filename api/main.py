from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.config import get_settings
from api.database import lifespan_db
from api.routers import articles, overview, trending, sources, alerts, entities, stream, sentiment

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
        "Provides analytics endpoints for Vietnamese news data."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    }