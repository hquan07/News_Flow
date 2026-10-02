import pytest

from api.config import _parse_integer_set
from api.models.telegram import (
    TelegramMessage,
    parse_telegram_query,
)
from api.services.telegram_access import TelegramAccessPolicy


def message(chat_id=100, user_id=200):
    return TelegramMessage.model_validate(
        {
            "message_id": 1,
            "date": 1_700_000_000,
            "chat": {"id": chat_id, "type": "private"},
            "from": {
                "id": user_id,
                "is_bot": False,
                "first_name": "Admin",
            },
            "text": "/alerts",
        }
    )


def test_parse_command_strips_bot_username():
    request = parse_telegram_query("  /Trend@NewsPulseBot 24h 5 ")

    assert request.command == "trend"
    assert request.args == ("24h", "5")
    assert request.raw_text == "/Trend@NewsPulseBot 24h 5"


def test_parse_plain_text_as_natural_language_query():
    request = parse_telegram_query("Có cảnh báo nào không?")

    assert request.command == "query"
    assert request.args == ("Có cảnh báo nào không?",)


def test_parse_ignores_empty_messages():
    assert parse_telegram_query(None) is None
    assert parse_telegram_query("   ") is None


def test_access_policy_fails_closed_without_allowlist():
    decision = TelegramAccessPolicy(set(), set()).check(message())

    assert decision.allowed is False
    assert decision.reason == "allowlist_not_configured"


def test_access_policy_requires_configured_chat_and_user():
    policy = TelegramAccessPolicy({100}, {200})

    assert policy.check(message()).allowed is True
    assert policy.check(message(chat_id=999)).reason == "chat_not_allowed"
    assert policy.check(message(user_id=999)).reason == "user_not_allowed"


def test_chat_allowlist_can_be_used_without_user_allowlist():
    policy = TelegramAccessPolicy({100}, set())

    assert policy.check(message(user_id=999)).allowed is True


def test_integer_allowlist_parser():
    assert _parse_integer_set("100, -200,100") == {100, -200}
    with pytest.raises(ValueError, match="comma-separated integer list"):
        _parse_integer_set("100,invalid")
