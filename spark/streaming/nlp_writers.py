from loguru import logger
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from spark.streaming.sink_writers import write_to_clickhouse_batch


def write_keywords_to_clickhouse(df: DataFrame) -> int:
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

        write_to_clickhouse_batch(kw_df, "raw_article_keywords")
        return kw_df.count()
    except Exception as e:
        logger.error(f"[Keywords] Failed to write: {e}")
        return 0


def write_entities_to_clickhouse(df: DataFrame) -> int:
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

        write_to_clickhouse_batch(ent_df, "raw_article_entities")
        return ent_df.count()
    except Exception as e:
        logger.error(f"[Entities] Failed to write: {e}")
        return 0


def write_sentiment_to_clickhouse(df: DataFrame) -> int:
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

        write_to_clickhouse_batch(sentiment_df, "raw_article_sentiment")
        return sentiment_df.count()
    except Exception as e:
        logger.error(f"[Sentiment] Failed to write: {e}")
        return 0