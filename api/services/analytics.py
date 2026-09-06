from typing import Optional
from api.config import get_ch_client

def _resolve_time_range(time_range, date_column="publish_time"):
    mapping = {
        "today": f"{date_column} >= now() - INTERVAL 24 HOUR",
        "yesterday": f"{date_column} >= now() - INTERVAL 48 HOUR AND {date_column} < now() - INTERVAL 24 HOUR",
        "7d": f"{date_column} >= now() - INTERVAL 7 DAY",
        "30d": f"{date_column} >= now() - INTERVAL 30 DAY",
        "90d": f"{date_column} >= now() - INTERVAL 90 DAY",
    }
    return mapping.get(time_range, mapping["7d"])

def _query(sql, params=None):
    client = get_ch_client()
    try:
        # Use simple parameters if needed
        # In clickhouse-connect, parameters are passed via parameters dict
        result = client.query(sql, parameters=params or {})
        return list(result.named_results())
    except Exception as e:
        print(f"ClickHouse Query Error: {e}")
        return []

def _query_one(sql, params=None):
    results = _query(sql, params)
    return results[0] if results else {}


def get_overview(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
    if category:
        where += " AND category = {category:String}"
        params["category"] = category
    return _query(
        f"SELECT toDate(publish_time) as date, source, category, count() as article_count, avg(word_count) as avg_word_count, avg(crawl_latency_minutes) as avg_crawl_latency "
        f"FROM newspulse.raw_articles WHERE {where} "
        f"GROUP BY date, source, category ORDER BY date DESC, source, category",
        params,
    )


def get_hourly_distribution(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
    if category:
        where += " AND category = {category:String}"
        params["category"] = category
        
    return _query(
        f"SELECT publish_hour AS hour, source, count() AS total_count "
        f"FROM newspulse.raw_articles "
        f"WHERE {where} AND publish_hour IS NOT NULL "
        f"GROUP BY hour, source ORDER BY hour",
        params,
    )


def get_trending_keywords(time_range="7d", limit=20, source=None, category=None):
    # Simple mock trending for now based on keywords in raw_article_keywords
    where = _resolve_time_range(time_range, "loaded_at")
    return _query(
        f"SELECT keyword, count() as mention_count "
        f"FROM newspulse.raw_article_keywords "
        f"WHERE {where} "
        f"GROUP BY keyword ORDER BY mention_count DESC LIMIT {limit}"
    )


def get_keyword_timeline(keyword=None, days=30):
    return []

def get_co_occurrences(keyword=None, limit=20):
    return []

def get_source_comparison(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
    if category:
        where += " AND category = {category:String}"
        params["category"] = category
        
    return _query(
        f"SELECT source, count() AS total_articles, "
        f"round(avg(publish_hour),1) AS avg_publish_hour, "
        f"any(category) AS top_category, "
        f"round(avg(word_count),1) AS avg_word_count "
        f"FROM newspulse.raw_articles WHERE {where} "
        f"GROUP BY source ORDER BY total_articles DESC",
        params
    )


def get_alerts(threshold=2.0, limit=10):
    # Using a simple moving average check on raw_articles
    return _query(
        f"WITH hourly AS ("
        f"  SELECT toStartOfHour(publish_time) AS hour_slot, count() AS cnt "
        f"  FROM newspulse.raw_articles "
        f"  WHERE publish_time >= now() - INTERVAL 7 DAY GROUP BY hour_slot"
        f"), stats AS ("
        f"  SELECT avg(cnt) AS avg_cnt, stddevPop(cnt) AS std_cnt FROM hourly"
        f") "
        f"SELECT h.hour_slot, h.cnt AS article_count, toInt32(s.avg_cnt) AS avg_count "
        f"FROM hourly h, stats s "
        f"WHERE h.cnt > s.avg_cnt + {threshold} * s.std_cnt ORDER BY h.hour_slot DESC LIMIT {limit}"
    )


def get_entity_stats(time_range="7d", entity_type=None, limit=20, source=None, category=None):
    where = _resolve_time_range(time_range, "loaded_at")
    params = {}
    if entity_type:
        where += " AND entity_type = {entity_type:String}"
        params["entity_type"] = entity_type
        
    return _query(
        f"SELECT entity, entity_type, "
        f"uniq(url_hash) AS article_count, "
        f"count() AS mention_count "
        f"FROM newspulse.raw_article_entities "
        f"WHERE {where} "
        f"GROUP BY entity, entity_type "
        f"ORDER BY article_count DESC LIMIT {limit}",
        params,
    )

def get_entity_timeline(entity=None, days=30):
    return []

def get_entities_by_category(category=None, limit=20):
    return []

def get_sentiment_distribution(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "loaded_at")
    params = {}
    rows = _query(
        f"SELECT sentiment_label, count() AS count "
        f"FROM newspulse.raw_article_sentiment "
        f"WHERE {where} AND sentiment_label != '' "
        f"GROUP BY sentiment_label",
        params,
    )
    for row in rows:
        row["sentiment_label"] = row["sentiment_label"].capitalize()
    return rows

def get_entity_network(time_range="7d", limit=50):
    return {"nodes": [], "links": []}
def get_sentiment_timeline(time_range="7d"):
    where = _resolve_time_range(time_range, "loaded_at")
    sql = f"""
        SELECT
            toStartOfHour(loaded_at) AS time,
            sentiment_label,
            count() AS count
        FROM newspulse.raw_article_sentiment
        WHERE {where} AND sentiment_label != ''
        GROUP BY time, sentiment_label
        ORDER BY time ASC
    """
    rows = _query(sql)
    
    # Pivot logic: transform into {time: "2026-09-06T12:00:00", Positive: 10, Negative: 2, Neutral: 5}
    timeline = {}
    for row in rows:
        t = row["time"].isoformat()
        if t not in timeline:
            timeline[t] = {"time": t, "Positive": 0, "Negative": 0, "Neutral": 0}
        
        # Mapping sentiment labels to standardized keys
        label = row["sentiment_label"].capitalize()
        if label in ["Positive", "Negative", "Neutral"]:
            timeline[t][label] = row["count"]
            
    return list(timeline.values())

def get_sentiment_by_source(time_range="7d"):
    where = _resolve_time_range(time_range, "publish_time")
    # We need to join with raw_articles to get the source
    sql = f"""
        SELECT
            a.source AS source,
            s.sentiment_label AS sentiment,
            count() AS count
        FROM newspulse.raw_article_sentiment s
        JOIN newspulse.raw_articles a ON s.url_hash = a.url_hash
        WHERE {where} AND s.sentiment_label != ''
        GROUP BY source, sentiment
    """
    rows = _query(sql)
    
    sources = {}
    for row in rows:
        src = row["source"]
        if src not in sources:
            sources[src] = {"source": src, "Positive": 0, "Negative": 0, "Neutral": 0}
            
        label = row["sentiment"].capitalize()
        if label in ["Positive", "Negative", "Neutral"]:
            sources[src][label] = row["count"]
            
    return list(sources.values())
