import logging
import time
import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


logger = logging.getLogger("newspulse.api")
request_id_context: ContextVar[str] = ContextVar("request_id", default="-")


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
            logger.info(
                "%s %s status=%s duration_ms=%.1f request_id=%s",
                scope.get("method"),
                scope.get("path"),
                status_code,
                (time.monotonic() - started) * 1000,
                request_id,
            )
        except Exception:
            logger.exception(
                "Unhandled request error method=%s path=%s request_id=%s",
                scope.get("method"),
                scope.get("path"),
                request_id,
            )
            raise
        finally:
            request_id_context.reset(token)
