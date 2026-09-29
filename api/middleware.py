import logging
import time
import uuid
import json
import threading
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from api.config import get_settings


logger = logging.getLogger("newspulse.api")
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


class FixedWindowRateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, tuple[int, int]] = {}

    def allow(self, key: str, limit: int) -> bool:
        window = int(time.monotonic() // 60)
        with self._lock:
            previous_window, count = self._buckets.get(key, (window, 0))
            if previous_window != window:
                count = 0
            count += 1
            self._buckets[key] = (window, count)
            return count <= limit

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = FixedWindowRateLimiter()


class RequestSafetyMiddleware:
    """Reject oversized bodies and abusive request rates before route work."""

    EXEMPT_PATHS = {"/health", "/health/live", "/health/ready"}

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length and int(content_length) > settings.API_MAX_BODY_BYTES:
            await self._reject(send, 413, "PAYLOAD_TOO_LARGE", "Request body is too large")
            return

        path = scope.get("path", "")
        if path not in self.EXEMPT_PATHS and not path.startswith("/docs"):
            client = scope.get("client")
            client_ip = client[0] if client else "unknown"
            if not rate_limiter.allow(client_ip, max(settings.API_RATE_LIMIT_PER_MINUTE, 1)):
                await self._reject(
                    send,
                    429,
                    "RATE_LIMITED",
                    "Too many requests; retry later",
                    headers={"Retry-After": "60"},
                )
                return

        await self.app(scope, receive, send)

    async def _reject(
        self,
        send: Send,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        response_headers = {"content-type": "application/json", **(headers or {})}
        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (key.lower().encode(), value.encode())
                for key, value in response_headers.items()
            ],
        })
        body = json.dumps({
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id_context.get(),
            }
        }).encode()
        await send({"type": "http.response.body", "body": body})


class RequestContextMiddleware:
    """Attach a request ID without buffering streaming responses."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        incoming_id = headers.get("X-Request-ID", "")
        request_id = incoming_id[:128] if incoming_id else str(uuid.uuid4())
        token = request_id_context.set(request_id)
        started = time.monotonic()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
            logger.info("request_completed", extra={
                "method": scope.get("method"),
                "path": scope.get("path"),
                "status_code": status_code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1),
                "request_id": request_id,
            })
        except Exception:
            logger.exception("unhandled_request_error", extra={
                "method": scope.get("method"),
                "path": scope.get("path"),
                "request_id": request_id,
            })
            raise
        finally:
            request_id_context.reset(token)
