from api.services import analytics, clickhouse_resilience
from api.config import get_settings
from api.exceptions import DependencyUnavailableError
from clickhouse_connect.driver.exceptions import ProgrammingError
import pytest


@pytest.fixture(autouse=True)
def reset_resilience_state():
    clickhouse_resilience.reset_clickhouse_resilience()
    yield
    clickhouse_resilience.reset_clickhouse_resilience()


class _Result:
    def named_results(self):
        return iter([{"value": 1}])


class _Client:
    def __init__(self, should_fail):
        self.should_fail = should_fail

    def query(self, *_args, **_kwargs):
        if self.should_fail:
            raise ConnectionError("temporary")
        return _Result()

    def close(self):
        pass


def test_clickhouse_query_retries_transient_failures(monkeypatch):
    attempts = iter([True, True, False])
    monkeypatch.setattr(
        clickhouse_resilience,
        "get_ch_client",
        lambda: _Client(next(attempts)),
    )
    monkeypatch.setattr(clickhouse_resilience.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(clickhouse_resilience.random, "uniform", lambda *_args: 0)
    settings = get_settings()
    monkeypatch.setattr(settings, "CLICKHOUSE_QUERY_RETRIES", 3)

    assert analytics._query("SELECT 1") == [{"value": 1}]


def test_clickhouse_query_raises_after_retries_are_exhausted(monkeypatch):
    monkeypatch.setattr(
        clickhouse_resilience,
        "get_ch_client",
        lambda: _Client(True),
    )
    monkeypatch.setattr(clickhouse_resilience.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(clickhouse_resilience.random, "uniform", lambda *_args: 0)
    settings = get_settings()
    monkeypatch.setattr(settings, "CLICKHOUSE_QUERY_RETRIES", 2)

    with pytest.raises(DependencyUnavailableError) as error:
        analytics._query("SELECT 1")

    assert error.value.dependency == "clickhouse"


def test_clickhouse_does_not_retry_programming_errors(monkeypatch):
    calls = 0
    monkeypatch.setattr(clickhouse_resilience, "get_ch_client", lambda: object())

    def invalid_query(_client):
        nonlocal calls
        calls += 1
        raise ProgrammingError("invalid SQL")

    with pytest.raises(ProgrammingError):
        clickhouse_resilience.execute_clickhouse(invalid_query)

    assert calls == 1


def test_clickhouse_circuit_opens_after_consecutive_failures(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "CLICKHOUSE_QUERY_RETRIES", 1)
    monkeypatch.setattr(settings, "CLICKHOUSE_CIRCUIT_FAILURE_THRESHOLD", 2)
    calls = 0
    monkeypatch.setattr(clickhouse_resilience, "get_ch_client", lambda: object())

    def unavailable(_client):
        nonlocal calls
        calls += 1
        raise ConnectionError("down")

    for _ in range(2):
        with pytest.raises(DependencyUnavailableError):
            clickhouse_resilience.execute_clickhouse(unavailable)

    with pytest.raises(DependencyUnavailableError):
        clickhouse_resilience.execute_clickhouse(unavailable)

    assert calls == 2
    assert clickhouse_resilience.get_circuit_snapshot().state == "open"
