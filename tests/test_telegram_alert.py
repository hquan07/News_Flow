import requests
import pytest

from infrastructure.monitoring.telegram_alert import (
    TelegramAlertNotifier,
    TelegramConfigurationError,
    TelegramDeliveryError,
    split_telegram_message,
)


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def test_missing_credentials_fail_closed(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    notifier = TelegramAlertNotifier(max_attempts=1)

    with pytest.raises(TelegramConfigurationError):
        notifier.send_alert("test")


def test_successful_delivery_uses_expected_payload():
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse(200)

    notifier = TelegramAlertNotifier(
        bot_token="test-token",
        chat_id="test-chat",
        timeout_seconds=4,
        max_attempts=1,
        post=post,
    )

    assert notifier.send_alert("<b>Alert</b>") is True
    assert calls[0][0].endswith("/bottest-token/sendMessage")
    assert calls[0][1]["timeout"] == 4
    assert calls[0][1]["json"] == {
        "chat_id": "test-chat",
        "text": "<b>Alert</b>",
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }


def test_rate_limit_honors_retry_after():
    responses = iter(
        [
            FakeResponse(429, {"parameters": {"retry_after": 7}}),
            FakeResponse(200),
        ]
    )
    sleeps = []
    notifier = TelegramAlertNotifier(
        bot_token="test-token",
        chat_id="test-chat",
        max_attempts=2,
        post=lambda *_args, **_kwargs: next(responses),
        sleep=sleeps.append,
    )

    notifier.send_alert("Alert")

    assert sleeps == [7.0]


def test_network_errors_are_retried_then_raised():
    attempts = []
    sleeps = []

    def post(*_args, **_kwargs):
        attempts.append(1)
        raise requests.Timeout("network timeout")

    notifier = TelegramAlertNotifier(
        bot_token="test-token",
        chat_id="test-chat",
        max_attempts=3,
        retry_base_seconds=0.5,
        post=post,
        sleep=sleeps.append,
    )

    with pytest.raises(TelegramDeliveryError, match="failed after 3 attempt"):
        notifier.send_alert("Alert")

    assert len(attempts) == 3
    assert sleeps == [0.5, 1.0]


def test_delivery_errors_redact_bot_token():
    token = "secret-token"

    def post(*_args, **_kwargs):
        raise requests.ConnectionError(f"failed URL containing {token}")

    notifier = TelegramAlertNotifier(
        bot_token=token,
        chat_id="test-chat",
        max_attempts=1,
        post=post,
    )

    with pytest.raises(TelegramDeliveryError) as exc_info:
        notifier.send_alert("Alert")

    assert token not in str(exc_info.value)


def test_non_retryable_error_fails_immediately():
    attempts = []

    def post(*_args, **_kwargs):
        attempts.append(1)
        return FakeResponse(400, {"description": "Bad Request"})

    notifier = TelegramAlertNotifier(
        bot_token="test-token",
        chat_id="test-chat",
        max_attempts=3,
        post=post,
        sleep=lambda _seconds: None,
    )

    with pytest.raises(TelegramDeliveryError, match="HTTP 400: Bad Request"):
        notifier.send_alert("Alert")

    assert len(attempts) == 1


def test_long_messages_are_split_before_delivery():
    message = "first section\n" + ("word " * 1200)
    chunks = split_telegram_message(message, limit=120)

    assert len(chunks) > 1
    assert all(0 < len(chunk) <= 120 for chunk in chunks)
    assert "".join(chunks).replace(" ", "") == message.strip().replace(" ", "").replace("\n", "")
