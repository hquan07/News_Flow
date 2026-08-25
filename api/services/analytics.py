from typing import Optional
import psycopg2
import psycopg2.extras
from api.config import get_pg_connection


def _resolve_time_range(time_range, date_column="date"):
    mapping = {
        "today": f"{date_column} = CURRENT_DATE",
        "yesterday": f"{date_column} = CURRENT_DATE - 1",
        "7d": f"{date_column} >= CURRENT_DATE - INTERVAL '7 days'",
        "30d": f"{date_column} >= CURRENT_DATE - INTERVAL '30 days'",
        "90d": f"{date_column} >= CURRENT_DATE - INTERVAL '90 days'",
    }
    return mapping.get(time_range, mapping["7d"])


def _query(sql, params=None):
    conn = get_pg_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    finally:
        conn.close()


def _query_one(sql, params=None):
    conn = get_pg_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or [])
            row = cur.fetchone()
            return dict(row) if row else {}
    finally:
        conn.close()


def get_overview(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "date")
    params = []
    if source:
        where += " AND source = %s"
        params.append(source)
    if category:
        where += " AND category = %s"
        params.append(category)
    return _query(
        f"SELECT date, source, category, article_count, avg_word_count, avg_crawl_latency "
        f"FROM mart.daily_overview WHERE {where} ORDER BY date DESC, source, category",
        params,
    )


def get_hourly_distribution(time_range="7d", source=None, category=None):
    if category:
        where = _resolve_time_range(time_range, "dt.full_date")
        params = []
        if source:
            where += " AND ds.name = %s"
            params.append(source)
        where += " AND dc.name = %s"
        params.append(category)
        return _query(
            f"SELECT publish_hour AS hour, ds.name AS source, COUNT(*) AS total_count "
            f"FROM warehouse.fact_article fa "
            f"JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id "
            f"JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id "
            f"JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id "
            f"WHERE {where} AND publish_hour IS NOT NULL "
            f"GROUP BY publish_hour, ds.name ORDER BY publish_hour",
            params,
        )
    else:
        where = _resolve_time_range(time_range, "date")
        params = []
        if source:
            where += " AND source = %s"
            params.append(source)
        return _query(
            f"SELECT hour, source, SUM(article_count) AS total_count "
            f"FROM mart.hourly_distribution WHERE {where} "
            f"GROUP BY hour, source ORDER BY hour",
            params,
        )


def get_trending_keywords(time_range="7d", limit=20, source=None, category=None):
    if not source and not category and time_range in ["7d", "week"]:
        return _query(
            "SELECT keyword, mention_count, prev_week_count, spike_score "
            "FROM mart.trending_keywords "
            "WHERE week_start >= DATE_TRUNC('week', CURRENT_DATE) "
            "ORDER BY spike_score DESC LIMIT %s",
            [limit],
        )
    else:
        interval_days = 7
        if time_range in ["30d", "month"]: interval_days = 30
        elif time_range == "today": interval_days = 1
        elif time_range == "yesterday": interval_days = 1
        
        filter_cond = ""
        filter_params = []
        if source:
            filter_cond += " AND ds.name = %s"
            filter_params.append(source)
        if category:
            filter_cond += " AND dc.name = %s"
            filter_params.append(category)
            
        params = filter_params + filter_params + [limit]
        
        sql = f"""
            WITH current_period AS (
                SELECT dk.keyword, COUNT(fa.article_id) AS mention_count
                FROM warehouse.fact_article fa
                JOIN warehouse.bridge_article_keyword bak ON fa.article_id = bak.article_id
                JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
                JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
                JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
                JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
                WHERE dt.full_date >= CURRENT_DATE - INTERVAL '{interval_days} days' {filter_cond}
                GROUP BY dk.keyword
            ),
            previous_period AS (
                SELECT dk.keyword, COUNT(fa.article_id) AS mention_count
                FROM warehouse.fact_article fa
                JOIN warehouse.bridge_article_keyword bak ON fa.article_id = bak.article_id
                JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
                JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
                JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
                JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
                WHERE dt.full_date >= CURRENT_DATE - INTERVAL '{interval_days * 2} days' 
                  AND dt.full_date < CURRENT_DATE - INTERVAL '{interval_days} days' {filter_cond}
                GROUP BY dk.keyword
            )
            SELECT cp.keyword, cp.mention_count, 
                   COALESCE(pp.mention_count, 0) AS prev_week_count,
                   CASE 
                       WHEN COALESCE(pp.mention_count, 0) = 0 THEN 100.0
                       ELSE ROUND(((cp.mention_count - pp.mention_count)::NUMERIC / pp.mention_count) * 100, 2)
                   END AS spike_score
            FROM current_period cp
            LEFT JOIN previous_period pp ON cp.keyword = pp.keyword
            ORDER BY spike_score DESC, cp.mention_count DESC
            LIMIT %s
        """
        return _query(sql, params)


