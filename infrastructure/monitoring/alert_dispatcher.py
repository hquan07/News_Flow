import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from uuid import uuid4

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError

from .telegram_alert import TelegramAlertNotifier, notifier

logger = logging.getLogger(__name__)

SEVERITY_ICONS = {
    "info": "ℹ️",
    "warning": "⚠️",
    "critical": "🚨",
}


@dataclass(frozen=True)
class AlertEvent:
    alert_id: str
    alert_type: str
    severity: str
    title: str
    details: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.severity not in SEVERITY_ICONS:
            raise ValueError(f"Unsupported alert severity: {self.severity}")


class MongoAlertCooldownStore:
    """Atomically claim alerts so concurrent DAG runs cannot send duplicates."""

    def __init__(self, collection, cooldown_minutes: int = 120) -> None:
        if cooldown_minutes < 1:
            raise ValueError("cooldown_minutes must be at least 1")
        self.collection = collection
        self.cooldown = timedelta(minutes=cooldown_minutes)

    def claim(self, alert_id: str) -> str | None:
        now = datetime.now(timezone.utc)
        claim_id = uuid4().hex
        try:
            document = self.collection.find_one_and_update(
                {
                    "_id": alert_id,
                    "$or": [
                        {"next_allowed_at": {"$exists": False}},
                        {"next_allowed_at": {"$lte": now}},
                    ],
                },
                {
                    "$set": {
                        "claim_id": claim_id,
                        "status": "pending",
                        "claimed_at": now,
                        "next_allowed_at": now + self.cooldown,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            return None

        if document and document.get("claim_id") == claim_id:
            return claim_id
        return None

    def mark_sent(self, alert_id: str, claim_id: str) -> None:
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": alert_id, "claim_id": claim_id},
            {
                "$set": {"status": "sent", "sent_at": now},
                "$unset": {"claim_id": ""},
            },
        )

    def release(self, alert_id: str, claim_id: str) -> None:
        now = datetime.now(timezone.utc)
        self.collection.update_one(
            {"_id": alert_id, "claim_id": claim_id},
            {
                "$set": {
                    "status": "failed",
                    "failed_at": now,
                    "next_allowed_at": now,
                },
                "$unset": {"claim_id": ""},
            },
        )


class TelegramAlertDispatcher:
    def __init__(
        self,
        cooldown_store: MongoAlertCooldownStore,
        telegram_notifier: TelegramAlertNotifier,
        dashboard_url: str | None = None,
    ) -> None:
        self.cooldown_store = cooldown_store
        self.telegram_notifier = telegram_notifier
        self.dashboard_url = dashboard_url

    def dispatch(self, events: list[AlertEvent]) -> int:
        claimed: list[tuple[AlertEvent, str]] = []
        for event in events:
            claim_id = self.cooldown_store.claim(event.alert_id)
            if claim_id:
                claimed.append((event, claim_id))

        if not claimed:
            logger.info("All %s Telegram alert(s) are inside cooldown.", len(events))
            return 0

        try:
            message = format_alert_digest(
                [event for event, _claim_id in claimed],
                dashboard_url=self.dashboard_url,
            )
            self.telegram_notifier.send_alert(message)
        except Exception:
            for event, claim_id in claimed:
                self.cooldown_store.release(event.alert_id, claim_id)
            raise

        for event, claim_id in claimed:
            self.cooldown_store.mark_sent(event.alert_id, claim_id)
        return len(claimed)


def format_alert_digest(
    events: list[AlertEvent],
    dashboard_url: str | None = None,
) -> str:
    lines = ["🚨 <b>NEWSPULSE ALERT REPORT</b>"]
    for event in events:
        icon = SEVERITY_ICONS[event.severity]
        lines.extend(
            [
                "",
                f"{icon} <b>{escape(event.title)}</b>",
                f"<i>{escape(event.severity.upper())} · {escape(event.alert_type)}</i>",
            ]
        )
        lines.extend(f"• {escape(detail)}" for detail in event.details)

    if dashboard_url:
        safe_url = escape(dashboard_url, quote=True)
        lines.extend(["", f'🔎 <a href="{safe_url}">Xem chi tiết trên dashboard</a>'])
    return "\n".join(lines)


def send_telegram_events(events: list[AlertEvent]) -> int:
    if not events:
        return 0

    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    mongo_db = os.getenv("MONGO_DB", "newspulse")
    cooldown_minutes = int(os.getenv("TELEGRAM_ALERT_COOLDOWN_MINUTES", "120"))
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    try:
        store = MongoAlertCooldownStore(
            client[mongo_db].telegram_alert_deliveries,
            cooldown_minutes=cooldown_minutes,
        )
        dispatcher = TelegramAlertDispatcher(
            store,
            notifier,
            dashboard_url=os.getenv("ALERT_DASHBOARD_URL"),
        )
        return dispatcher.dispatch(events)
    finally:
        client.close()
