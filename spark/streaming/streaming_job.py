import signal
import sys

from loguru import logger
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from config.spark_config import (
    CHECKPOINT_PATHS,
    NLP_MAX_OFFSETS_PER_TRIGGER,
    NLP_STARTING_OFFSETS,
    NLP_STREAMING_TRIGGER_INTERVAL,
    RAW_MAX_OFFSETS_PER_TRIGGER,
    RAW_STARTING_OFFSETS,
    RAW_STREAMING_TRIGGER_INTERVAL,
    SOCIAL_MAX_OFFSETS_PER_TRIGGER,
    SOCIAL_STARTING_OFFSETS,
    SOCIAL_STREAMING_TRIGGER_INTERVAL,
    SPARK_SINGLETON_LOCK,
)
from spark.processing.clickbait_detector import apply_clickbait_detection
from spark.processing.keyword_extractor import apply_keyword_extraction
from spark.processing.ner_pipeline import apply_ner_extraction
from spark.processing.sentiment_pipeline import (
    apply_sentiment_analysis,
    apply_social_sentiment_analysis,
)
from spark.processing.text_processor import apply_text_cleaning
from spark.streaming.kafka_consumer import create_kafka_stream, create_social_kafka_stream
from spark.streaming.nlp_writers import (
    write_clickbait_to_clickhouse,
    write_entities_to_clickhouse,
    write_keywords_to_clickhouse,
    write_sentiment_to_clickhouse,
)
from spark.streaming.sink_writers import create_dead_letter_writer, write_to_clickhouse_batch
from spark.utils.singleton_lock import acquire_singleton_lock, validate_unique_checkpoints
from spark.utils.spark_session import create_spark_session


def _valid_records(stream: DataFrame) -> DataFrame:
    return stream.filter(F.col("parse_error").isNull()).drop("raw_payload", "parse_error")


def _raw_article_output(batch_df: DataFrame) -> DataFrame:
    """Build raw rows with Spark SQL only; model inference is forbidden here."""
    content = F.coalesce(F.col("content"), F.lit(""))
    parsed_publish_time = F.coalesce(
        F.to_timestamp(F.col("publish_time")),
        F.to_timestamp(F.col("publish_time"), "dd/MM/yyyy HH:mm"),
    )
    publish_time = F.coalesce(
        parsed_publish_time,
        F.to_timestamp(F.col("crawl_time")),
        F.current_timestamp(),
    )
    crawled_at = F.coalesce(F.to_timestamp(F.col("crawl_time")), F.current_timestamp())

    return (
        batch_df.select(
            F.col("url_hash"),
            F.col("url"),
            F.coalesce(F.col("title"), F.lit("")).alias("title"),
            content.alias("content"),
            F.coalesce(F.col("author"), F.lit("")).alias("author"),
            publish_time.alias("publish_time"),
            F.coalesce(F.col("source"), F.lit("")).alias("source"),
            F.lit("").alias("source_domain"),
            F.coalesce(F.lower(F.col("category")), F.lit("general")).alias("category"),
            F.when(F.length(F.trim(content)) == 0, F.lit(0))
            .otherwise(F.size(F.split(F.trim(content), r"\s+")))
            .cast("int")
            .alias("word_count"),
            F.lit(0).cast("int").alias("keyword_count"),
            F.hour(publish_time).cast("short").alias("publish_hour"),
            F.when(
                parsed_publish_time.isNotNull() & F.to_timestamp(F.col("crawl_time")).isNotNull(),
                (
                    F.unix_timestamp(F.to_timestamp(F.col("crawl_time")))
                    - F.unix_timestamp(parsed_publish_time)
                )
                / 60,
            )
            .otherwise(F.lit(0.0))
            .cast("float")
            .alias("crawl_latency_minutes"),
            F.lit(0.0).cast("float").alias("clickbait_score"),
            crawled_at.alias("crawled_at"),
            F.current_timestamp().alias("loaded_at"),
        )
        .filter(F.col("url_hash").isNotNull())
        .dropDuplicates(["url_hash"])
    )


def _write_raw_batch(batch_df: DataFrame, batch_id: int) -> None:
    batch_df.persist()
    try:
        if batch_df.isEmpty():
            return
        output_df = _raw_article_output(batch_df).persist()
        try:
            article_count = output_df.count()
            write_to_clickhouse_batch(output_df, "raw_articles")
            logger.info(
                f"[Raw ingest] Batch {batch_id}: wrote {article_count} records to raw_articles"
            )
        finally:
            output_df.unpersist()
    finally:
        batch_df.unpersist()


def _write_nlp_batch(batch_df: DataFrame, batch_id: int) -> None:
    batch_df.persist()
    try:
        if batch_df.isEmpty():
            return

        kw_count = write_keywords_to_clickhouse(batch_df)
        ent_count = write_entities_to_clickhouse(batch_df)
        sent_count = write_sentiment_to_clickhouse(batch_df)
        clickbait_count = write_clickbait_to_clickhouse(batch_df)
        logger.info(
            f"[NLP enrichment] Batch {batch_id}: {kw_count} keywords, "
            f"{ent_count} entities, {sent_count} sentiment, "
            f"{clickbait_count} clickbait records"
        )
    finally:
        batch_df.unpersist()


