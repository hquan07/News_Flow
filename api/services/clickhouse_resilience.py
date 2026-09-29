"""Bounded execution, retry, and circuit breaking for ClickHouse calls."""

import random
import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

from clickhouse_connect.driver.exceptions import (
    InterfaceError,
    OperationalError,
    StreamClosedError,
    StreamFailureError,
)

from api.config import get_ch_client, get_settings
from api.exceptions import DependencyUnavailableError


T = TypeVar("T")
logger = logging.getLogger("newspulse.clickhouse")
RETRYABLE_ERRORS = (
    ConnectionError,
    TimeoutError,
    OSError,
    InterfaceError,
    OperationalError,
    StreamClosedError,
    StreamFailureError,
)


@dataclass
class CircuitSnapshot:
    state: str
    consecutive_failures: int
    opened_at: float | None


class CircuitBreaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._half_open_probe = False

    def before_call(self, threshold: int, recovery_seconds: float) -> None:
        with self._lock:
            if self._opened_at is None:
                return
            if time.monotonic() - self._opened_at < recovery_seconds:
                raise DependencyUnavailableError("clickhouse")
            if self._half_open_probe:
                raise DependencyUnavailableError("clickhouse")
            self._half_open_probe = True

    def success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None
            self._half_open_probe = False

    def failure(self, threshold: int) -> None:
        with self._lock:
            self._consecutive_failures += 1
            self._half_open_probe = False
            if self._consecutive_failures >= threshold:
                self._opened_at = time.monotonic()

    def snapshot(self, recovery_seconds: float) -> CircuitSnapshot:
        with self._lock:
            if self._opened_at is None:
                state = "closed"
            elif time.monotonic() - self._opened_at >= recovery_seconds:
                state = "half-open"
            else:
                state = "open"
            return CircuitSnapshot(
                state=state,
                consecutive_failures=self._consecutive_failures,
                opened_at=self._opened_at,
            )

    def reset(self) -> None:
        self.success()


_circuit = CircuitBreaker()
_bulkhead_lock = threading.Lock()
_bulkhead: threading.BoundedSemaphore | None = None
_bulkhead_size: int | None = None


def _get_bulkhead(max_concurrency: int) -> threading.BoundedSemaphore:
    global _bulkhead, _bulkhead_size
    with _bulkhead_lock:
        if _bulkhead is None or _bulkhead_size != max_concurrency:
            _bulkhead = threading.BoundedSemaphore(max_concurrency)
            _bulkhead_size = max_concurrency
        return _bulkhead


def execute_clickhouse(operation: Callable[[object], T]) -> T:
    settings = get_settings()
    threshold = max(settings.CLICKHOUSE_CIRCUIT_FAILURE_THRESHOLD, 1)
    recovery_seconds = max(settings.CLICKHOUSE_CIRCUIT_RECOVERY_SECONDS, 0.1)
    _circuit.before_call(threshold, recovery_seconds)

    bulkhead = _get_bulkhead(max(settings.CLICKHOUSE_MAX_CONCURRENCY, 1))
    acquired = bulkhead.acquire(
        timeout=max(settings.CLICKHOUSE_ACQUIRE_TIMEOUT_SECONDS, 0.01)
    )
    if not acquired:
        raise DependencyUnavailableError("clickhouse")

    try:
        attempts = max(settings.CLICKHOUSE_QUERY_RETRIES, 1)
        for attempt in range(1, attempts + 1):
            try:
                result = operation(get_ch_client())
                _circuit.success()
                return result
            except RETRYABLE_ERRORS as exc:
                if attempt == attempts:
                    _circuit.failure(threshold)
                    logger.error(
                        "ClickHouse operation failed after %s attempts: %s",
                        attempts,
                        type(exc).__name__,
                    )
                    raise DependencyUnavailableError("clickhouse") from exc
                base_delay = settings.RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
                delay = min(base_delay, settings.RETRY_MAX_DELAY_SECONDS)
                delay += random.uniform(0, max(settings.RETRY_JITTER_SECONDS, 0))
                logger.warning(
                    "Transient ClickHouse failure attempt=%s/%s retry_in=%.3fs error=%s",
                    attempt,
                    attempts,
                    delay,
                    type(exc).__name__,
                )
                time.sleep(delay)
            except Exception:
                # A non-transient server response proves the dependency is
                # reachable, so it must not leave a half-open probe stuck.
                _circuit.success()
                raise
        raise DependencyUnavailableError("clickhouse")
    finally:
        bulkhead.release()


def get_circuit_snapshot() -> CircuitSnapshot:
    settings = get_settings()
    return _circuit.snapshot(settings.CLICKHOUSE_CIRCUIT_RECOVERY_SECONDS)


def reset_clickhouse_resilience() -> None:
    """Reset process-local state for tests and controlled recovery."""
    _circuit.reset()
