import asyncio

from api.models.telegram import TelegramUpdate
from api.services.telegram_runtime import TelegramAuditStore, TelegramRateLimiter


class FakeCollection:
    def __init__(self, document=None):
        self.document = document
        self.indexes = []
        self.updates = []
        self.inserts = []

    async def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))

    async def find_one(self, query):
        return self.document

    async def update_one(self, query, update, **kwargs):
        self.updates.append((query, update, kwargs))

    async def insert_one(self, document):
        self.inserts.append(document)


class FakeDatabase:
    def __init__(self, offset=None):
        self.telegram_bot_audit = FakeCollection()
        document = {"offset": offset} if offset is not None else None
        self.telegram_bot_state = FakeCollection(document)


def update():
    return TelegramUpdate.model_validate(
        {
            "update_id": 10,
            "message": {
                "message_id": 1,
                "date": 1_700_000_000,
                "chat": {"id": 100, "type": "private"},
                "from": {"id": 200, "first_name": "Admin"},
                "text": "Nội dung không được lưu",
            },
        }
    )


def test_rate_limiter_expires_old_events():
    values = iter([0.0, 1.0, 2.0, 61.0])
    limiter = TelegramRateLimiter(2, window_seconds=60, clock=lambda: next(values))

    assert limiter.allow(200) is True
    assert limiter.allow(200) is True
    assert limiter.allow(200) is False
    assert limiter.allow(200) is True


def test_audit_store_persists_offset_and_metadata_without_raw_text():
    database = FakeDatabase(offset=40)
    store = TelegramAuditStore(database, retention_days=30)

    async def scenario():
        await store.ensure_indexes()
        assert await store.load_offset() == 40
        await store.save_offset(41)
        await store.record(
            update(),
            command="status",
            outcome="success",
            reason=None,
            latency_ms=12.34,
        )

    asyncio.run(scenario())

    assert database.telegram_bot_audit.indexes[0][1]["expireAfterSeconds"] == 30 * 86400
    assert database.telegram_bot_state.updates[0][1]["$set"]["offset"] == 41
    audit = database.telegram_bot_audit.inserts[0]
    assert audit["chat_id"] == 100
    assert audit["user_id"] == 200
    assert audit["command"] == "status"
    assert "text" not in audit
    assert "Nội dung" not in str(audit)
