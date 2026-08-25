import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from unittest.mock import patch
from datetime import date, datetime

from api.main import app
from api.database import get_pg_session
from api.config import get_settings

settings = get_settings()

# Test database engine
TEST_DB_URL = settings.postgres_async_url

test_engine = create_async_engine(TEST_DB_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_pg_session():
    async with test_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# Override the dependency
app.dependency_overrides[get_pg_session] = override_get_pg_session


# Fixtures
@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def db_session():
    async with test_session_factory() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def seed_test_data(db_session: AsyncSession):
    # Ensure schemas exist
    for schema in ["warehouse", "mart"]:
        await db_session.execute(
            text(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        )
    await db_session.commit()

    # Seed dimension tables
    await db_session.execute(text("""
                                  INSERT INTO warehouse.dim_source (source_id, name, domain, base_url)
                                  VALUES (901, 'vnexpress', 'vnexpress.net', 'https://vnexpress.net'),
                                         (902, 'tuoitre', 'tuoitre.vn', 'https://tuoitre.vn'),
                                         (903, 'thanhnien', 'thanhnien.vn', 'https://thanhnien.vn')
                                  ON CONFLICT (source_id) DO NOTHING
                                  """))

    await db_session.execute(text("""
                                  INSERT INTO warehouse.dim_category (category_id, name)
                                  VALUES (901, 'tech'),
                                         (902, 'sports'),
                                         (903, 'economy')
                                  ON CONFLICT (category_id) DO NOTHING
                                  """))

    today = date.today()
    await db_session.execute(text("""
                                  INSERT INTO warehouse.dim_time (time_id, full_date, day_of_week, week_of_year, month, quarter, year, is_weekend)
                                  VALUES (90001, :today, :dow, :week, :month, :quarter, :year, :is_weekend)
                                  ON CONFLICT (time_id) DO NOTHING
                                  """), {
                                 "today": today,
                                 "dow": today.isoweekday(),
                                 "week": today.isocalendar()[1],
                                 "month": today.month,
                                 "quarter": (today.month - 1) // 3 + 1,
                                 "year": today.year,
                                 "is_weekend": today.weekday() >= 5,
                             })

    await db_session.execute(text("""
                                  INSERT INTO warehouse.dim_author (author_id, name, source_id)
                                  VALUES (901, 'Test Author', 901)
                                  ON CONFLICT (author_id) DO NOTHING
                                  """))

    # Seed fact articles
    await db_session.execute(text("""
                                  INSERT INTO warehouse.fact_article (article_id, url_hash, title, url, source_id, category_id,
                                                                      time_id,
                                                                      author_id, word_count, keyword_count,
                                                                      publish_hour,
                                                                      crawl_latency_minutes)
                                  VALUES (90001, 'hash_test_1', 'Test AI Article', 'https://vnexpress.net/test-1', 901, 901, 90001,
                                          901, 500, 5, 10, 2.5),
                                         (90002, 'hash_test_2', 'Test Sports Article', 'https://tuoitre.vn/test-2', 902, 902, 90001,
                                          NULL, 300, 3, 14, 1.8),
                                         (90003, 'hash_test_3', 'Test Economy Article', 'https://thanhnien.vn/test-3', 903, 903, 90001,
                                          NULL, 700, 8, 8, 3.2)
                                  ON CONFLICT (article_id) DO NOTHING
                                  """))

    # Seed keywords and bridge
    await db_session.execute(text("""
                                  INSERT INTO warehouse.dim_keyword (keyword_id, keyword, is_trending)
                                  VALUES (901, 'AI', TRUE),
                                         (902, 'machine learning', TRUE),
                                         (903, 'bóng đá', FALSE)
                                  ON CONFLICT (keyword_id) DO NOTHING
                                  """))

    await db_session.execute(text("""
                                  INSERT INTO warehouse.bridge_article_keyword (article_id, keyword_id, relevance_score)
                                  VALUES (90001, 901, 0.95),
                                         (90001, 902, 0.80),
                                         (90002, 903, 0.90)
                                  ON CONFLICT DO NOTHING
                                  """))

    # Seed entities and bridge
    await db_session.execute(text("""
                                  INSERT INTO warehouse.dim_entity (entity_id, entity_name, entity_type)
                                  VALUES (901, 'Việt Nam', 'LOC'),
                                         (902, 'Google', 'ORG'),
                                         (903, 'Nguyễn Văn A', 'PER')
                                  ON CONFLICT (entity_id) DO NOTHING
                                  """))

    await db_session.execute(text("""
                                  INSERT INTO warehouse.bridge_article_entity (article_id, entity_id)
                                  VALUES (90001, 901),
                                         (90001, 902),
                                         (90002, 901),
                                         (90003, 903)
                                  ON CONFLICT DO NOTHING
                                  """))

    # Seed mart tables
    await db_session.execute(text("""
                                  INSERT INTO mart.mart_daily_overview (report_date, source_name, category_name,
                                                                        article_count,
                                                                        avg_word_count, avg_keyword_count)
                                  VALUES (:today, 'vnexpress', 'tech', 15, 450.0, 5.2),
                                         (:today, 'tuoitre', 'sports', 12, 320.0, 3.8),
                                         (:today, 'thanhnien', 'economy', 8, 680.0, 7.1)
                                  ON CONFLICT (report_date, source_name, category_name) DO NOTHING
                                  """), {"today": today})

    await db_session.execute(text("""
                                  INSERT INTO mart.mart_hourly_distribution (report_date, source_name, hour,
                                                                             article_count)
                                  VALUES (:today, 'vnexpress', 8, 5),
                                         (:today, 'vnexpress', 10, 8),
                                         (:today, 'vnexpress', 14, 6),
                                         (:today, 'tuoitre', 10, 4),
                                         (:today, 'tuoitre', 14, 7)
                                  ON CONFLICT (report_date, source_name, hour) DO NOTHING
                                  """), {"today": today})

    await db_session.commit()

    yield

    # Cleanup test data (IDs in 90000+ range)
    await db_session.execute(text(
        "DELETE FROM warehouse.bridge_article_keyword WHERE article_id >= 90000"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.bridge_article_entity WHERE article_id >= 90000"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.fact_article WHERE article_id >= 90000"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.dim_keyword WHERE keyword_id >= 900"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.dim_entity WHERE entity_id >= 900"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.dim_author WHERE author_id >= 900"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.dim_time WHERE time_id >= 90000"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.dim_category WHERE category_id >= 900"
    ))
    await db_session.execute(text(
        "DELETE FROM warehouse.dim_source WHERE source_id >= 900"
    ))
    await db_session.execute(text(
        "DELETE FROM mart.mart_daily_overview WHERE source_name IN ('vnexpress','tuoitre','thanhnien') AND report_date = :today"
    ), {"today": today})
    await db_session.execute(text(
        "DELETE FROM mart.mart_hourly_distribution WHERE source_name IN ('vnexpress','tuoitre') AND report_date = :today"
    ), {"today": today})
    await db_session.commit()