import asyncio
import logging
import signal

from api.config import close_ch_client, get_settings
from api.database import close_mongo
from api.logging_config import configure_logging
from api.models.telegram import TelegramUpdate, parse_telegram_query
from api.services.telegram_access import TelegramAccessPolicy
from api.services.telegram_client import TelegramAPIError, TelegramBotClient
from api.services.telegram_queries import TelegramQueryService

logger = logging.getLogger("newspulse.telegram.worker")


class TelegramBotWorker:
    def __init__(
        self,
        client: TelegramBotClient,
        access_policy: TelegramAccessPolicy,
        query_service: TelegramQueryService,
        poll_timeout_seconds: int = 25,
    ) -> None:
        self.client = client
        self.access_policy = access_policy
        self.query_service = query_service
        self.poll_timeout_seconds = max(poll_timeout_seconds, 1)
        self.offset: int | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        await self.client.disable_webhook()
        logger.info("Telegram query worker started")
        while not stop_event.is_set():
            try:
                updates = await self.client.get_updates(
                    self.offset,
                    self.poll_timeout_seconds,
                )
                for update in updates:
                    self.offset = update.update_id + 1
                    await self.handle_update(update)
            except TelegramAPIError:
                logger.exception("Telegram polling failed")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=5)
                except TimeoutError:
                    pass

    async def handle_update(self, update: TelegramUpdate) -> None:
        message = update.message
        if not message or not message.text:
            return
        if message.sender and message.sender.is_bot:
            return

        decision = self.access_policy.check(message)
        if not decision.allowed:
            logger.warning(
                "Telegram query denied reason=%s chat_id=%s user_id=%s",
                decision.reason,
                message.chat.id,
                message.sender.id if message.sender else None,
            )
            return

        request = parse_telegram_query(message.text)
        if request is None:
            return

        try:
            response = await self.query_service.execute(request)
        except Exception:
            logger.exception(
                "Telegram query failed command=%s chat_id=%s",
                request.command,
                message.chat.id,
            )
            await self.client.send_message(
                message.chat.id,
                "Không thể hoàn tất truy vấn lúc này. Vui lòng thử lại sau.",
            )
            return

        await self.client.send_message(message.chat.id, response.text)


async def run_worker() -> None:
    settings = get_settings()
    access_policy = TelegramAccessPolicy(
        settings.telegram_allowed_chat_ids,
        settings.telegram_allowed_user_ids,
    )
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    if not settings.telegram_allowed_chat_ids and not settings.telegram_allowed_user_ids:
        raise RuntimeError("A Telegram chat or user allowlist is required")

    configure_logging()
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop_event.set)

    client = TelegramBotClient(settings.TELEGRAM_BOT_TOKEN)
    worker = TelegramBotWorker(
        client,
        access_policy,
        TelegramQueryService(),
        poll_timeout_seconds=settings.TELEGRAM_POLL_TIMEOUT_SECONDS,
    )
    try:
        await worker.run(stop_event)
    finally:
        await client.close()
        await close_mongo()
        close_ch_client()
        logger.info("Telegram query worker stopped")


if __name__ == "__main__":
    asyncio.run(run_worker())
