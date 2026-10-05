"""Low-cardinality HTTP metrics shared by all API workers."""

import os
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)
from starlette.types import ASGIApp, Message, Receive, Scope, Send


REQUESTS = Counter(
    "newspulse_http_requests_total",
    "Completed HTTP requests",
    ("method", "route", "status"),
)
LATENCY = Histogram(
    "newspulse_http_request_duration_seconds",
    "Time until the HTTP response starts",
    ("method", "route"),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)


def metrics_payload() -> tuple[bytes, str]:
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(), CONTENT_TYPE_LATEST


class HttpMetricsMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        started = time.monotonic()
        observed = False

        def observe(status: int) -> None:
            nonlocal observed
            if observed:
                return
            observed = True
            route = scope.get("route")
            route_name = getattr(route, "path", "unmatched")
            method = scope.get("method", "UNKNOWN")
            REQUESTS.labels(method, route_name, str(status)).inc()
            LATENCY.labels(method, route_name).observe(time.monotonic() - started)

        async def send_with_metrics(message: Message) -> None:
            if message["type"] == "http.response.start":
                observe(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_metrics)
        except Exception:
            observe(500)
            raise
