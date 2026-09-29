"""Per-worker alert telemetry with active-worker aggregation in MongoDB."""

import asyncio
import logging
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from threading import Lock
from time import monotonic
from typing import Dict
from uuid import uuid4

from api.database import get_mongo_db


logger = logging.getLogger("newspulse.alert_metrics")


class AlertMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self.worker_id = str(uuid4())
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", Lock()):
            self._started_at = datetime.now(timezone.utc)
            self._started_monotonic = monotonic()
            self._operations: Dict[str, dict] = defaultdict(
                lambda: {
                    "requests": 0,
                    "successes": 0,
                    "not_found": 0,
                    "errors": 0,
                    "total_latency_ms": 0.0,
                    "max_latency_ms": 0.0,
                }
            )

    def observe(self, operation: str, outcome: str, duration_seconds: float) -> None:
        latency_ms = max(duration_seconds, 0) * 1000
        with self._lock:
            metric = self._operations[operation]
            metric["requests"] += 1
            counter = {
                "success": "successes",
                "not_found": "not_found",
                "error": "errors",
            }.get(outcome, "errors")
            metric[counter] += 1
            metric["total_latency_ms"] += latency_ms
            metric["max_latency_ms"] = max(metric["max_latency_ms"], latency_ms)

    def snapshot(self) -> dict:
        with self._lock:
            operations = deepcopy(dict(self._operations))
            started_at = self._started_at
            uptime_seconds = max(monotonic() - self._started_monotonic, 0)

        totals = {"requests": 0, "successes": 0, "not_found": 0, "errors": 0}
        for metric in operations.values():
            requests = metric["requests"]
            metric["average_latency_ms"] = round(
                metric.pop("total_latency_ms") / requests if requests else 0,
                2,
            )
            metric["max_latency_ms"] = round(metric["max_latency_ms"], 2)
            for key in totals:
                totals[key] += metric[key]

        return {
            "scope": "process-local",
            "workers": 1,
            "started_at": started_at,
            "generated_at": datetime.now(timezone.utc),
            "uptime_seconds": round(uptime_seconds, 2),
            "totals": totals,
            "operations": operations,
        }

    def _raw_snapshot(self) -> tuple[datetime, dict]:
        with self._lock:
            return self._started_at, deepcopy(dict(self._operations))

    async def flush_to_mongo(self) -> None:
        started_at, operations = self._raw_snapshot()
        await get_mongo_db().alert_metric_workers.update_one(
            {"_id": self.worker_id},
            {
                "$set": {
                    "started_at": started_at,
                    "last_seen_at": datetime.now(timezone.utc),
                    "operations": operations,
                }
            },
            upsert=True,
        )

    async def shared_snapshot(self) -> dict:
        try:
            await self.flush_to_mongo()
            active_since = datetime.now(timezone.utc) - timedelta(seconds=30)
            cursor = get_mongo_db().alert_metric_workers.find(
                {"last_seen_at": {"$gte": active_since}},
                {"_id": 0},
            )
            workers = await cursor.to_list(length=100)
        except Exception:
            logger.exception("Unable to aggregate alert metrics from MongoDB")
            fallback = self.snapshot()
            fallback["scope"] = "process-local-fallback"
            return fallback

        combined: Dict[str, dict] = defaultdict(
            lambda: {
                "requests": 0,
                "successes": 0,
                "not_found": 0,
                "errors": 0,
                "total_latency_ms": 0.0,
                "max_latency_ms": 0.0,
            }
        )
        for worker in workers:
            for operation, metric in worker.get("operations", {}).items():
                target = combined[operation]
                for key in (
                    "requests",
                    "successes",
                    "not_found",
                    "errors",
                    "total_latency_ms",
                ):
                    target[key] += metric.get(key, 0)
                target["max_latency_ms"] = max(
                    target["max_latency_ms"],
                    metric.get("max_latency_ms", 0),
                )

        totals = {"requests": 0, "successes": 0, "not_found": 0, "errors": 0}
        operations = {}
        for operation, metric in combined.items():
            requests = metric["requests"]
            operations[operation] = {
                "requests": requests,
                "successes": metric["successes"],
                "not_found": metric["not_found"],
                "errors": metric["errors"],
                "average_latency_ms": round(
                    metric["total_latency_ms"] / requests if requests else 0,
                    2,
                ),
                "max_latency_ms": round(metric["max_latency_ms"], 2),
            }
            for key in totals:
                totals[key] += metric[key]

        now = datetime.now(timezone.utc)
        started_at = min(
            (worker.get("started_at", now) for worker in workers),
            default=now,
        )
        return {
            "scope": "shared-mongodb",
            "workers": len(workers),
            "started_at": started_at,
            "generated_at": now,
            "uptime_seconds": round(max((now - started_at).total_seconds(), 0), 2),
            "totals": totals,
            "operations": operations,
        }


async def alert_metrics_flush_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await alert_metrics.flush_to_mongo()
        except Exception:
            logger.exception("Unable to flush alert metrics to MongoDB")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
        except TimeoutError:
            pass


alert_metrics = AlertMetrics()
