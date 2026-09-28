import logging
import time
from typing import Optional

from api.config import get_ch_client


logger = logging.getLogger("newspulse.analytics")


def _resolve_time_range(time_range, date_column="publish_time"):
    mapping = {
        "today": f"{date_column} >= now() - INTERVAL 24 HOUR",
        "yesterday": f"{date_column} >= now() - INTERVAL 48 HOUR AND {date_column} < now() - INTERVAL 24 HOUR",
        "7d": f"{date_column} >= now() - INTERVAL 7 DAY",
        "30d": f"{date_column} >= now() - INTERVAL 30 DAY",
        "90d": f"{date_column} >= now() - INTERVAL 90 DAY",
        "all": "1 = 1",
    }
    return mapping.get(time_range, mapping["7d"])


def _query(sql, params=None):
    from api.config import get_settings

    settings = get_settings()
    attempts = max(settings.CLICKHOUSE_QUERY_RETRIES, 1)
    for attempt in range(1, attempts + 1):
        client = None
        try:
            client = get_ch_client()
            result = client.query(sql, parameters=params or {})
            return list(result.named_results())
        except Exception as exc:
            if attempt == attempts:
                logger.error(
                    "ClickHouse query failed after %s attempts: %s",
                    attempts,
                    exc,
                )
                return []
            delay = settings.RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "ClickHouse query attempt %s/%s failed; retrying in %.2fs",
                attempt,
                attempts,
                delay,
            )
            time.sleep(delay)
        finally:
            if client is not None and hasattr(client, "close"):
                client.close()


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


def get_social_debates(time_range="7d", limit=10, source=None, category=None):
    where = _resolve_time_range(time_range, "loaded_at")
    params = {}
    if source:
        where += " AND source = {source:String}"
        params["source"] = source
    return _query(
        f"SELECT title AS topic, reply_count AS comments_count, "
        f"round((reply_count * 1.5 + like_count) / 100, 1) AS controversy_score "
        f"FROM newspulse.social_sentiment_metrics "
        f"WHERE {where} AND reply_count > 0 "
        f"ORDER BY controversy_score DESC LIMIT {limit}",
        params
    )


def get_social_crisis_alerts(negative_pct_threshold=30.0, min_posts=10):
    """Detect sources with high negative sentiment in the last hour."""
    return _query(
        f"SELECT source, "
        f"count() as total_posts, "
        f"countIf(sentiment_label = 'negative') as negative_posts, "
        f"round((countIf(sentiment_label = 'negative') / count()) * 100, 1) as negative_pct "
        f"FROM newspulse.social_sentiment_metrics "
        f"WHERE publish_time >= now() - INTERVAL 1 HOUR "
        f"GROUP BY source "
        f"HAVING negative_pct > {negative_pct_threshold} AND total_posts >= {min_posts} "
        f"ORDER BY negative_pct DESC"
    )


_PLACEHOLDER_PATTERNS = [
    "Chủ đề đang hot trên %",
    "Bài thảo luận % trên %",
]


def _is_placeholder_title(title: str) -> bool:
    """Check if a title is a known synthetic/placeholder string."""
    if not title or not title.strip():
        return True
    for pattern in _PLACEHOLDER_PATTERNS:
        parts = pattern.split("%")
        if all(p in title for p in parts if p):
            return True
    return False


def _is_synthetic_post(post_id: str) -> bool:
    """Identify records generated by the demo/live-data producer."""
    return bool(post_id and post_id.startswith("live_post_"))


def get_viral_post_alerts(interaction_threshold=50):
    """Detect individual social posts with high interactions in the last hour."""
    rows = _query(
        f"SELECT post_id, source, title, "
        f"(like_count + reply_count) as interactions, "
        f"sentiment_label, "
        f"publish_time "
        f"FROM newspulse.social_sentiment_metrics "
        f"WHERE publish_time >= now() - INTERVAL 1 HOUR "
        f"AND (like_count + reply_count) >= {interaction_threshold} "
        f"ORDER BY interactions DESC LIMIT 10"
    )
    results = []
    seen_ids = set()
    for row in rows:
        pid = row.get("post_id", "")
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        title = row.get("title", "")
        is_placeholder = _is_placeholder_title(title)
        pt = row.get("publish_time")
        results.append({
            "post_id": pid,
            "source": row.get("source", ""),
            "title": title if not is_placeholder else "",
            "interactions": row.get("interactions", 0),
            "sentiment_label": row.get("sentiment_label", ""),
            "publish_time": pt.isoformat() if hasattr(pt, "isoformat") else str(pt) if pt else None,
            "data_quality": {
                "title_available": not is_placeholder,
                "synthetic": _is_synthetic_post(pid),
            },
        })
    return results


