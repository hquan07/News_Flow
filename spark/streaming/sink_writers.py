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


def _get_clickhouse_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
        username=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )


def write_to_clickhouse_batch(df: DataFrame, table: str):
    if df.isEmpty():
        return
        
    rows = df.collect()
    if not rows:
        return
        
    # Get column names
    cols = df.columns
    # Convert Row objects to tuples
    data = [tuple(row[c] for c in cols) for row in rows]
    
    try:
        client = _get_clickhouse_client()
        client.insert(table, data, column_names=cols)
    except Exception as e:
        logger.error(f"Failed to write to ClickHouse table {table}: {e}")


def create_mongodb_streaming_writer(df: DataFrame, collection: str = MONGO_PROCESSED_COLLECTION):
    def _write_batch(batch_df: DataFrame, batch_id: int):
        if batch_df.isEmpty():
            return
        write_to_mongodb_batch(batch_df, collection)
        print(f"[MongoDB] Batch {batch_id}: wrote {batch_df.count()} records to {collection}")

    return (
        df.writeStream
        .foreachBatch(_write_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/mongodb")
        .start()
    )


def create_postgres_streaming_writer(df: DataFrame, table: str = "raw_articles"):
    # Renamed logically, but keeping function name if imported elsewhere
    # (Though we should probably rename it to create_clickhouse_streaming_writer)
    pass


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
            F.col("publish_timestamp").alias("publish_time"),
            F.col("source"),
            F.lit("").alias("source_domain"), # Avoid None for String type
            F.col("category_normalized").alias("category"),
            F.col("word_count"),
            F.col("keyword_count"),
            F.col("publish_hour"),
            F.col("crawl_latency_minutes"),
            F.col("crawled_timestamp").alias("crawled_at"),
            F.current_timestamp().alias("loaded_at"),
        ).fillna({"author": "", "content": "", "category": ""})

        write_to_clickhouse_batch(output_df, table)
        print(f"[ClickHouse] Batch {batch_id}: wrote {output_df.count()} records to {table}")

    return (
        df.writeStream
        .foreachBatch(_write_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/clickhouse")
        .start()
    )