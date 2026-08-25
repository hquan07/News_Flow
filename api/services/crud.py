from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
from datetime import date

async def get_articles(
        session: AsyncSession,
        *,
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
    conditions = []
    params: dict = {}
    joins = []

    if q:
        conditions.append("fa.title ILIKE :q")
        params["q"] = f"%{q}%"
    if source:
        conditions.append("ds.name = :source")
        params["source"] = source
    if category:
        conditions.append("dc.name = :category")
        params["category"] = category
    if date_from:
        conditions.append("dt.full_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("dt.full_date <= :date_to")
        params["date_to"] = date_to
    if entity:
        joins.append("JOIN warehouse.bridge_article_entity bae ON fa.article_id = bae.article_id")
        joins.append("JOIN warehouse.dim_entity de ON bae.entity_id = de.entity_id")
        conditions.append("de.entity_name = :entity")
        params["entity"] = entity
    if keyword:
        joins.append("JOIN warehouse.bridge_article_keyword bak ON fa.article_id = bak.article_id")
        joins.append("JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id")
        conditions.append("dk.keyword = :keyword")
        params["keyword"] = keyword

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    join_clause = " ".join(joins)

    # Count total
    count_sql = f"""
        SELECT COUNT(DISTINCT fa.article_id) as total
        FROM warehouse.fact_article fa
        JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
        JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
        JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
        {join_clause}
        {where_clause}
    """
    count_result = await session.execute(text(count_sql), params)
    total = count_result.scalar()

    # Fetch page
    offset = (page - 1) * page_size
    params["limit"] = page_size
    params["offset"] = offset

    data_sql = f"""
        SELECT
            fa.article_id,
            fa.title,
            fa.url,
            ds.name as source,
            dc.name as category,
            dt.full_date as publish_date,
            fa.publish_hour,
            da.name as author,
            fa.word_count,
            fa.keyword_count,
            fa.crawl_latency_minutes
        FROM warehouse.fact_article fa
        JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
        JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
        JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
        LEFT JOIN warehouse.dim_author da ON fa.author_id = da.author_id
        {join_clause}
        {where_clause}
        ORDER BY dt.full_date DESC, fa.publish_hour DESC
        LIMIT :limit OFFSET :offset
    """
    result = await session.execute(text(data_sql), params)
    rows = result.mappings().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "data": [dict(r) for r in rows],
    }


async def get_article_detail(
        session: AsyncSession, article_id: int
) -> Optional[dict]:
    # Base article info
    sql = """
          SELECT fa.article_id, \
                 fa.title, \
                 fa.url, \
                 ds.name as source, \
                 dc.name as category, \
                 dt.full_date as publish_date, \
                 fa.publish_hour, \
                 da.name as author, \
                 fa.word_count, \
                 fa.keyword_count, \
                 fa.crawl_latency_minutes
          FROM warehouse.fact_article fa
                   JOIN warehouse.dim_source ds ON fa.source_id = ds.source_id
                   JOIN warehouse.dim_category dc ON fa.category_id = dc.category_id
                   JOIN warehouse.dim_time dt ON fa.time_id = dt.time_id
                   LEFT JOIN warehouse.dim_author da ON fa.author_id = da.author_id
          WHERE fa.article_id = :article_id \
          """
    result = await session.execute(text(sql), {"article_id": article_id})
    row = result.mappings().first()
    if not row:
        return None

    article = dict(row)

    # Keywords
    kw_sql = """
             SELECT dk.keyword, bak.relevance_score
             FROM warehouse.bridge_article_keyword bak
                      JOIN warehouse.dim_keyword dk ON bak.keyword_id = dk.keyword_id
             WHERE bak.article_id = :article_id
             ORDER BY bak.relevance_score DESC \
             """
    kw_result = await session.execute(text(kw_sql), {"article_id": article_id})
    article["keywords"] = [r["keyword"] for r in kw_result.mappings().all()]

    # Entities (NER)
    ent_sql = """
              SELECT de.entity_name, de.entity_type
              FROM warehouse.bridge_article_entity bae
                       JOIN warehouse.dim_entity de ON bae.entity_id = de.entity_id
              WHERE bae.article_id = :article_id \
              """
    ent_result = await session.execute(text(ent_sql), {"article_id": article_id})
    article["entities"] = [dict(r) for r in ent_result.mappings().all()]

    return article


async def delete_article(session: AsyncSession, article_id: int) -> bool:
    # Check existence
    check = await session.execute(
        text("SELECT 1 FROM warehouse.fact_article WHERE article_id = :id"),
        {"id": article_id},
    )
    if not check.scalar():
        return False

    # Delete bridges first, then fact
    await session.execute(
        text("DELETE FROM warehouse.bridge_article_keyword WHERE article_id = :id"),
        {"id": article_id},
    )
    await session.execute(
        text("DELETE FROM warehouse.bridge_article_entity WHERE article_id = :id"),
        {"id": article_id},
    )
    await session.execute(
        text("DELETE FROM warehouse.fact_article WHERE article_id = :id"),
        {"id": article_id},
    )
    await session.commit()
    return True