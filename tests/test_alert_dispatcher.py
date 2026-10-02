import pytest

from infrastructure.monitoring.alert_dispatcher import (
    AlertEvent,
    MongoAlertCooldownStore,
    TelegramAlertDispatcher,
    format_alert_digest,
)
from infrastructure.monitoring.telegram_alert import TelegramDeliveryError
from pymongo.errors import DuplicateKeyError


class FakeCooldownStore:
    def __init__(self, blocked=None):
        self.blocked = set(blocked or [])
        self.sent = []
        self.released = []

    def claim(self, alert_id):
        if alert_id in self.blocked:
            return None
        return f"claim:{alert_id}"

    def mark_sent(self, alert_id, claim_id):
        self.sent.append((alert_id, claim_id))

    def release(self, alert_id, claim_id):
        self.released.append((alert_id, claim_id))


class FakeNotifier:
    def __init__(self, error=None):
        self.error = error
        self.messages = []

    def send_alert(self, message):
        self.messages.append(message)
        if self.error:
            raise self.error
        return True


class FakeMongoCollection:
    def __init__(self, duplicate=False):
        self.duplicate = duplicate
        self.claim_call = None
        self.update_calls = []

    def find_one_and_update(self, query, update, **options):
        self.claim_call = (query, update, options)
        if self.duplicate:
            raise DuplicateKeyError("already claimed")
        return {"claim_id": update["$set"]["claim_id"]}

    def update_one(self, query, update):
        self.update_calls.append((query, update))


def event(alert_id="volume:2026100208"):
    return AlertEvent(
        alert_id=alert_id,
        alert_type="volume_spike",
        severity="warning",
        title="Bão tin tức",
        details=("120 tin", "Tăng 3.0x"),
    )


def test_dispatch_only_sends_alerts_outside_cooldown():
    store = FakeCooldownStore(blocked={"duplicate"})
    telegram = FakeNotifier()
    dispatcher = TelegramAlertDispatcher(store, telegram)

    sent = dispatcher.dispatch([event("duplicate"), event("new")])

    assert sent == 1
    assert len(telegram.messages) == 1
    assert store.sent == [("new", "claim:new")]


def test_dispatch_releases_claim_when_delivery_fails():
    store = FakeCooldownStore()
    telegram = FakeNotifier(TelegramDeliveryError("offline"))
    dispatcher = TelegramAlertDispatcher(store, telegram)

    with pytest.raises(TelegramDeliveryError):
        dispatcher.dispatch([event("new")])

    assert store.sent == []
    assert store.released == [("new", "claim:new")]


def test_digest_escapes_dynamic_content_and_link():
    unsafe = AlertEvent(
        alert_id="trend:test",
        alert_type="trend_spike",
        severity="critical",
        title="<script>alert</script>",
        details=("A & B",),
    )

    message = format_alert_digest(
        [unsafe],
        dashboard_url='https://example.com/alerts?q="unsafe"&source=a',
    )

    assert "<script>" not in message
    assert "&lt;script&gt;alert&lt;/script&gt;" in message
    assert "A &amp; B" in message
    assert "&quot;unsafe&quot;&amp;source=a" in message


def test_invalid_severity_is_rejected():
    with pytest.raises(ValueError, match="Unsupported alert severity"):
        AlertEvent("id", "type", "urgent", "title", ("detail",))


def test_mongo_cooldown_claim_is_atomic_and_bounded():
    collection = FakeMongoCollection()
    store = MongoAlertCooldownStore(collection, cooldown_minutes=90)

    claim_id = store.claim("volume:2026100208")

    query, update, options = collection.claim_call
    assert claim_id == update["$set"]["claim_id"]
    assert query["_id"] == "volume:2026100208"
    assert update["$set"]["status"] == "pending"
    assert (
        update["$set"]["next_allowed_at"] - update["$set"]["claimed_at"]
    ).total_seconds() == 90 * 60
    assert options["upsert"] is True


def test_mongo_cooldown_treats_duplicate_key_as_existing_claim():
    store = MongoAlertCooldownStore(FakeMongoCollection(duplicate=True))

    assert store.claim("duplicate") is None


def test_mongo_cooldown_records_success_and_releases_failure():
    collection = FakeMongoCollection()
    store = MongoAlertCooldownStore(collection)

    store.mark_sent("alert-1", "claim-1")
    store.release("alert-2", "claim-2")

    assert collection.update_calls[0][0] == {
        "_id": "alert-1",
        "claim_id": "claim-1",
    }
    assert collection.update_calls[0][1]["$set"]["status"] == "sent"
    assert collection.update_calls[1][1]["$set"]["status"] == "failed"
    assert (
        collection.update_calls[1][1]["$set"]["next_allowed_at"]
        == collection.update_calls[1][1]["$set"]["failed_at"]
    )
