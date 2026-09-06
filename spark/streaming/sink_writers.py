from pyspark.sql import DataFrame
from pyspark.sql import functions as F
import clickhouse_connect
from loguru import logger

from config.spark_config import (
    MONGO_URI,
    MONGO_DATABASE,
    MONGO_PROCESSED_COLLECTION,
    CLICKHOUSE_HOST,
    CLICKHOUSE_PORT,
    CLICKHOUSE_DB,
    CLICKHOUSE_USER,
    CLICKHOUSE_PASSWORD,
)


def _get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
    )


def write_to_mongodb_batch(df: DataFrame, collection: str = MONGO_PROCESSED_COLLECTION):
    (
        df.write
        .format("mongodb")
        .mode("append")
        .option("connection.uri", MONGO_URI)
        .option("database", MONGO_DATABASE)
        .option("collection", collection)
        .save()
    )


def write_to_clickhouse_batch(df: DataFrame, table: str):
    if df.isEmpty():
        return

    rows = df.collect()
    if not rows:
        return

    cols = df.columns
    data = [tuple(row[c] for c in cols) for row in rows]

    try:
        client = _get_clickhouse_client()
        client.insert(table, data, column_names=cols)
    except Exception as e:
        logger.error(f"Failed to write to ClickHouse table {table}: {e}")


def create_clickhouse_streaming_writer(df: DataFrame, table: str = "raw_articles"):
    def _write_batch(batch_df: DataFrame, batch_id: int):
        if batch_df.isEmpty():
            return

        output_df = batch_df.select(
            F.col("url_hash"),
            F.col("url"),
            F.col("title_clean").alias("title"),
            F.col("content_clean").alias("content"),
            F.col("author"),
            F.coalesce(F.col("publish_timestamp"), F.col("crawled_timestamp"), F.current_timestamp()).alias("publish_time"),
            F.col("source"),
            F.lit("").alias("source_domain"),
            F.col("category_normalized").alias("category"),
            F.col("word_count"),
            F.col("keyword_count"),
            F.col("publish_hour"),
            F.col("crawl_latency_minutes"),
            F.coalesce(F.col("crawled_timestamp"), F.current_timestamp()).alias("crawled_at"),
            F.current_timestamp().alias("loaded_at"),
        ).fillna({
            "author": "", 
            "content": "", 
            "category": "",
            "title": "",
            "url": "",
            "url_hash": "",
            "source": "",
            "word_count": 0,
            "keyword_count": 0,
            "publish_hour": 0,
            "crawl_latency_minutes": 0.0
        })

        write_to_clickhouse_batch(output_df, table)
        logger.info(f"[ClickHouse] Batch {batch_id}: wrote {output_df.count()} records to {table}")

    return (
        df.writeStream
        .foreachBatch(_write_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/clickhouse")
        .start()
    )