from pyspark.sql import DataFrame
from pyspark.sql import functions as F
import clickhouse_connect
import time
from typing import List, Tuple
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
    CLICKHOUSE_INSERT_BATCH_SIZE,
    CLICKHOUSE_WRITE_RETRIES,
    RETRY_BASE_DELAY_SECONDS,
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_DLQ_TOPIC,
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


def _insert_chunk(table: str, columns: List[str], data: List[Tuple]) -> None:
    for attempt in range(1, CLICKHOUSE_WRITE_RETRIES + 1):
        client = None
        try:
            client = _get_clickhouse_client()
            client.insert(table, data, column_names=columns)
            return
        except Exception:
            if attempt == CLICKHOUSE_WRITE_RETRIES:
                raise
            time.sleep(RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
        finally:
            if client is not None:
                client.close()


def _write_partition(rows, table: str, columns: List[str]) -> None:
    chunk = []
    for row in rows:
        chunk.append(tuple(row[column] for column in columns))
        if len(chunk) >= CLICKHOUSE_INSERT_BATCH_SIZE:
            _insert_chunk(table, columns, chunk)
            chunk = []
    if chunk:
        _insert_chunk(table, columns, chunk)


def write_to_clickhouse_batch(df: DataFrame, table: str):
    """Insert one Spark partition at a time without collecting on the driver."""
    if df.isEmpty():
        return
    columns = df.columns
    df.foreachPartition(lambda rows: _write_partition(rows, table, columns))


def create_dead_letter_writer(df: DataFrame, checkpoint_location: str):
    payload = df.select(
        F.concat_ws(
            ":",
            F.col("kafka_topic"),
            F.col("kafka_partition"),
            F.col("kafka_offset"),
        ).cast("string").alias("key"),
        F.to_json(F.struct(
            F.col("parse_error").alias("reason"),
            F.col("raw_payload").alias("payload"),
            F.col("kafka_topic").alias("original_topic"),
            F.col("kafka_partition").alias("original_partition"),
            F.col("kafka_offset").alias("original_offset"),
            F.col("kafka_timestamp").alias("original_timestamp"),
            (
                F.col("schema_version") if "schema_version" in df.columns else F.lit(None)
            ).alias("schema_version"),
            (
                F.col("event_type") if "event_type" in df.columns else F.lit(None)
            ).alias("event_type"),
        )).alias("value"),
    )
    return (
        payload.writeStream
        .format("kafka")
        .queryName("dlq_" + checkpoint_location.rsplit("/", 1)[-1].replace("-", "_"))
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("topic", KAFKA_DLQ_TOPIC)
        .option("checkpointLocation", checkpoint_location)
        .outputMode("append")
        .start()
    )


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
