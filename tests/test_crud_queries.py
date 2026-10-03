from datetime import datetime

from api.services import crud


class _Result:
    def __init__(self, rows=None, first_row=None):
        self._rows = rows or []
        self.first_row = first_row

    def named_results(self):
        return iter(self._rows)


class _Client:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []
        self.closed = False

    def query(self, sql, parameters=None):
        self.calls.append((sql, parameters or {}))
        return next(self.results)

    def close(self):
        self.closed = True


def test_article_filters_and_sentiment_are_applied(monkeypatch):
    client = _Client([
        _Result(first_row=(1,)),
        _Result(rows=[{
            "article_id": "hash-1",
            "title": "AI tại Việt Nam",
            "sentiment_score": 0.75,
            "sentiment_label": "positive",
        }]),
    ])
    monkeypatch.setattr(crud, "execute_clickhouse", lambda operation: operation(client))

    response = crud.get_articles(
        page=2,
        page_size=10,
        entity="OpenAI",
        keyword="trí tuệ nhân tạo",
    )

    count_sql, count_params = client.calls[0]
    data_sql, data_params = client.calls[1]
    assert "raw_articles FINAL" in count_sql
    assert "raw_article_entities" in count_sql
    assert "raw_article_keywords" in count_sql
    assert count_params == {"entity": "OpenAI", "keyword": "trí tuệ nhân tạo"}
    assert "argMax(sentiment_score, loaded_at)" in data_sql
    assert "LIMIT {page_size:UInt32} OFFSET {offset:UInt64}" in data_sql
    assert data_params["page_size"] == 10
    assert data_params["offset"] == 10
    assert response["data"][0]["sentiment_score"] == 0.75
    assert client.closed is False


def test_sentiment_filter_joins_latest_sentiment_in_count_and_data(monkeypatch):
    client = _Client([
        _Result(first_row=(1,)),
        _Result(rows=[{
            "article_id": "hash-positive",
            "title": "Positive article",
            "sentiment_score": 0.8,
            "sentiment_label": "positive",
        }]),
    ])
    monkeypatch.setattr(crud, "execute_clickhouse", lambda operation: operation(client))

    response = crud.get_articles(sentiment="positive")

    count_sql, count_params = client.calls[0]
    data_sql, data_params = client.calls[1]
    for sql in (count_sql, data_sql):
        assert "raw_article_sentiment" in sql
        assert "argMax(sentiment_label, loaded_at)" in sql
        assert "ifNull(sentiment.sentiment_label, 'neutral') = {sentiment:String}" in sql
    assert count_params == {"sentiment": "positive"}
    assert data_params["sentiment"] == "positive"
    assert response["total"] == 1
    assert response["data"][0]["sentiment_label"] == "positive"


def test_article_detail_deduplicates_enrichment_rows(monkeypatch):
    client = _Client([
        _Result(rows=[{"article_id": "hash-1", "sentiment_score": -0.25}]),
        _Result(rows=[{"keyword": "AI"}]),
        _Result(rows=[{"entity_name": "OpenAI", "entity_type": "ORG"}]),
    ])
    monkeypatch.setattr(crud, "execute_clickhouse", lambda operation: operation(client))

    article = crud.get_article_detail("hash-1")

    assert article["sentiment_score"] == -0.25
    assert article["keywords"] == ["AI"]
    assert article["entities"] == [{"entity_name": "OpenAI", "entity_type": "ORG"}]
    assert "GROUP BY keyword" in client.calls[1][0]
    assert "GROUP BY entity, entity_type" in client.calls[2][0]
    assert client.closed is False


def test_article_filters_support_alert_time_window():
    published_from = datetime(2026, 9, 28, 10, 0)
    published_to = datetime(2026, 9, 28, 11, 0)

    where, params = crud._build_article_filters(
        published_from=published_from,
        published_to=published_to,
    )

    assert "publish_time >= {published_from:DateTime}" in where
    assert "publish_time < {published_to:DateTime}" in where
    assert params == {
        "published_from": published_from,
        "published_to": published_to,
    }
