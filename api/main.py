from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from api.config import close_ch_client, get_settings
from api.database import lifespan_db
from api.exceptions import DependencyUnavailableError
from api.middleware import RequestContextMiddleware, request_id_context
from api.services.health import dependency_health
from api.services.alert_metrics import alert_metrics, alert_metrics_flush_loop
from api.routers import articles, overview, trending, sources, alerts, entities, stream, sentiment, social, auth, recommendations, admin, crawler_admin, public

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    metrics_stop = asyncio.Event()
    metrics_task = asyncio.create_task(alert_metrics_flush_loop(metrics_stop))
    try:
        async with lifespan_db():
            yield
    finally:
        metrics_stop.set()
        await metrics_task
        try:
            await alert_metrics.flush_to_mongo()
        except Exception:
            pass
        close_ch_client()


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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)


@app.exception_handler(DependencyUnavailableError)
async def dependency_unavailable_handler(
    _request: Request,
    exc: DependencyUnavailableError,
):
    request_id = request_id_context.get()
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "DEPENDENCY_UNAVAILABLE",
                "message": "Required data service is temporarily unavailable",
                "dependency": exc.dependency,
                "request_id": request_id,
            }
        },
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
app.include_router(social.router, prefix=prefix)
app.include_router(auth.router, prefix=prefix)
app.include_router(recommendations.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
app.include_router(crawler_admin.router, prefix=prefix)
app.include_router(public.router, prefix=prefix)


@app.get("/health", tags=["Health"])
@app.get("/health/live", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    result = await dependency_health()
    return JSONResponse(
        content={
            **result,
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
        },
        status_code=200 if result["status"] == "healthy" else 503,
    )


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
    }
