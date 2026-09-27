from api.services import analytics
from api.config import get_settings


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
    monkeypatch.setattr(analytics, "get_ch_client", lambda: _Client(next(attempts)))
    monkeypatch.setattr(analytics.time, "sleep", lambda _seconds: None)
    settings = get_settings()
    monkeypatch.setattr(settings, "CLICKHOUSE_QUERY_RETRIES", 3)

    assert analytics._query("SELECT 1") == [{"value": 1}]
