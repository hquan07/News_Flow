import hashlib
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    ArrayType,
)

from config.spark_config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_TOPICS,
    KAFKA_CONSUMER_GROUP,
)

# Schema matching the Kafka message produced by Phase 1 crawlers
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
        .option("startingOffsets", "latest")
        .option("failOnDataLoss", "false")
        .option("maxOffsetsPerTrigger", 500)
        .load()
    )

    parsed_stream = (
        raw_stream
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("partition").alias("kafka_partition"),
            F.col("offset").alias("kafka_offset"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.from_json(
                F.col("value").cast("string"),
                ARTICLE_SCHEMA,
            ).alias("article"),
        )
        .select(
            "kafka_topic",
            "kafka_partition",
            "kafka_offset",
            "kafka_timestamp",
            "article.*",
        )
        # Drop messages with missing required fields
        .filter(
            F.col("url").isNotNull()
            & F.col("title").isNotNull()
        )
        .withColumn("url_hash", md5_hash_udf(F.col("url")))
        # Drop raw_html — not needed for processing, saves memory
        .drop("raw_html")
    )

    return parsed_stream


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

    parsed_batch = (
        raw_batch
        .select(
            F.col("topic").alias("kafka_topic"),
            F.col("timestamp").alias("kafka_timestamp"),
            F.from_json(
                F.col("value").cast("string"),
                ARTICLE_SCHEMA,
            ).alias("article"),
        )
        .select("kafka_topic", "kafka_timestamp", "article.*")
        .filter(
            F.col("url").isNotNull()
            & F.col("title").isNotNull()
        )
        .withColumn("url_hash", md5_hash_udf(F.col("url")))
        .drop("raw_html")
    )

    return parsed_batch