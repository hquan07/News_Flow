import hashlib
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, ArrayType

from config.spark_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPICS,
    KAFKA_CONSUMER_GROUP,
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


def create_kafka_stream(spark: SparkSession) -> DataFrame:
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", ",".join(KAFKA_TOPICS))
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 500)
        .load()
    )

    return (
        raw_stream
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.from_json(F.col("value").cast("string"), ARTICLE_SCHEMA).alias("article"),
        )
        .select("kafka_topic", "kafka_partition", "kafka_offset", "kafka_timestamp", "article.*")
        .filter(F.col("url").isNotNull() & F.col("title").isNotNull())
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

def create_social_kafka_stream(spark: SparkSession) -> DataFrame:
    raw_stream = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", "social_posts")
        .option("startingOffsets", "earliest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 500)
        .load()
    )

    return (
        raw_stream
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.from_json(F.col("value").cast("string"), SOCIAL_SCHEMA).alias("post"),
        )
        .select("kafka_topic", "kafka_partition", "kafka_offset", "kafka_timestamp", "post.*")
        .filter(F.col("post_id").isNotNull())
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