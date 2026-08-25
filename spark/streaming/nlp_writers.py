import os
import psycopg2
from loguru import logger
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from spark.streaming.sink_writers import write_to_postgres_batch


def _get_pg_conn():
    """Create a direct psycopg2 connection for upsert operations."""
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "postgres"),
        port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.getenv("PG_DB", "newspulse"),
        user=os.getenv("PG_USER", "newspulse"),
        password=os.getenv("PG_PASSWORD", "newspulse"),
    )


def write_keywords_to_postgres(df: DataFrame) -> int:
    if df.isEmpty():
        return 0

    try:
        # Explode keywords array
        kw_df = df.select(
            F.col("url_hash"),
            F.explode(F.col("keywords")).alias("kw")
        ).select(
            F.col("url_hash"),
            F.col("kw.keyword"),
            F.col("kw.score")
        )

        if kw_df.isEmpty():
            return 0

        write_to_postgres_batch(kw_df, "raw.article_keywords", mode="append")
        return kw_df.count()
    except Exception as e:
        logger.error(f"[Keywords] Failed to write: {e}")
        return 0


def write_entities_to_postgres(df: DataFrame) -> int:
    if df.isEmpty():
        return 0

    try:
        # Explode entities array
        ent_df = df.select(
            F.col("url_hash"),
            F.explode(F.col("entities")).alias("ent")
        ).select(
            F.col("url_hash"),
            F.col("ent.entity"),
            F.col("ent.entity_type"),
            F.col("ent.label")
        )

        if ent_df.isEmpty():
            return 0

        write_to_postgres_batch(ent_df, "raw.article_entities", mode="append")
        return ent_df.count()
    except Exception as e:
        logger.error(f"[Entities] Failed to write: {e}")
        return 0


def write_sentiment_to_postgres(df: DataFrame) -> int:
    """Write sentiment data using psycopg2 with ON CONFLICT DO NOTHING."""
    if df.isEmpty():
        return 0

    try:
        sentiment_df = df.select(
            F.col("url_hash"),
            F.col("sentiment_score"),
            F.col("sentiment_label")
        )

        if sentiment_df.isEmpty():
            return 0

        # Collect to driver and upsert via psycopg2 to handle PK conflicts
        rows = sentiment_df.collect()
        if not rows:
            return 0

        conn = _get_pg_conn()
        cur = conn.cursor()
        count = 0
        for row in rows:
            cur.execute(
                """
                INSERT INTO raw.article_sentiment (url_hash, sentiment_score, sentiment_label)
                VALUES (%s, %s, %s)
                ON CONFLICT (url_hash) DO UPDATE SET
                    sentiment_score = EXCLUDED.sentiment_score,
                    sentiment_label = EXCLUDED.sentiment_label
                """,
                (row["url_hash"], float(row["sentiment_score"]) if row["sentiment_score"] is not None else 0.0,
                 row["sentiment_label"] or "neutral"),
            )
            count += 1
        conn.commit()
        cur.close()
        conn.close()
        return count
    except Exception as e:
        logger.error(f"[Sentiment] Failed to write: {e}")
        return 0