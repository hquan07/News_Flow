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
        result = client.query(sql, parameters=params or {})
        return list(result.named_results())
    except Exception as e:
        print(f"ClickHouse Query Error: {e}")
        return []


def _query_one(sql, params=None):
    results = _query(sql, params)
    return results[0] if results else {}


def _append_filters(where, params, source=None, category=None):
    """Append optional source/category filters to a WHERE clause."""
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
    if category:
        where += " AND category = {category:String}"
        params["category"] = category
    return where, params


def get_overview(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    where, params = _append_filters(where, params, source, category)
    return _query(
        f"SELECT toDate(publish_time) as date, source, category, "
        f"count() as article_count, avg(word_count) as avg_word_count, "
        f"avg(crawl_latency_minutes) as avg_crawl_latency "
        f"FROM newspulse.raw_articles WHERE {where} "
        f"GROUP BY date, source, category ORDER BY date DESC, source, category",
        params,
    )


def get_hourly_distribution(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    where, params = _append_filters(where, params, source, category)
    return _query(
        f"SELECT publish_hour AS hour, source, count() AS total_count "
        f"FROM newspulse.raw_articles "
        f"WHERE {where} AND publish_hour IS NOT NULL "
        f"GROUP BY hour, source ORDER BY hour",
        params,
    )


def get_trending_keywords(time_range="7d", limit=20, source=None, category=None):
    where = _resolve_time_range(time_range, "loaded_at")
    return _query(
        f"SELECT keyword, count() as count "
        f"FROM newspulse.raw_article_keywords "
        f"WHERE {where} "
        f"GROUP BY keyword ORDER BY count DESC LIMIT {limit}"
    )


def get_source_comparison(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "publish_time")
    params = {}
    where, params = _append_filters(where, params, source, category)
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
    """Detect anomalous spikes using z-score on hourly article counts."""
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
        f"SELECT entity AS entity_name, entity_type, "
        f"uniq(url_hash) AS article_count, "
        f"count() AS mention_count "
        f"FROM newspulse.raw_article_entities "
        f"WHERE {where} "
        f"GROUP BY entity, entity_type "
        f"ORDER BY article_count DESC LIMIT {limit}",
        params,
    )


def get_sentiment_distribution(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "loaded_at")
    rows = _query(
        f"SELECT sentiment_label, count() AS count "
        f"FROM newspulse.raw_article_sentiment "
        f"WHERE {where} AND sentiment_label != '' "
        f"GROUP BY sentiment_label",
    )
    for row in rows:
        row["sentiment_label"] = row["sentiment_label"].capitalize()
    return rows


def get_sentiment_timeline(time_range="7d"):
    where = _resolve_time_range(time_range, "loaded_at")
    rows = _query(f"""
        SELECT toStartOfHour(loaded_at) AS time, sentiment_label, count() AS count
        FROM newspulse.raw_article_sentiment
        WHERE {where} AND sentiment_label != ''
        GROUP BY time, sentiment_label
        ORDER BY time ASC
    """)

    timeline = {}
    for row in rows:
        t = row["time"].isoformat()
        if t not in timeline:
            timeline[t] = {"time": t, "Positive": 0, "Negative": 0, "Neutral": 0}
        label = row["sentiment_label"].capitalize()
        if label in ("Positive", "Negative", "Neutral"):
            timeline[t][label] = row["count"]
    return list(timeline.values())


def get_sentiment_by_source(time_range="7d"):
    where = _resolve_time_range(time_range, "publish_time")
    rows = _query(f"""
        SELECT a.source AS source, s.sentiment_label AS sentiment, count() AS count
        FROM newspulse.raw_article_sentiment s
        JOIN newspulse.raw_articles a ON s.url_hash = a.url_hash
        WHERE {where} AND s.sentiment_label != ''
        GROUP BY source, sentiment
    """)

    sources = {}
    for row in rows:
        src = row["source"]
        if src not in sources:
            sources[src] = {"source": src, "Positive": 0, "Negative": 0, "Neutral": 0}
        label = row["sentiment"].capitalize()
        if label in ("Positive", "Negative", "Neutral"):
            sources[src][label] = row["count"]
    return list(sources.values())


def get_entity_type_distribution(time_range="7d"):
    where = _resolve_time_range(time_range, "loaded_at")
    return _query(
        f"SELECT entity_type, count() AS count "
        f"FROM newspulse.raw_article_entities "
        f"WHERE {where} "
        f"GROUP BY entity_type "
        f"ORDER BY count DESC"
    )


def get_entity_sentiment(time_range="7d", limit=15):
    where = _resolve_time_range(time_range, "e.loaded_at")
    top_entities_where = _resolve_time_range(time_range, "loaded_at")
    
    top_entities_sql = f"""
        SELECT entity
        FROM newspulse.raw_article_entities
        WHERE {top_entities_where}
        GROUP BY entity
        ORDER BY count() DESC
        LIMIT {limit}
    """
    
    query = f"""
        SELECT e.entity AS entity, s.sentiment_label AS sentiment, count() AS count
        FROM newspulse.raw_article_entities e
        JOIN newspulse.raw_article_sentiment s ON e.url_hash = s.url_hash
        WHERE e.entity IN ({top_entities_sql}) AND {where} AND s.sentiment_label != ''
        GROUP BY entity, sentiment
    """
    rows = _query(query)
    
    entities_data = {}
    for row in rows:
        ent = row["entity"]
        if ent not in entities_data:
            entities_data[ent] = {"entity": ent, "Positive": 0, "Negative": 0, "Neutral": 0, "total": 0}
        label = row["sentiment"].capitalize()
        if label in ("Positive", "Negative", "Neutral"):
            entities_data[ent][label] = row["count"]
            entities_data[ent]["total"] += row["count"]
            
    sorted_entities = sorted(list(entities_data.values()), key=lambda x: x["total"], reverse=True)
    return sorted_entities

def get_entity_knowledge_graph(time_range="7d", limit=30):
    where = _resolve_time_range(time_range, "loaded_at")

    top_entities_sql = f"""
        SELECT entity AS id, any(entity_type) AS group, count() AS val
        FROM newspulse.raw_article_entities
        WHERE {where}
        GROUP BY entity
        ORDER BY val DESC
        LIMIT {limit}
    """
    nodes_raw = _query(top_entities_sql)

    if not nodes_raw:
        return {"nodes": [], "links": []}
        
    where_e1 = where.replace("loaded_at", "e1.loaded_at").replace("publish_time", "e1.publish_time")
    where_e2 = where.replace("loaded_at", "e2.loaded_at").replace("publish_time", "e2.publish_time")

    edge_query = f"""
        WITH top_entities AS (
            SELECT entity FROM newspulse.raw_article_entities
            WHERE {where}
            GROUP BY entity ORDER BY count() DESC LIMIT {limit}
        )
        SELECT
            e1.entity AS source,
            e2.entity AS target,
            count(DISTINCT e1.url_hash) AS weight
        FROM newspulse.raw_article_entities e1
        JOIN newspulse.raw_article_entities e2 ON e1.url_hash = e2.url_hash
        WHERE {where_e1}
          AND {where_e2}
          AND e1.entity IN (SELECT entity FROM top_entities)
          AND e2.entity IN (SELECT entity FROM top_entities)
          AND e1.entity < e2.entity
        GROUP BY source, target
        HAVING weight > 0
        ORDER BY weight DESC
        LIMIT 100
    """
    links_raw = _query(edge_query)

    nodes = [{"id": n["id"], "name": n["id"], "val": n["val"], "group": n["group"]} for n in nodes_raw]
    links = [{"source": l["source"], "target": l["target"], "weight": l["weight"]} for l in links_raw]

    return {"nodes": nodes, "links": links}

