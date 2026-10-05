from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from api.config import close_ch_client, get_settings
from api.database import lifespan_db
from api.services.chat_store import ensure_chat_indexes
from api.services.chat_guard import ensure_indexes as ensure_chat_guard_indexes
from api.services.chat_metrics import ensure_indexes as ensure_chat_metrics_indexes
from api.services.chat_actions import ensure_indexes as ensure_chat_action_indexes
from api.services.intelligence_store import ensure_indexes as ensure_intelligence_indexes
from api.services.crisis_store import ensure_indexes as ensure_crisis_indexes
from api.services.scheduled_reports import ensure_indexes as ensure_report_indexes
from api.services.source_config import ensure_indexes as ensure_source_indexes
from api.services.retention import ensure_indexes as ensure_retention_indexes
from api.services.workspace_store import ensure_indexes as ensure_workspace_indexes
from api.exceptions import DependencyUnavailableError
from api.middleware import (
    RequestContextMiddleware,
    RequestSafetyMiddleware,
    request_id_context,
)
from api.logging_config import configure_logging
from api.services.health import dependency_health
from api.services.alert_metrics import alert_metrics, alert_metrics_flush_loop
from api.services.http_metrics import HttpMetricsMiddleware, metrics_payload
from api.services.data_metrics import warehouse_metrics_payload
from api.routers import articles, overview, trending, sources, alerts, entities, stream, sentiment, social, auth, recommendations, admin, crawler_admin, public, user_admin, chat, chat_actions, intelligence, events, insights, briefings, operations, retention, workspaces
from api.security import require_permission

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    metrics_stop = asyncio.Event()
    metrics_task = asyncio.create_task(alert_metrics_flush_loop(metrics_stop))
    try:
        async with lifespan_db():
            await ensure_chat_indexes()
            await ensure_chat_guard_indexes()
            await ensure_chat_metrics_indexes()
            await ensure_chat_action_indexes()
            await ensure_intelligence_indexes()
            await ensure_crisis_indexes()
            await ensure_report_indexes()
            await ensure_source_indexes()
            await ensure_retention_indexes()
            await ensure_workspace_indexes()
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
app.add_middleware(RequestSafetyMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(HttpMetricsMiddleware)


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
dashboard_access = [Depends(require_permission("dashboard.read"))]
app.include_router(articles.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(overview.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(trending.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(sources.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(
    alerts.router,
    prefix=prefix,
    dependencies=[Depends(require_permission("alerts.read"))],
)
app.include_router(entities.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(sentiment.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(stream.router, prefix=prefix)
app.include_router(social.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(auth.router, prefix=prefix)
app.include_router(recommendations.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
app.include_router(crawler_admin.router, prefix=prefix)
app.include_router(user_admin.router, prefix=prefix)
app.include_router(public.router, prefix=prefix)
app.include_router(chat.router, prefix=prefix)
app.include_router(chat_actions.router, prefix=prefix)
app.include_router(intelligence.router, prefix=prefix)
app.include_router(events.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(insights.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(briefings.router, prefix=prefix, dependencies=dashboard_access)
app.include_router(operations.router, prefix=prefix)
app.include_router(retention.router, prefix=prefix)
app.include_router(workspaces.router, prefix=prefix)


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


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics():
    payload, content_type = metrics_payload()
    return Response(content=payload, media_type=content_type)


@app.get("/metrics/data", include_in_schema=False)
async def prometheus_data_metrics():
    try:
        payload = await warehouse_metrics_payload()
    except Exception:
        return Response(status_code=503, content="Warehouse metrics unavailable\n")
    return Response(content=payload, media_type="text/plain; version=0.0.4")


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs": "/docs",
        "health": "/health",
    }
