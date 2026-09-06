import sys
import signal
from loguru import logger

from spark.utils.spark_session import create_spark_session
from spark.streaming.kafka_consumer import create_kafka_stream
from spark.streaming.sink_writers import (
    create_mongodb_streaming_writer,
    create_clickhouse_streaming_writer,
)
from spark.streaming.nlp_writers import (
    write_keywords_to_clickhouse,
    write_entities_to_clickhouse,
    write_sentiment_to_clickhouse,
)
from spark.processing.text_processor import apply_text_cleaning
from spark.processing.keyword_extractor import apply_keyword_extraction
from spark.processing.ner_pipeline import apply_ner_extraction
from spark.processing.sentiment_pipeline import apply_sentiment_analysis
from config.spark_config import STREAMING_TRIGGER_INTERVAL


def main():
    logger.info("=" * 60)
    logger.info("NewsPulse Streaming Job — Starting")
    logger.info("=" * 60)

    # Create Spark session
    spark = create_spark_session(
        app_name="NewsPulse-Streaming",
        is_streaming=True,
    )
    logger.info("SparkSession created successfully")

    # Step 1: Read from Kafka
    logger.info("Connecting to Kafka topics...")
    raw_stream = create_kafka_stream(spark)

    # Step 2: Apply text cleaning
    logger.info("Setting up text cleaning pipeline...")
    cleaned_stream = apply_text_cleaning(raw_stream)

    # Step 3: Extract keywords
    logger.info("Setting up keyword extraction...")
    with_keywords = apply_keyword_extraction(cleaned_stream)

    # Step 4: Apply NER and Sentiment
    logger.info("Setting up NER pipeline (PhoBERT)...")
    enriched_stream = apply_ner_extraction(with_keywords)
    
    logger.info("Setting up Sentiment pipeline...")
    enriched_stream = apply_sentiment_analysis(enriched_stream)

    # Step 5: Write to sinks
    logger.info("Starting sink writers...")

    # MongoDB sink (full enriched data) - DISABLED (incompatible connector)
    # mongo_query = create_mongodb_streaming_writer(enriched_stream)
    # logger.info("MongoDB streaming writer started")

    # ClickHouse sink (structured columns only)
    clickhouse_query = create_clickhouse_streaming_writer(enriched_stream)
    logger.info("ClickHouse streaming writer started")

    # Keywords + Entities + Sentiment sink (write to raw.article_*)
    def _write_nlp_batch(batch_df, batch_id):
        if batch_df.isEmpty():
            return
        kw_count = write_keywords_to_clickhouse(batch_df)
        ent_count = write_entities_to_clickhouse(batch_df)
        sent_count = write_sentiment_to_clickhouse(batch_df)
        logger.info(
            f"[NLP] Batch {batch_id}: {kw_count} keywords, {ent_count} entities, {sent_count} sentiment records"
        )

    nlp_query = (
        enriched_stream.writeStream
        .foreachBatch(_write_nlp_batch)
        .outputMode("append")
        .option("checkpointLocation", "/tmp/spark-checkpoints/nlp")
        .start()
    )
    logger.info("NLP (keywords + entities + sentiment) streaming writer started")

    # Graceful shutdown handler
    def shutdown(signum, frame):
        logger.warning(f"Received signal {signum}, shutting down...")
        nlp_query.stop()
        clickhouse_query.stop()
        spark.stop()
        logger.info("Streaming job stopped gracefully")
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("=" * 60)
    logger.info("Streaming pipeline running. Waiting for data...")
    logger.info("=" * 60)

    # Block until terminated
    spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()