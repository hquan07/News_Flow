import json
import logging

import pytest
from httpx import AsyncClient

from api.config import get_settings
from api.logging_config import JsonFormatter
from api.middleware import rate_limiter
from api.routers.stream import SSEConnectionLimiter, _format_sse


@pytest.mark.asyncio
async def test_rate_limit_returns_structured_429(
    async_client: AsyncClient,
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "API_RATE_LIMIT_PER_MINUTE", 1)
    rate_limiter.reset()

    first = await async_client.get("/")
    second = await async_client.get("/")

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "RATE_LIMITED"
    assert second.json()["error"]["request_id"]
    assert second.headers["Retry-After"] == "60"
    rate_limiter.reset()


@pytest.mark.asyncio
async def test_oversized_body_returns_413(
    async_client: AsyncClient,
    monkeypatch,
):
    settings = get_settings()
    monkeypatch.setattr(settings, "API_MAX_BODY_BYTES", 10)
    rate_limiter.reset()

    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "large-password"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"


def test_json_formatter_includes_request_context():
    record = logging.LogRecord(
        "newspulse.test",
        logging.INFO,
        __file__,
        1,
        "request_completed",
        (),
        None,
    )
    record.request_id = "request-123"
    record.status_code = 200

    payload = json.loads(JsonFormatter().format(record))

    assert payload["message"] == "request_completed"
    assert payload["request_id"] == "request-123"
    assert payload["status_code"] == 200


def test_sse_event_contains_id_and_retry_hint(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "SSE_RETRY_MILLISECONDS", 7000)

    event = _format_sse("update", '{"type":"heartbeat"}')

    assert event.startswith("id: ")
    assert "retry: 7000\n" in event
    assert "event: update\n" in event
    assert event.endswith("\n\n")


@pytest.mark.asyncio
async def test_sse_connection_limiter_releases_capacity():
    limiter = SSEConnectionLimiter()

    assert await limiter.acquire(1) is True
    assert await limiter.acquire(1) is False
    await limiter.release()
    assert await limiter.acquire(1) is True