def get_keyword_timeline(keyword=None, days=30):
    return _query(
        "SELECT week_start, mention_count FROM mart.trending_keywords "
        "WHERE keyword = %s AND week_start >= CURRENT_DATE - INTERVAL '%s days' "
        "ORDER BY week_start",
        [keyword, days],
    )


def get_co_occurrences(keyword=None, limit=20):
    return _query(
        "SELECT dk1.keyword AS keyword_a, dk2.keyword AS keyword_b, COUNT(*) AS co_count "
        "FROM warehouse.bridge_article_keyword bak1 "
        "JOIN warehouse.bridge_article_keyword bak2 "
        "  ON bak1.article_id = bak2.article_id AND bak1.keyword_id < bak2.keyword_id "
        "JOIN warehouse.dim_keyword dk1 ON dk1.keyword_id = bak1.keyword_id "
        "JOIN warehouse.dim_keyword dk2 ON dk2.keyword_id = bak2.keyword_id "
        "GROUP BY dk1.keyword, dk2.keyword ORDER BY co_count DESC LIMIT %s",
        [limit],
    )


def get_source_comparison(time_range="7d", source=None, category=None):
    if category:
        where = _resolve_time_range(time_range, "dt.full_date")
        params = []
        if source:
            where += " AND ds.name = %s"
            params.append(source)
        where += " AND dc.name = %s"
        params.append(category)
        
        return _query(
            f"SELECT ds.name AS source, COUNT(fa.article_id) AS total_articles, "
            f"ROUND(AVG(fa.publish_hour),1) AS avg_publish_hour, "
            f"MODE() WITHIN GROUP (ORDER BY dc.name) AS top_category, "
            f"ROUND(AVG(fa.word_count),1) AS avg_word_count "
            f"FROM warehouse.fact_article fa "
            f"JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id "
            f"JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id "
            f"JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id "
            f"WHERE {where} "
            f"GROUP BY ds.name ORDER BY total_articles DESC",
            params
        )
    else:
        where = _resolve_time_range(time_range, "date")
        params = []
        if source:
            where += " AND source = %s"
            params.append(source)
        return _query(
            f"SELECT source, SUM(total_articles) AS total_articles, "
            f"ROUND(AVG(avg_publish_hour),1) AS avg_publish_hour, "
            f"MODE() WITHIN GROUP (ORDER BY top_category) AS top_category, "
            f"ROUND(AVG(avg_word_count),1) AS avg_word_count "
            f"FROM mart.source_comparison WHERE {where} "
            f"GROUP BY source ORDER BY total_articles DESC",
            params
        )


def get_alerts(threshold=2.0, limit=10):
    return _query(
        "WITH hourly AS ("
        "  SELECT DATE_TRUNC('hour', publish_time) AS hour_slot, COUNT(*) AS cnt "
        "  FROM warehouse.fact_article "
        "  WHERE publish_time >= CURRENT_DATE - INTERVAL '7 days' GROUP BY hour_slot"
        "), stats AS ("
        "  SELECT AVG(cnt) AS avg_cnt, COALESCE(STDDEV(cnt), 1) AS std_cnt FROM hourly"
        ") "
        "SELECT h.hour_slot, h.cnt AS article_count, s.avg_cnt::INTEGER AS avg_count "
        "FROM hourly h, stats s "
        "WHERE h.cnt > s.avg_cnt + %s * s.std_cnt ORDER BY h.hour_slot DESC LIMIT %s",
        [threshold, limit],
    )