def _write_social_batch(batch_df: DataFrame, batch_id: int) -> None:
    batch_df.persist()
    try:
        if batch_df.isEmpty():
            return

        output_df = (
            batch_df.select(
                F.col("post_id"),
                F.col("source"),
                F.col("title"),
                F.col("content"),
                F.col("url"),
                F.col("author"),
                F.col("top_comments"),
                F.col("like_count").cast("int"),
                F.col("upvote_ratio").cast("float"),
                F.col("reply_count").cast("int"),
                F.col("sentiment_score").cast("float"),
                F.col("sentiment_label"),
                F.col("publish_time").cast("timestamp"),
                F.coalesce(F.col("crawl_time").cast("timestamp"), F.current_timestamp()).alias(
                    "crawled_at"
                ),
                F.current_timestamp().alias("loaded_at"),
            )
            .fillna(
                {
                    "title": "",
                    "content": "",
                    "url": "",
                    "author": "",
                    "like_count": 0,
                    "upvote_ratio": 1.0,
                    "reply_count": 0,
                    "sentiment_score": 0.0,
                    "sentiment_label": "neutral",
                }
            )
            .dropDuplicates(["post_id"])
            .persist()
        )
        try:
            post_count = output_df.count()
            write_to_clickhouse_batch(output_df, "social_sentiment_metrics")
            logger.info(
                f"[ClickHouse] Batch {batch_id}: wrote {post_count} records "
                "to social_sentiment_metrics"
            )
        finally:
            output_df.unpersist()
    finally:
        batch_df.unpersist()


def main() -> None:
    logger.info("=" * 60)
    logger.info("NewsPulse Streaming Job — Starting")
    logger.info("=" * 60)

    validate_unique_checkpoints(CHECKPOINT_PATHS)
    singleton_lock = acquire_singleton_lock(SPARK_SINGLETON_LOCK)
    logger.info(f"Acquired singleton lock at {SPARK_SINGLETON_LOCK}")

    spark = None
    queries = []
    try:
        spark = create_spark_session(app_name="NewsPulse-Streaming", is_streaming=True)
        logger.info("SparkSession created successfully")

        # Fast path: new Kafka messages reach raw_articles without waiting for NLP.
        raw_input = create_kafka_stream(
            spark,
            max_offsets_per_trigger=RAW_MAX_OFFSETS_PER_TRIGGER,
            starting_offsets=RAW_STARTING_OFFSETS,
        )
        queries.append(
            create_dead_letter_writer(
                raw_input.filter(F.col("parse_error").isNotNull()),
                CHECKPOINT_PATHS["news_dlq"],
            )
        )
        queries.append(
            _valid_records(raw_input)
            .writeStream.foreachBatch(_write_raw_batch)
            .outputMode("append")
            .trigger(processingTime=RAW_STREAMING_TRIGGER_INTERVAL)
            .option("checkpointLocation", CHECKPOINT_PATHS["news_raw"])
            .start()
        )
        logger.info("Raw article ingest writer started")

        # Slow path: resume the historical checkpoint and enrich independently.
        nlp_input = create_kafka_stream(
            spark,
            max_offsets_per_trigger=NLP_MAX_OFFSETS_PER_TRIGGER,
            starting_offsets=NLP_STARTING_OFFSETS,
        )
        enriched_stream = apply_text_cleaning(_valid_records(nlp_input))
        enriched_stream = apply_keyword_extraction(enriched_stream)
        enriched_stream = apply_ner_extraction(enriched_stream)
        enriched_stream = apply_sentiment_analysis(enriched_stream)
        enriched_stream = apply_clickbait_detection(enriched_stream)
        queries.append(
            enriched_stream.writeStream.foreachBatch(_write_nlp_batch)
            .outputMode("append")
            .trigger(processingTime=NLP_STREAMING_TRIGGER_INTERVAL)
            .option("checkpointLocation", CHECKPOINT_PATHS["news_nlp"])
            .start()
        )
        logger.info("NLP enrichment writer started")

        social_input = create_social_kafka_stream(
            spark,
            max_offsets_per_trigger=SOCIAL_MAX_OFFSETS_PER_TRIGGER,
            starting_offsets=SOCIAL_STARTING_OFFSETS,
        )
        queries.append(
            create_dead_letter_writer(
                social_input.filter(F.col("parse_error").isNotNull()),
                CHECKPOINT_PATHS["social_dlq"],
            )
        )
        social_enriched = apply_social_sentiment_analysis(_valid_records(social_input))
        queries.append(
            social_enriched.writeStream.foreachBatch(_write_social_batch)
            .outputMode("append")
            .trigger(processingTime=SOCIAL_STREAMING_TRIGGER_INTERVAL)
            .option("checkpointLocation", CHECKPOINT_PATHS["social"])
            .start()
        )
        logger.info("Social streaming writer started")

        def shutdown(signum, _frame):
            logger.warning(f"Received signal {signum}, shutting down...")
            for query in queries:
                query.stop()
            spark.stop()

        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)

        logger.info("=" * 60)
        logger.info("Streaming pipeline running. Waiting for data...")
        logger.info("=" * 60)
        spark.streams.awaitAnyTermination()
    finally:
        if spark is not None:
            try:
                spark.stop()
            except Exception:
                pass
        singleton_lock.close()
        logger.info("Released singleton lock")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        logger.exception(f"Streaming pipeline terminated: {exc}")
        sys.exit(1)
