from dataclasses import dataclass

from api.models.telegram import TelegramMessage


@dataclass(frozen=True)
class TelegramAccessDecision:
    allowed: bool
    reason: str


class TelegramAccessPolicy:
    def __init__(
        self,
        allowed_chat_ids: set[int],
        allowed_user_ids: set[int],
    ) -> None:
        self.allowed_chat_ids = allowed_chat_ids
        self.allowed_user_ids = allowed_user_ids

    def check(self, message: TelegramMessage) -> TelegramAccessDecision:
        if not self.allowed_chat_ids and not self.allowed_user_ids:
            return TelegramAccessDecision(False, "allowlist_not_configured")

        if self.allowed_chat_ids and message.chat.id not in self.allowed_chat_ids:
            return TelegramAccessDecision(False, "chat_not_allowed")

        sender_id = message.sender.id if message.sender else None
        if self.allowed_user_ids and sender_id not in self.allowed_user_ids:
            return TelegramAccessDecision(False, "user_not_allowed")

        return TelegramAccessDecision(True, "allowed")
