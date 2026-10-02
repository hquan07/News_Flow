import asyncio

import httpx
import pytest

from api.models.telegram import TelegramUpdate
from api.services.telegram_access import TelegramAccessPolicy
from api.services.telegram_client import (
    TelegramAPIError,
    TelegramBotClient,
    split_plain_message,
)
from api.services.telegram_queries import TelegramQueryResponse
from api.telegram_bot_worker import TelegramBotWorker


def run(coroutine):
    return asyncio.run(coroutine)


def update(chat_id=100, user_id=200, text="/status"):
    return TelegramUpdate.model_validate(
        {
            "update_id": 50,
            "message": {
                "message_id": 3,
                "date": 1_700_000_000,
                "chat": {"id": chat_id, "type": "private"},
                "from": {
                    "id": user_id,
                    "is_bot": False,
                    "first_name": "Admin",
                },
                "text": text,
            },
        }
    )


class FakeBotClient:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class FakeQueryService:
    def __init__(self, error=None):
        self.error = error
        self.requests = []

    async def execute(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return TelegramQueryResponse("healthy", request.command)


def test_client_parses_updates_and_sends_messages():
    requests = []

    async def handler(request):
        requests.append(request)
        method = request.url.path.rsplit("/", 1)[-1]
        if method == "getUpdates":
            return httpx.Response(
                200,
                json={"ok": True, "result": [update().model_dump(by_alias=True)]},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 4}})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramBotClient("test-token", http_client=http)

    updates = run(client.get_updates(offset=40, timeout_seconds=1))
    run(client.send_message(100, "hello"))
    run(http.aclose())

    assert updates[0].update_id == 50
    assert requests[0].url.path.endswith("/getUpdates")
    assert requests[1].url.path.endswith("/sendMessage")


def test_client_raises_sanitized_api_error():
    async def handler(_request):
        return httpx.Response(401, json={"ok": False, "description": "Unauthorized"})

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = TelegramBotClient("secret-token", http_client=http, max_attempts=1)

    with pytest.raises(TelegramAPIError, match="HTTP 401: Unauthorized") as exc_info:
        run(client.get_updates(offset=None, timeout_seconds=1))
    run(http.aclose())

    assert "secret-token" not in str(exc_info.value)


def test_long_plain_messages_are_split():
    chunks = split_plain_message("word " * 1200, limit=100)

    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)


def test_worker_answers_authorized_query():
    client = FakeBotClient()
    queries = FakeQueryService()
    worker = TelegramBotWorker(
        client,
        TelegramAccessPolicy({100}, {200}),
        queries,
    )

    run(worker.handle_update(update()))

    assert queries.requests[0].command == "status"
    assert client.messages == [(100, "healthy")]


def test_worker_silently_ignores_unauthorized_query():
    client = FakeBotClient()
    queries = FakeQueryService()
    worker = TelegramBotWorker(
        client,
        TelegramAccessPolicy({100}, {200}),
        queries,
    )

    run(worker.handle_update(update(user_id=999)))

    assert queries.requests == []
    assert client.messages == []


def test_worker_returns_safe_error_message():
    client = FakeBotClient()
    queries = FakeQueryService(RuntimeError("database secret"))
    worker = TelegramBotWorker(
        client,
        TelegramAccessPolicy({100}, {200}),
        queries,
    )

    run(worker.handle_update(update(text="/alerts")))

    assert "database secret" not in client.messages[0][1]
    assert "thử lại sau" in client.messages[0][1]