def get_entity_stats(time_range="7d", entity_type=None, limit=20, source=None, category=None):
    where = _resolve_time_range(time_range, "dt.full_date")
    params = []
    if entity_type:
        where += " AND de.entity_type = %s"
        params.append(entity_type)
    if source:
        where += " AND ds.name = %s"
        params.append(source)
    if category:
        where += " AND dc.name = %s"
        params.append(category)
        
    params.append(limit)
    return _query(
        f"SELECT de.entity_name AS entity, de.entity_type, "
        f"COUNT(DISTINCT bae.article_id) AS article_count, "
        f"COUNT(bae.article_id) AS mention_count "
        f"FROM warehouse.dim_entity de "
        f"JOIN warehouse.bridge_article_entity bae ON de.entity_id = bae.entity_id "
        f"JOIN warehouse.fact_article fa ON fa.article_id = bae.article_id "
        f"JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id "
        f"JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id "
        f"JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id "
        f"WHERE {where} "
        f"GROUP BY de.entity_id, de.entity_name, de.entity_type "
        f"ORDER BY article_count DESC LIMIT %s",
        params,
    )


def get_entity_timeline(entity=None, days=30):
    return _query(
        "SELECT dt.full_date AS date, COUNT(*) AS mention_count "
        "FROM warehouse.bridge_article_entity bae "
        "JOIN warehouse.dim_entity de ON de.entity_id = bae.entity_id "
        "JOIN warehouse.fact_article fa ON fa.article_id = bae.article_id "
        "JOIN warehouse.dim_time dt ON dt.time_id = fa.time_id "
        "WHERE de.entity_name = %s AND dt.full_date >= CURRENT_DATE - INTERVAL '%s days' "
        "GROUP BY dt.full_date ORDER BY dt.full_date",
        [entity, days],
    )


def get_entities_by_category(category=None, limit=20):
    where = "1=1"
    params = []
    if category:
        where += " AND dc.name = %s"
        params.append(category)
    params.append(limit)
    return _query(
        f"SELECT de.entity_name AS entity, de.entity_type, dc.name AS category, COUNT(*) AS mention_count "
        f"FROM warehouse.bridge_article_entity bae "
        f"JOIN warehouse.dim_entity de ON de.entity_id = bae.entity_id "
        f"JOIN warehouse.fact_article fa ON fa.article_id = bae.article_id "
        f"JOIN warehouse.dim_category dc ON dc.category_id = fa.category_id "
        f"WHERE {where} "
        f"GROUP BY de.entity_name, de.entity_type, dc.name "
        f"ORDER BY mention_count DESC LIMIT %s",
        params,
    )


def get_sentiment_distribution(time_range="7d", source=None, category=None):
    where = _resolve_time_range(time_range, "dt.full_date")
    params = []
    if source:
        where += " AND ds.name = %s"
        params.append(source)
    if category:
        where += " AND dc.name = %s"
        params.append(category)
        
    return _query(
        f"SELECT fa.sentiment_label, COUNT(*) AS count "
        f"FROM warehouse.fact_article fa "
        f"JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id "
        f"JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id "
        f"JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id "
        f"WHERE {where} AND fa.sentiment_label IS NOT NULL "
        f"GROUP BY fa.sentiment_label",
        params,
    )


def get_entity_network(time_range="7d", limit=50):
    where = _resolve_time_range(time_range, "date")
    edges = _query(
        f"SELECT entity_a, entity_b, SUM(co_occurrence_count) AS weight "
        f"FROM mart.entity_network "
        f"WHERE {where} "
        f"GROUP BY entity_a, entity_b "
        f"ORDER BY weight DESC LIMIT %s",
        [limit]
    )
    
    nodes_set = set()
    for e in edges:
        nodes_set.add(e["entity_a"])
        nodes_set.add(e["entity_b"])
        
    nodes = [{"id": n, "label": n} for n in nodes_set]
    links = [{"source": e["entity_a"], "target": e["entity_b"], "weight": e["weight"]} for e in edges]
    
    return {"nodes": nodes, "links": links}