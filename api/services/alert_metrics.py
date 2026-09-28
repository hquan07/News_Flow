"""Lightweight process-local telemetry for alert workflows.

The service deliberately has no external dependency so it can be used in the
standalone deployment. Counters reset whenever the API process restarts and
are exposed only through an admin-protected endpoint.
"""

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from typing import Dict


class AlertMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
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
            "started_at": started_at,
            "generated_at": datetime.now(timezone.utc),
            "uptime_seconds": round(uptime_seconds, 2),
            "totals": totals,
            "operations": operations,
        }


alert_metrics = AlertMetrics()
