import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from api.models.telegram import TelegramUpdate


class TelegramRateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60,
        clock=time.monotonic,
    ) -> None:
        self.limit = max(limit, 1)
        self.window_seconds = max(window_seconds, 1)
        self.clock = clock
        self.events: dict[int, deque[float]] = defaultdict(deque)

    def allow(self, key: int) -> bool:
        now = self.clock()
        events = self.events[key]
        cutoff = now - self.window_seconds
        while events and events[0] <= cutoff:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True


class TelegramAuditStore:
    def __init__(self, database, retention_days: int = 90) -> None:
        self.audit = database.telegram_bot_audit
        self.state = database.telegram_bot_state
        self.retention_seconds = max(retention_days, 1) * 24 * 60 * 60

    async def ensure_indexes(self) -> None:
        await self.audit.create_index(
            "created_at",
            expireAfterSeconds=self.retention_seconds,
            name="telegram_audit_ttl",
        )
        await self.audit.create_index(
            [("chat_id", 1), ("created_at", -1)],
            name="telegram_audit_chat_time",
        )

    async def load_offset(self) -> int | None:
        document = await self.state.find_one({"_id": "polling"})
        return document.get("offset") if document else None

    async def save_offset(self, offset: int) -> None:
        await self.state.update_one(
            {"_id": "polling"},
            {
                "$set": {
                    "offset": offset,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    async def record(
        self,
        update: TelegramUpdate,
        *,
        command: str | None,
        outcome: str,
        latency_ms: float,
        reason: str | None = None,
    ) -> None:
        message = update.message
        await self.audit.insert_one(
            {
                "update_id": update.update_id,
                "chat_id": message.chat.id if message else None,
                "user_id": (
                    message.sender.id
                    if message and message.sender
                    else None
                ),
                "command": command,
                "outcome": outcome,
                "reason": reason,
                "latency_ms": round(latency_ms, 1),
                "created_at": datetime.now(timezone.utc),
            }
        )
