from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from config.spark_config import (
    MONGO_URI,
    MONGO_DATABASE,
    MONGO_PROCESSED_COLLECTION,
    POSTGRES_URL,
    POSTGRES_PROPERTIES,
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


def write_to_postgres_batch(df: DataFrame, table: str, mode: str = "append"):
    (
        df.write
        .jdbc(
            url=POSTGRES_URL,
            table=table,
            mode=mode,
            properties=POSTGRES_PROPERTIES,
        )
    )


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


def create_postgres_streaming_writer(df: DataFrame, table: str = "raw.articles"):
    def _write_batch(batch_df: DataFrame, batch_id: int):
        if batch_df.isEmpty():
            return

        output_df = batch_df.select(
            F.col("url"),
            F.col("url_hash"),
            F.col("title_clean").alias("title"),
            F.col("content_clean").alias("content"),
            F.col("author"),
            F.col("publish_timestamp").alias("publish_time"),
            F.col("source"),
            F.lit(None).cast("string").alias("source_domain"),
            F.col("category_normalized").alias("category"),
            F.col("word_count"),
            F.col("keyword_count"),
            F.col("publish_hour"),
            F.col("crawl_latency_minutes"),
            F.col("crawled_timestamp").alias("crawled_at"),
            F.current_timestamp().alias("loaded_at"),
        )

        write_to_postgres_batch(output_df, table)
        print(f"[PostgreSQL] Batch {batch_id}: wrote {output_df.count()} records to {table}")

    return (
        df.writeStream
        .foreachBatch(_write_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/postgres")
        .start()
    )