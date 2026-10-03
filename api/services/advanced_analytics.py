"""Bounded, explainable analytics built on warehouse facts."""

import math
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from api.services.analytics import _query
from api.services.event_clustering import _tokens, event_detail


def propagation(keyword: str, days: int = 7) -> dict:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = _query(
        "SELECT toStartOfHour(a.publish_time) AS bucket, a.source, count() AS article_count "
        "FROM newspulse.raw_articles AS a FINAL WHERE a.publish_time >= {since:DateTime} "
        "AND (a.title ILIKE {term:String} OR a.url_hash IN ("
        "SELECT url_hash FROM newspulse.raw_article_keywords WHERE keyword ILIKE {term:String})) "
        "GROUP BY bucket, a.source ORDER BY bucket, a.source LIMIT 1000",
        {"since": since, "term": f"%{keyword}%"},
    )
    if not rows:
        return {"keyword": keyword, "origin": None, "peak": None, "timeline": [], "source_delays_minutes": []}
    first_by_source: dict[str, datetime] = {}
    for row in rows:
        source, bucket = str(row["source"]), row["bucket"]
        if source not in first_by_source or bucket < first_by_source[source]:
            first_by_source[source] = bucket
    origin_source, origin_time = min(first_by_source.items(), key=lambda item: item[1])
    peak = max(rows, key=lambda row: int(row["article_count"]))
    return {
        "keyword": keyword,
        "origin": {"source": origin_source, "time": origin_time},
        "peak": peak,
        "timeline": rows,
        "source_delays_minutes": [
            {"source": source, "delay_minutes": int((first - origin_time).total_seconds() / 60)}
            for source, first in sorted(first_by_source.items(), key=lambda item: item[1])
        ],
    }


def source_divergence(event_id: str) -> dict:
    event = event_detail(event_id, days=30)
    by_source: dict[str, set[str]] = {}
    ids = []
    for article in event["articles"]:
        source = str(article["source"])
        by_source.setdefault(source, set()).update(_tokens(str(article["title"])))
        ids.append(str(article["article_id"]))
    sentiment_rows = _query(
        "SELECT a.source, round(avg(s.sentiment_score), 3) AS avg_sentiment "
        "FROM newspulse.raw_articles AS a FINAL INNER JOIN ("
        "SELECT url_hash, argMax(sentiment_score, loaded_at) AS sentiment_score "
        "FROM newspulse.raw_article_sentiment WHERE url_hash IN {ids:Array(String)} GROUP BY url_hash"
        ") AS s USING (url_hash) WHERE a.url_hash IN {ids:Array(String)} GROUP BY a.source",
        {"ids": ids},
    ) if ids else []
    sentiment = {str(row["source"]): float(row["avg_sentiment"]) for row in sentiment_rows}
    sources = sorted(by_source)
    comparisons = []
    for index, left in enumerate(sources):
        for right in sources[index + 1:]:
            union = by_source[left] | by_source[right]
            overlap = len(by_source[left] & by_source[right]) / len(union) if union else 1.0
            comparisons.append({
                "source_a": left, "source_b": right,
                "framing_distance": round(1 - overlap, 3),
                "sentiment_gap": round(abs(sentiment.get(left, 0) - sentiment.get(right, 0)), 3),
            })
    return {
        "event_id": event_id, "title": event["title"],
        "sources": [{"source": source, "avg_sentiment": sentiment.get(source), "title_terms": sorted(by_source[source])[:20]} for source in sources],
        "comparisons": comparisons,
        "note": "Framing distance compares title vocabulary; it does not determine editorial bias.",
    }


