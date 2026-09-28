from typing import Optional
from datetime import date, datetime
import logging
from api.config import get_ch_client


logger = logging.getLogger("newspulse.crud")


def _build_article_filters(
        q=None,
        source=None,
        category=None,
        date_from=None,
        date_to=None,
        published_from=None,
        published_to=None,
        entity=None,
        keyword=None,
):
    conditions = []
    params = {}

    if q:
        conditions.append("title ILIKE {q:String}")
        params["q"] = f"%{q}%"
    if source:
        conditions.append("source = {source:String}")
        params["source"] = source
    if category:
        conditions.append("category = {category:String}")
        params["category"] = category
    if date_from:
        conditions.append("toDate(publish_time) >= {date_from:Date}")
        params["date_from"] = date_from
    if date_to:
        conditions.append("toDate(publish_time) <= {date_to:Date}")
        params["date_to"] = date_to
    if published_from:
        conditions.append("publish_time >= {published_from:DateTime}")
        params["published_from"] = published_from
    if published_to:
        conditions.append("publish_time < {published_to:DateTime}")
        params["published_to"] = published_to
    if entity:
        conditions.append("""
            url_hash IN (
                SELECT url_hash
                FROM newspulse.raw_article_entities
                WHERE lowerUTF8(entity) = lowerUTF8({entity:String})
            )
        """)
        params["entity"] = entity
    if keyword:
        conditions.append("""
            url_hash IN (
                SELECT url_hash
                FROM newspulse.raw_article_keywords
                WHERE lowerUTF8(keyword) = lowerUTF8({keyword:String})
            )
        """)
        params["keyword"] = keyword

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    return where_clause, params


def get_articles(
        page: int = 1,
        page_size: int = 20,
        q: Optional[str] = None,
        source: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        published_from: Optional[datetime] = None,
        published_to: Optional[datetime] = None,
        entity: Optional[str] = None,
        keyword: Optional[str] = None,
) -> dict:
    client = get_ch_client()
    where_clause, params = _build_article_filters(
        q=q,
        source=source,
        category=category,
        date_from=date_from,
        date_to=date_to,
        published_from=published_from,
        published_to=published_to,
        entity=entity,
        keyword=keyword,
    )
    try:
        try:
            count_result = client.query(
                f"SELECT count() AS total FROM newspulse.raw_articles FINAL {where_clause}",
                parameters=params,
            ).first_row
            total = count_result[0] if count_result else 0
        except Exception:
            logger.exception("Failed to count articles")
            total = 0

        query_params = {
            **params,
            "page_size": page_size,
            "offset": (page - 1) * page_size,
        }
        data_sql = f"""
            SELECT
                url_hash AS article_id, title, url, source, category,
                publish_time AS publish_date, publish_hour,
                author, word_count, keyword_count, crawl_latency_minutes,
                ifNull(sentiment.sentiment_score, toFloat32(0)) AS sentiment_score,
                ifNull(sentiment.sentiment_label, 'neutral') AS sentiment_label
            FROM newspulse.raw_articles FINAL
            LEFT JOIN (
                SELECT
                    url_hash,
                    argMax(sentiment_score, loaded_at) AS sentiment_score,
                    argMax(sentiment_label, loaded_at) AS sentiment_label
                FROM newspulse.raw_article_sentiment
                GROUP BY url_hash
            ) AS sentiment USING (url_hash)
            {where_clause}
            ORDER BY publish_time DESC, publish_hour DESC
            LIMIT {{page_size:UInt32}} OFFSET {{offset:UInt64}}
        """

        try:
            result = client.query(data_sql, parameters=query_params)
            rows = list(result.named_results())
        except Exception:
            logger.exception("Failed to list articles")
            rows = []

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "data": rows,
        }
    finally:
        client.close()


def get_article_detail(article_id: str) -> Optional[dict]:
    client = get_ch_client()
    sql = """
        SELECT
            url_hash as article_id, title, url, source, category,
            publish_time as publish_date, publish_hour,
            author, word_count, keyword_count, crawl_latency_minutes,
            ifNull(sentiment.sentiment_score, toFloat32(0)) AS sentiment_score,
            ifNull(sentiment.sentiment_label, 'neutral') AS sentiment_label
        FROM newspulse.raw_articles FINAL
        LEFT JOIN (
            SELECT
                url_hash,
                argMax(sentiment_score, loaded_at) AS sentiment_score,
                argMax(sentiment_label, loaded_at) AS sentiment_label
            FROM newspulse.raw_article_sentiment
            GROUP BY url_hash
        ) AS sentiment USING (url_hash)
        WHERE url_hash = {article_id:String}
    """
    try:
        res = list(client.query(sql, parameters={"article_id": article_id}).named_results())
        if not res:
            return None
        article = res[0]

        kw_res = list(client.query(
            """
            SELECT keyword
            FROM newspulse.raw_article_keywords
            WHERE url_hash = {article_id:String}
            GROUP BY keyword
            ORDER BY max(score) DESC
            """,
            parameters={"article_id": article_id},
        ).named_results())
        article["keywords"] = [r["keyword"] for r in kw_res]

        ent_res = list(client.query(
            """
            SELECT entity AS entity_name, entity_type
            FROM newspulse.raw_article_entities
            WHERE url_hash = {article_id:String}
            GROUP BY entity, entity_type
            ORDER BY entity_type, entity
            """,
            parameters={"article_id": article_id},
        ).named_results())
        article["entities"] = ent_res

        return article
    except Exception:
        logger.exception("Failed to load article detail article_id=%s", article_id)
        return None
    finally:
        client.close()
