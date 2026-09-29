import hashlib
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, ArrayType

from config.spark_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPICS,
    NLP_MAX_OFFSETS_PER_TRIGGER,
    NLP_STARTING_OFFSETS,
    SOCIAL_MAX_OFFSETS_PER_TRIGGER,
    SOCIAL_STARTING_OFFSETS,
)

ARTICLE_SCHEMA = StructType([
    StructField("url", StringType(), False),
    StructField("title", StringType(), False),
    StructField("content", StringType(), True),
    StructField("raw_html", StringType(), True),
    StructField("category", StringType(), True),
    StructField("source", StringType(), True),
    StructField("author", StringType(), True),
    StructField("publish_time", StringType(), True),
    StructField("crawl_time", StringType(), True),
    StructField("description", StringType(), True),
    StructField("tags", ArrayType(StringType()), True),
    StructField("thumbnail_url", StringType(), True),
])


@F.udf(returnType=StringType())
def md5_hash_udf(url: str) -> str:
    if not url:
        return None
    return hashlib.md5(url.encode()).hexdigest()


def create_kafka_stream(
    spark: SparkSession,
    *,
    max_offsets_per_trigger: int = NLP_MAX_OFFSETS_PER_TRIGGER,
    starting_offsets: str = NLP_STARTING_OFFSETS,
) -> DataFrame:
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", ",".join(KAFKA_TOPICS))
        .option("startingOffsets", starting_offsets)
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", max_offsets_per_trigger)
        .load()
    )

    parsed = (
        raw_stream
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.col("value").cast("string").alias("raw_payload"),
            F.from_json(F.col("value").cast("string"), ARTICLE_SCHEMA).alias("article"),
        )
        .withColumn(
            "parse_error",
            F.when(F.col("article").isNull(), F.lit("invalid_json"))
            .when(F.col("article.url").isNull(), F.lit("missing_url"))
            .when(F.col("article.title").isNull(), F.lit("missing_title")),
        )
    )
    return (
        parsed
        .select(
            "kafka_topic", "kafka_partition", "kafka_offset",
            "kafka_timestamp", "raw_payload", "parse_error", "article.*",
        )
        .withColumn("url_hash", md5_hash_udf(F.col("url")))
        .drop("raw_html")
    )


SOCIAL_SCHEMA = StructType([
    StructField("post_id", StringType(), False),
    StructField("url", StringType(), False),
    StructField("title", StringType(), True),
    StructField("content", StringType(), True),
    StructField("author", StringType(), True),
    StructField("source", StringType(), True),
    StructField("category", StringType(), True),
    StructField("like_count", StringType(), True), # Some crawlers return int, some return float/string, string is safe for parsing
    StructField("upvote_ratio", StringType(), True),
    StructField("reply_count", StringType(), True),
    StructField("top_comments", ArrayType(StringType()), True),
    StructField("publish_time", StringType(), True),
    StructField("crawl_time", StringType(), True),
])

def create_social_kafka_stream(
    spark: SparkSession,
    *,
    max_offsets_per_trigger: int = SOCIAL_MAX_OFFSETS_PER_TRIGGER,
    starting_offsets: str = SOCIAL_STARTING_OFFSETS,
) -> DataFrame:
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", "social_posts")
        .option("startingOffsets", starting_offsets)
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", max_offsets_per_trigger)
        .load()
    )

    parsed = (
        raw_stream
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.col("value").cast("string").alias("raw_payload"),
            F.from_json(F.col("value").cast("string"), SOCIAL_SCHEMA).alias("post"),
        )
        .withColumn(
            "parse_error",
            F.when(F.col("post").isNull(), F.lit("invalid_json"))
            .when(F.col("post.post_id").isNull(), F.lit("missing_post_id")),
        )
    )
    return (
        parsed.select(
            "kafka_topic", "kafka_partition", "kafka_offset",
            "kafka_timestamp", "raw_payload", "parse_error", "post.*",
        )
    )


def create_kafka_batch(spark: SparkSession) -> DataFrame:
    raw_batch = (
        spark.read
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", ",".join(KAFKA_TOPICS))
        .option("startingOffsets", "earliest")
        .option("endingOffsets", "latest")
        .load()
    )

    return (
        raw_batch
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.from_json(F.col("value").cast("string"), ARTICLE_SCHEMA).alias("article"),
        )
        .select("kafka_topic", "kafka_timestamp", "article.*")
        .filter(F.col("url").isNotNull() & F.col("title").isNotNull())
        .withColumn("url_hash", md5_hash_udf(F.col("url")))
        .drop("raw_html")
    )
