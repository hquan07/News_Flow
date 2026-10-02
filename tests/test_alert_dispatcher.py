import pytest

from infrastructure.monitoring.alert_dispatcher import (
    AlertEvent,
    TelegramAlertDispatcher,
    format_alert_digest,
)
from infrastructure.monitoring.telegram_alert import TelegramDeliveryError


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