def get_viral_post_detail(post_id: str):
    """Fetch full detail for a single social post by post_id."""
    rows = _query(
        "SELECT post_id, source, title, content, "
        "like_count, reply_count, upvote_ratio, "
        "(like_count + reply_count) as interactions, "
        "sentiment_score, sentiment_label, "
        "url, author, top_comments, "
        "publish_time, crawled_at "
        "FROM newspulse.social_sentiment_metrics "
        "WHERE post_id = {post_id:String} "
        "LIMIT 1",
        {"post_id": post_id},
    )
    if not rows:
        return None

    row = rows[0]
    title = row.get("title", "")
    content = row.get("content", "")
    url = row.get("url", "")
    is_placeholder_t = _is_placeholder_title(title)
    is_placeholder_c = bool(
        not content or not content.strip()
        or "Nội dung chi tiết của bài thảo luận" in content
    )
    pt = row.get("publish_time")
    ca = row.get("crawled_at")

    return {
        "post_id": row["post_id"],
        "source": row.get("source", ""),
        "title": title if not is_placeholder_t else "",
        "content": content if not is_placeholder_c else "",
        "excerpt": (content[:200] + "…") if content and len(content) > 200 and not is_placeholder_c else (content if not is_placeholder_c else ""),
        "url": url,
        "author": row.get("author", ""),
        "like_count": row.get("like_count", 0),
        "reply_count": row.get("reply_count", 0),
        "interactions": row.get("interactions", 0),
        "upvote_ratio": row.get("upvote_ratio", 0.0),
        "sentiment_score": row.get("sentiment_score", 0.0),
        "sentiment_label": row.get("sentiment_label", ""),
        "top_comments": row.get("top_comments", []),
        "publish_time": pt.isoformat() if hasattr(pt, "isoformat") else str(pt) if pt else None,
        "crawled_at": ca.isoformat() if hasattr(ca, "isoformat") else str(ca) if ca else None,
        "data_quality": {
            "title_available": not is_placeholder_t,
            "content_available": not is_placeholder_c,
            "url_available": bool(url and url.strip()),
            "synthetic": _is_synthetic_post(row["post_id"]),
        },
    }


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


def _sentiment_article_filters(time_range, source=None, category=None):
    where = _resolve_time_range(time_range, "a.publish_time")
    params = {}
    if source:
        where += " AND a.source = {source:String}"
        params["source"] = source
    if category:
        where += " AND a.category = {category:String}"
        params["category"] = category
    return where, params


def get_sentiment_timeline(time_range="7d", source=None, category=None):
    where, params = _sentiment_article_filters(time_range, source, category)
    bucket = {
        "today": "toStartOfHour(a.publish_time)",
        "7d": "toStartOfDay(a.publish_time)",
        "30d": "toStartOfDay(a.publish_time)",
        "90d": "toStartOfWeek(a.publish_time)",
        "all": "toStartOfMonth(a.publish_time)",
    }.get(time_range, "toStartOfDay(a.publish_time)")
    rows = _query(f"""
        SELECT {bucket} AS time, s.sentiment_label, count() AS count
        FROM newspulse.raw_article_sentiment s
        INNER JOIN newspulse.raw_articles a ON s.url_hash = a.url_hash
        WHERE {where} AND s.sentiment_label != ''
        GROUP BY time, s.sentiment_label
        ORDER BY time ASC
    """, params)

    timeline = {}
    for row in rows:
        t = row["time"].isoformat()
        if t not in timeline:
            timeline[t] = {"time": t, "Positive": 0, "Negative": 0, "Neutral": 0}
        label = row["sentiment_label"].capitalize()
        if label in ("Positive", "Negative", "Neutral"):
            timeline[t][label] = row["count"]
    return list(timeline.values())


def get_sentiment_by_source(time_range="7d", source=None, category=None):
    where, params = _sentiment_article_filters(time_range, source, category)
    rows = _query(f"""
        SELECT a.source AS source, s.sentiment_label AS sentiment, count() AS count
        FROM newspulse.raw_article_sentiment s
        INNER JOIN newspulse.raw_articles a ON s.url_hash = a.url_hash
        WHERE {where} AND s.sentiment_label != ''
        GROUP BY a.source, s.sentiment_label
        ORDER BY count DESC
    """, params)

    sources = {}
    for row in rows:
        src = row["source"]
        if src not in sources:
            sources[src] = {"source": src, "Positive": 0, "Negative": 0, "Neutral": 0}
        label = row["sentiment"].capitalize()
        if label in ("Positive", "Negative", "Neutral"):
            sources[src][label] = row["count"]
    return list(sources.values())


def get_sentiment_coverage():
    row = _query_one("""
        SELECT
            (SELECT uniqExact(url_hash) FROM newspulse.raw_article_sentiment) AS total,
            (SELECT uniqExact(s.url_hash)
             FROM newspulse.raw_article_sentiment s
             INNER JOIN newspulse.raw_articles a ON s.url_hash = a.url_hash) AS linked
    """)
    total = int(row.get("total", 0))
    linked = int(row.get("linked", 0))
    return {
        "total": total,
        "linked": linked,
        "unlinked": max(total - linked, 0),
        "coverage_pct": round(linked * 100 / total, 1) if total else 100.0,
    }


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
