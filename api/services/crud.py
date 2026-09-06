from typing import Optional
from datetime import date
from api.config import get_ch_client

def get_articles(
        page: int = 1,
        page_size: int = 20,
        q: Optional[str] = None,
        source: Optional[str] = None,
        category: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        entity: Optional[str] = None,
        keyword: Optional[str] = None,
) -> dict:
    client = get_ch_client()
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

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total
    count_sql = f"SELECT count() as total FROM newspulse.raw_articles {where_clause}"
    try:
        count_result = client.query(count_sql, parameters=params).first_row
        total = count_result[0] if count_result else 0
    except Exception as e:
        print("Count Error:", e)
        total = 0

    # Fetch page
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = f"""
        SELECT
            url_hash as article_id,
            title,
            url,
            source,
            category,
            publish_time as publish_date,
            publish_hour,
            author,
            word_count,
            keyword_count,
            crawl_latency_minutes
        FROM newspulse.raw_articles
        {where_clause}
        ORDER BY publish_time DESC, publish_hour DESC
        LIMIT {page_size} OFFSET {offset}
    """
    
    try:
        result = client.query(data_sql, parameters=params)
        rows = list(result.named_results())
    except Exception as e:
        print("Data Error:", e)
        rows = []

    # Map output fields for frontend format compatibility
    for row in rows:
        row["sentiment_score"] = 0.0 # Mock or join sentiment here

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "data": rows,
    }


def get_article_detail(article_id: str) -> Optional[dict]:
    client = get_ch_client()
    sql = """
        SELECT
            url_hash as article_id,
            title,
            url,
            source,
            category,
            publish_time as publish_date,
            publish_hour,
            author,
            word_count,
            keyword_count,
            crawl_latency_minutes
        FROM newspulse.raw_articles
        WHERE url_hash = {article_id:String}
    """
    try:
        res = client.query(sql, parameters={"article_id": article_id}).named_results()
        if not res:
            return None
        article = res[0]
        
        # Get keywords
        kw_sql = "SELECT keyword FROM newspulse.raw_article_keywords WHERE url_hash = {article_id:String} ORDER BY score DESC"
        kw_res = client.query(kw_sql, parameters={"article_id": article_id}).named_results()
        article["keywords"] = [r["keyword"] for r in kw_res]
        
        # Get entities
        ent_sql = "SELECT entity as entity_name, entity_type FROM newspulse.raw_article_entities WHERE url_hash = {article_id:String}"
        ent_res = client.query(ent_sql, parameters={"article_id": article_id}).named_results()
        article["entities"] = ent_res
        
        return article
    except Exception as e:
        print("Detail Error:", e)
        return None


def delete_article(article_id: str) -> bool:
    # Not supported well in ClickHouse for simple APIs. Let's return False or mock.
    return False