import sys
import signal
from loguru import logger
from pyspark.sql import functions as F

from spark.utils.spark_session import create_spark_session
from spark.streaming.kafka_consumer import create_kafka_stream, create_social_kafka_stream
from spark.streaming.sink_writers import create_clickhouse_streaming_writer
from spark.streaming.nlp_writers import (
    write_keywords_to_clickhouse,
    write_entities_to_clickhouse,
    write_sentiment_to_clickhouse,
)
from spark.processing.text_processor import apply_text_cleaning
from spark.processing.keyword_extractor import apply_keyword_extraction
from spark.processing.ner_pipeline import apply_ner_extraction
from spark.processing.sentiment_pipeline import apply_sentiment_analysis, apply_social_sentiment_analysis
from spark.processing.clickbait_detector import apply_clickbait_detection
from config.spark_config import STREAMING_TRIGGER_INTERVAL


def main():
    logger.info("=" * 60)
    logger.info("NewsPulse Streaming Job — Starting")
    logger.info("=" * 60)

    spark = create_spark_session(app_name="NewsPulse-Streaming", is_streaming=True)
    logger.info("SparkSession created successfully")

    raw_stream = create_kafka_stream(spark)
    cleaned_stream = apply_text_cleaning(raw_stream)
    with_keywords = apply_keyword_extraction(cleaned_stream)
    enriched_stream = apply_ner_extraction(with_keywords)
    enriched_stream = apply_sentiment_analysis(enriched_stream)
    enriched_stream = apply_clickbait_detection(enriched_stream)

    def _write_all_batch(batch_df, batch_id):
        if batch_df.isEmpty():
            return
        
        # Persist to avoid recomputing the entire NLP pipeline for each write
        batch_df.persist()
        
        # Write to raw_articles
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
            F.col("clickbait_score"),
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
            "crawl_latency_minutes": 0.0,
            "clickbait_score": 0.0
        })
        
        from spark.streaming.sink_writers import write_to_clickhouse_batch
        write_to_clickhouse_batch(output_df, "raw_articles")
        logger.info(f"[ClickHouse] Batch {batch_id}: wrote {output_df.count()} records to raw_articles")

        # Write to NLP tables
        kw_count = write_keywords_to_clickhouse(batch_df)
        ent_count = write_entities_to_clickhouse(batch_df)
        sent_count = write_sentiment_to_clickhouse(batch_df)
        logger.info(f"[NLP] Batch {batch_id}: {kw_count} keywords, {ent_count} entities, {sent_count} sentiment records")
        
        batch_df.unpersist()

    main_query = (
        enriched_stream.writeStream
        .foreachBatch(_write_all_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/main")
        .start()
    )
    logger.info("Main streaming writer started")

    # ================= SOCIAL STREAMING =================
    social_stream = create_social_kafka_stream(spark)
    social_enriched = apply_social_sentiment_analysis(social_stream)

    def _write_social_batch(batch_df, batch_id):
        if batch_df.isEmpty():
            return
        
        batch_df.persist()
        
        output_df = batch_df.select(
            F.col("post_id"),
            F.col("source"),
            F.col("title"),
            F.col("content"),
            F.col("like_count").cast("int"),
            F.col("upvote_ratio").cast("float"),
            F.col("reply_count").cast("int"),
            F.col("sentiment_score").cast("float"),
            F.col("sentiment_label"),
            F.col("publish_time").cast("timestamp"),
            F.coalesce(F.col("crawl_time").cast("timestamp"), F.current_timestamp()).alias("crawled_at"),
            F.current_timestamp().alias("loaded_at"),
        ).fillna({
            "title": "",
            "content": "",
            "like_count": 0,
            "upvote_ratio": 1.0,
            "reply_count": 0,
            "sentiment_score": 0.0,
            "sentiment_label": "neutral"
        })
        
        from spark.streaming.sink_writers import write_to_clickhouse_batch
        write_to_clickhouse_batch(output_df, "social_sentiment_metrics")
        logger.info(f"[ClickHouse] Batch {batch_id}: wrote {output_df.count()} records to social_sentiment_metrics")
        
        batch_df.unpersist()

    social_query = (
        social_enriched.writeStream
        .foreachBatch(_write_social_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/social")
        .start()
    )
    logger.info("Social streaming writer started")

    def shutdown(signum, frame):
        logger.warning(f"Received signal {signum}, shutting down...")
        main_query.stop()
        social_query.stop()
        spark.stop()
        logger.info("Streaming job stopped gracefully")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("=" * 60)
    logger.info("Streaming pipeline running. Waiting for data...")
    logger.info("=" * 60)

    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()