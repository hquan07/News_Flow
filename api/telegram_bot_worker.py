import asyncio
import logging
import signal
import time

from api.config import close_ch_client, get_settings
from api.database import close_mongo, get_mongo_db
from api.logging_config import configure_logging
from api.models.telegram import TelegramUpdate, parse_telegram_query
from api.services.telegram_access import TelegramAccessPolicy
from api.services.telegram_client import TelegramAPIError, TelegramBotClient
from api.services.telegram_queries import TelegramQueryService
from api.services.telegram_runtime import TelegramAuditStore, TelegramRateLimiter

logger = logging.getLogger("newspulse.telegram.worker")

BOT_COMMANDS = [
    {"command": "alerts", "description": "Cảnh báo volume spike"},
    {"command": "trend", "description": "Từ khóa nổi bật"},
    {"command": "source", "description": "Thống kê theo nguồn"},
    {"command": "report", "description": "Báo cáo tổng quan"},
    {"command": "status", "description": "Trạng thái hệ thống"},
    {"command": "help", "description": "Hướng dẫn tra cứu"},
]


class TelegramBotWorker:
    def __init__(
        self,
        client: TelegramBotClient,
        access_policy: TelegramAccessPolicy,
        query_service: TelegramQueryService,
        poll_timeout_seconds: int = 25,
        rate_limiter: TelegramRateLimiter | None = None,
        audit_store: TelegramAuditStore | None = None,
    ) -> None:
        self.client = client
        self.access_policy = access_policy
        self.query_service = query_service
        self.poll_timeout_seconds = max(poll_timeout_seconds, 1)
        self.rate_limiter = rate_limiter
        self.audit_store = audit_store
        self.offset: int | None = None

    async def run(self, stop_event: asyncio.Event) -> None:
        if self.audit_store:
            await self.audit_store.ensure_indexes()
            self.offset = await self.audit_store.load_offset()
        await self.client.disable_webhook(drop_pending_updates=self.offset is None)
        await self.client.set_commands(BOT_COMMANDS)
        logger.info("Telegram query worker started")
        while not stop_event.is_set():
            try:
                updates = await self.client.get_updates(
                    self.offset,
                    self.poll_timeout_seconds,
                )
                for update in updates:
                    self.offset = update.update_id + 1
                    try:
                        await self.handle_update(update)
                    finally:
                        if self.audit_store:
                            await self.audit_store.save_offset(self.offset)
            except TelegramAPIError:
                logger.exception("Telegram polling failed")
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=5)
                except TimeoutError:
                    pass

    async def handle_update(self, update: TelegramUpdate) -> None:
        started = time.monotonic()
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
            await self._record(
                update,
                command=None,
                outcome="denied",
                reason=decision.reason,
                started=started,
            )
            return

        rate_key = message.sender.id if message.sender else message.chat.id
        if self.rate_limiter and not self.rate_limiter.allow(rate_key):
            await self.client.send_message(
                message.chat.id,
                "Bạn gửi truy vấn quá nhanh. Vui lòng thử lại sau ít phút.",
            )
            await self._record(
                update,
                command=None,
                outcome="rate_limited",
                reason="per_minute_limit",
                started=started,
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
            await self._record(
                update,
                command=request.command,
                outcome="error",
                reason="query_failed",
                started=started,
            )
            return

        await self.client.send_message(message.chat.id, response.text)
        await self._record(
            update,
            command=response.command,
            outcome="success",
            reason=None,
            started=started,
        )

    async def _record(
        self,
        update: TelegramUpdate,
        *,
        command: str | None,
        outcome: str,
        reason: str | None,
        started: float,
    ) -> None:
        if not self.audit_store:
            return
        try:
            await self.audit_store.record(
                update,
                command=command,
                outcome=outcome,
                reason=reason,
                latency_ms=(time.monotonic() - started) * 1000,
            )
        except Exception:
            logger.exception("Unable to persist Telegram query audit event")


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
    audit_store = TelegramAuditStore(
        get_mongo_db(),
        retention_days=settings.TELEGRAM_AUDIT_RETENTION_DAYS,
    )
    worker = TelegramBotWorker(
        client,
        access_policy,
        TelegramQueryService(),
        poll_timeout_seconds=settings.TELEGRAM_POLL_TIMEOUT_SECONDS,
        rate_limiter=TelegramRateLimiter(
            settings.TELEGRAM_RATE_LIMIT_PER_MINUTE
        ),
        audit_store=audit_store,
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
