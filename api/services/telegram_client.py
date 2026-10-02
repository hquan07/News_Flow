import asyncio
import logging

import httpx

from api.models.telegram import TelegramUpdate

logger = logging.getLogger("newspulse.telegram.client")

TELEGRAM_MESSAGE_LIMIT = 3900
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class TelegramAPIError(RuntimeError):
    pass


class TelegramBotClient:
    def __init__(
        self,
        bot_token: str,
        http_client: httpx.AsyncClient | None = None,
        max_attempts: int = 3,
    ) -> None:
        if not bot_token:
            raise ValueError("Telegram bot token is required")
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.http_client = http_client or httpx.AsyncClient()
        self._owns_client = http_client is None
        self.max_attempts = max(max_attempts, 1)

    async def close(self) -> None:
        if self._owns_client:
            await self.http_client.aclose()

    async def disable_webhook(self, drop_pending_updates: bool = False) -> None:
        await self._call(
            "deleteWebhook",
            {"drop_pending_updates": drop_pending_updates},
        )

    async def get_updates(
        self,
        offset: int | None,
        timeout_seconds: int,
    ) -> list[TelegramUpdate]:
        payload = {
            "timeout": timeout_seconds,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = await self._call(
            "getUpdates",
            payload,
            timeout_seconds=timeout_seconds + 5,
        )
        return [TelegramUpdate.model_validate(item) for item in result]

    async def send_message(self, chat_id: int, text: str) -> None:
        for chunk in split_plain_message(text):
            await self._call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
            )

    async def _call(
        self,
        method: str,
        payload: dict,
        timeout_seconds: float = 15,
    ):
        last_error = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            response = None
            try:
                response = await self.http_client.post(
                    f"{self.base_url}/{method}",
                    json=payload,
                    timeout=timeout_seconds,
                )
                data = response.json()
                if response.status_code == 200 and data.get("ok"):
                    return data.get("result")
                last_error = (
                    f"HTTP {response.status_code}: "
                    f"{data.get('description', 'request rejected')}"
                )
            except (httpx.HTTPError, ValueError) as exc:
                detail = str(exc).replace(self.bot_token, "[redacted]")
                last_error = f"{type(exc).__name__}: {detail}"
                data = {}

            retryable = response is None or response.status_code in RETRYABLE_STATUS_CODES
            if not retryable or attempt == self.max_attempts:
                break

            retry_after = data.get("parameters", {}).get("retry_after")
            delay = float(retry_after) if retry_after is not None else 2 ** (attempt - 1)
            delay = min(delay, 60.0)
            logger.warning(
                "Telegram API %s failed attempt=%s/%s retry_in=%.1fs",
                method,
                attempt,
                self.max_attempts,
                delay,
            )
            await asyncio.sleep(delay)

        raise TelegramAPIError(
            f"Telegram API {method} failed after {self.max_attempts} "
            f"attempt(s): {last_error}"
        )


def split_plain_message(
    message: str,
    limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    if not message or not message.strip():
        raise ValueError("Telegram message must not be empty")

    chunks = []
    remaining = message.strip()
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    if remaining:
        chunks.append(remaining)
    return chunks
