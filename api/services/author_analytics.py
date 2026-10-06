"""Author-level analytics for official news articles."""

from typing import Optional

from api.services.clickhouse_resilience import execute_clickhouse


_TIME_CONDITIONS = {
    "today": "toDate(publish_time) = today()",
    "7d": "publish_time >= now() - INTERVAL 7 DAY",
    "30d": "publish_time >= now() - INTERVAL 30 DAY",
    "all": "1 = 1",
}

_LATEST_SENTIMENT_JOIN = """
    LEFT JOIN (
        SELECT
            url_hash,
            argMax(sentiment_score, loaded_at) AS sentiment_score,
            argMax(sentiment_label, loaded_at) AS sentiment_label
        FROM newspulse.raw_article_sentiment
        GROUP BY url_hash
    ) AS sentiment USING (url_hash)
"""


def get_author_analytics(
    *,
    time_range: str = "all",
    source: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """Return coverage and ranked author metrics from the article fact stream."""
    time_condition = _TIME_CONDITIONS[time_range]
    scope_conditions = [time_condition]
    params: dict = {"limit": limit}
    if source:
        scope_conditions.append("source = {source:String}")
        params["source"] = source

    scope_where = " AND ".join(scope_conditions)
    named_author = "lengthUTF8(trimBoth(author)) > 0"

    summary_sql = f"""
        SELECT
            count() AS total_articles,
            countIf({named_author}) AS authored_articles,
            uniqExactIf(
                tuple(lowerUTF8(trimBoth(author)), source),
                {named_author}
            ) AS total_authors
        FROM newspulse.raw_articles FINAL
        WHERE {scope_where}
    """
    summary_rows = execute_clickhouse(
        lambda client: list(
            client.query(summary_sql, parameters=params).named_results()
        )
    )
    summary = summary_rows[0] if summary_rows else {}

    authors_sql = f"""
        SELECT
            trimBoth(author) AS author,
            source,
            uniqExact(url_hash) AS article_count,
            topK(1)(category)[1] AS top_category,
            min(publish_time) AS first_published_at,
            max(publish_time) AS last_published_at,
            countIf(sentiment.sentiment_label = 'positive') AS positive_count,
            countIf(sentiment.sentiment_label = 'neutral') AS neutral_count,
            countIf(sentiment.sentiment_label = 'negative') AS negative_count,
            countIf(notEmpty(ifNull(sentiment.sentiment_label, ''))) AS analyzed_count,
            if(
                analyzed_count > 0,
                round(avgIf(
                    sentiment.sentiment_score,
                    notEmpty(ifNull(sentiment.sentiment_label, ''))
                ), 3),
                NULL
            ) AS avg_sentiment
        FROM newspulse.raw_articles FINAL
        {_LATEST_SENTIMENT_JOIN}
        WHERE {scope_where} AND {named_author}
        GROUP BY author, source
        ORDER BY article_count DESC, last_published_at DESC, author ASC
        LIMIT {{limit:UInt32}}
    """
    authors = execute_clickhouse(
        lambda client: list(
            client.query(authors_sql, parameters=params).named_results()
        )
    )

    total_articles = int(summary.get("total_articles", 0))
    authored_articles = int(summary.get("authored_articles", 0))
    unattributed_articles = max(total_articles - authored_articles, 0)

    return {
        "summary": {
            "total_authors": int(summary.get("total_authors", 0)),
            "total_articles": total_articles,
            "authored_articles": authored_articles,
            "unattributed_articles": unattributed_articles,
            "coverage_pct": round(
                authored_articles / total_articles * 100, 1
            ) if total_articles else 0.0,
        },
        "authors": authors,
        "time_range": time_range,
        "source": source,
    }