def nlp_explanation(article_id: str) -> dict:
    rows = _query(
        "SELECT a.url_hash AS article_id, a.title, a.source, a.content, "
        "ifNull(s.sentiment_score, toFloat32(0)) AS sentiment_score, "
        "ifNull(s.sentiment_label, 'neutral') AS sentiment_label "
        "FROM newspulse.raw_articles AS a FINAL LEFT JOIN ("
        "SELECT url_hash, argMax(sentiment_score, loaded_at) AS sentiment_score, "
        "argMax(sentiment_label, loaded_at) AS sentiment_label FROM newspulse.raw_article_sentiment GROUP BY url_hash"
        ") AS s USING (url_hash) WHERE a.url_hash = {article_id:String} LIMIT 1",
        {"article_id": article_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Article not found")
    row = rows[0]
    keywords = _query(
        "SELECT keyword, round(max(score), 3) AS score FROM newspulse.raw_article_keywords "
        "WHERE url_hash = {article_id:String} GROUP BY keyword ORDER BY score DESC LIMIT 10",
        {"article_id": article_id},
    )
    entities = _query(
        "SELECT entity AS name, entity_type AS type, count() AS mentions FROM newspulse.raw_article_entities "
        "WHERE url_hash = {article_id:String} GROUP BY entity, entity_type ORDER BY mentions DESC LIMIT 10",
        {"article_id": article_id},
    )
    content = " ".join(str(row.get("content", "")).split())
    evidence = []
    for keyword in keywords[:3]:
        term = str(keyword["keyword"])
        position = content.casefold().find(term.casefold())
        if position >= 0:
            evidence.append(content[max(0, position - 80):position + len(term) + 120])
    return {
        "article": {key: row[key] for key in ("article_id", "title", "source", "sentiment_score", "sentiment_label")},
        "keywords": keywords, "entities": entities, "evidence": evidence,
        "explanation": f"Sentiment label is derived from score {float(row['sentiment_score']):.3f}; keywords and entities are ranked from the NLP enrichment tables.",
    }


def forecast_series(values: list[float], horizon: int) -> list[dict]:
    if not values:
        return []
    window = values[-min(24, len(values)):]
    n = len(window)
    x_mean = (n - 1) / 2
    y_mean = sum(window) / n
    denominator = sum((x - x_mean) ** 2 for x in range(n))
    slope = sum((x - x_mean) * (value - y_mean) for x, value in enumerate(window)) / denominator if denominator else 0.0
    fitted = [y_mean + slope * (x - x_mean) for x in range(n)]
    error = math.sqrt(sum((value - estimate) ** 2 for value, estimate in zip(window, fitted)) / n)
    return [
        {
            "offset": offset,
            "value": round(max(0, y_mean + slope * (n - 1 + offset - x_mean)), 2),
            "lower": round(max(0, y_mean + slope * (n - 1 + offset - x_mean) - 1.96 * error), 2),
            "upper": round(max(0, y_mean + slope * (n - 1 + offset - x_mean) + 1.96 * error), 2),
        }
        for offset in range(1, horizon + 1)
    ]


def forecast(metric: str = "articles", horizon: int = 6) -> dict:
    if metric == "articles":
        rows = _query(
            "SELECT toStartOfHour(publish_time) AS bucket, toFloat64(count()) AS value "
            "FROM newspulse.raw_articles FINAL WHERE publish_time >= now() - INTERVAL 7 DAY "
            "GROUP BY bucket ORDER BY bucket"
        )
    else:
        rows = _query(
            "SELECT toStartOfHour(loaded_at) AS bucket, toFloat64(avg(sentiment_score)) AS value "
            "FROM newspulse.raw_article_sentiment WHERE loaded_at >= now() - INTERVAL 7 DAY "
            "GROUP BY bucket ORDER BY bucket"
        )
    predicted = forecast_series([float(row["value"]) for row in rows], horizon)
    last_bucket = rows[-1]["bucket"] if rows else datetime.now(timezone.utc)
    for point in predicted:
        point["bucket"] = last_bucket + timedelta(hours=point["offset"])
    return {"metric": metric, "history": rows[-48:], "forecast": predicted, "method": "24-point linear trend with residual confidence band"}
