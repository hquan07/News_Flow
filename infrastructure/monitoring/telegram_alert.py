import logging
import os
import time
from collections.abc import Callable

import requests

logger = logging.getLogger(__name__)

TELEGRAM_MESSAGE_LIMIT = 3900
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class TelegramDeliveryError(RuntimeError):
    """Raised when Telegram cannot accept an alert."""


class TelegramConfigurationError(TelegramDeliveryError):
    """Raised when required Telegram credentials are missing."""


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("Invalid %s value; using %s", name, default)
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        logger.warning("Invalid %s value; using %s", name, default)
        return default


def split_telegram_message(
    message: str,
    limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    """Split a message on line/word boundaries below Telegram's hard limit."""
    if not message or not message.strip():
        raise ValueError("Telegram message must not be empty")
    if limit < 1:
        raise ValueError("Telegram message limit must be positive")

    chunks: list[str] = []
    remaining = message.strip()
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at <= 0:
            split_at = limit

        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


class TelegramAlertNotifier:
    def __init__(
        self,
        bot_token: str | None = None,
        chat_id: str | None = None,
        timeout_seconds: float | None = None,
        max_attempts: int | None = None,
        retry_base_seconds: float | None = None,
        post: Callable[..., requests.Response] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else _env_float("TELEGRAM_TIMEOUT_SECONDS", 10.0)
        )
        self.max_attempts = (
            max_attempts
            if max_attempts is not None
            else _env_int("TELEGRAM_MAX_ATTEMPTS", 3)
        )
        self.retry_base_seconds = (
            retry_base_seconds
            if retry_base_seconds is not None
            else _env_float("TELEGRAM_RETRY_BASE_SECONDS", 1.0)
        )
        self._post = post or requests.post
        self._sleep = sleep or time.sleep

    def send_alert(self, message: str) -> bool:
        self._validate_configuration()
        chunks = split_telegram_message(message)

        for index, chunk in enumerate(chunks, start=1):
            self._send_chunk(chunk, index=index, total=len(chunks))

        logger.info("Telegram alert sent successfully in %s chunk(s).", len(chunks))
        return True

    def _validate_configuration(self) -> None:
        placeholders = {
            "your_telegram_bot_token_here",
            "YOUR_TELEGRAM_BOT_TOKEN_HERE",
        }
        if not self.bot_token or self.bot_token in placeholders or not self.chat_id:
            raise TelegramConfigurationError(
                "Telegram credentials are not configured"
            )
        if self.max_attempts < 1:
            raise TelegramConfigurationError(
                "TELEGRAM_MAX_ATTEMPTS must be at least 1"
            )

    def _send_chunk(self, message: str, *, index: int, total: int) -> None:
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        last_error = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            response = None
            try:
                response = self._post(
                    url,
                    json=payload,
                    timeout=self.timeout_seconds,
                )
                if response.status_code == 200:
                    return
                last_error = self._response_error(response)
            except requests.RequestException as exc:
                detail = str(exc).replace(str(self.bot_token), "[redacted]")
                last_error = f"{type(exc).__name__}: {detail}"

            retryable = response is None or response.status_code in RETRYABLE_STATUS_CODES
            if not retryable or attempt == self.max_attempts:
                break

            delay = self._retry_delay(response, attempt)
            logger.warning(
                "Telegram chunk %s/%s failed on attempt %s/%s; retrying in %.1fs",
                index,
                total,
                attempt,
                self.max_attempts,
                delay,
            )
            self._sleep(delay)

        raise TelegramDeliveryError(
            f"Telegram chunk {index}/{total} failed after "
            f"{self.max_attempts} attempt(s): {last_error}"
        )

    def _retry_delay(
        self,
        response: requests.Response | None,
        attempt: int,
    ) -> float:
        if response is not None and response.status_code == 429:
            try:
                retry_after = response.json().get("parameters", {}).get("retry_after")
                if retry_after is not None:
                    return min(float(retry_after), 60.0)
            except (TypeError, ValueError, requests.JSONDecodeError):
                pass
        return min(self.retry_base_seconds * (2 ** (attempt - 1)), 60.0)

    @staticmethod
    def _response_error(response: requests.Response) -> str:
        try:
            description = response.json().get("description")
        except requests.JSONDecodeError:
            description = None
        return f"HTTP {response.status_code}: {description or 'request rejected'}"


notifier = TelegramAlertNotifier()


def send_telegram_alert(message: str) -> bool:
    """Send an HTML-formatted alert or raise TelegramDeliveryError."""
    return notifier.send_alert(message)
