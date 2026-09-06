import os

# Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

KAFKA_TOPICS = [
    "news.general",
    "news.sports",
    "news.tech",
    "news.economy",
    "news.politics",
    "news.entertainment",
    "news.health",
    "news.education",
    "news.world",
    "news.law",
]

KAFKA_CONSUMER_GROUP = "newspulse-spark-streaming"


# MongoDB Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongo:27017")
MONGO_DATABASE = os.getenv("MONGO_DB", "newspulse")
MONGO_RAW_COLLECTION = "articles_raw"
MONGO_PROCESSED_COLLECTION = "articles_processed"


# ClickHouse Configuration
CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "clickhouse")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_DB = os.getenv("CLICKHOUSE_DB", "newspulse")
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "admin")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "admin123")


# Spark Session Configuration
SPARK_APP_NAME = "NewsPulse-Streaming"
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://spark-master:7077")

SPARK_CONF = {
    "spark.sql.streaming.checkpointLocation": "/tmp/spark-checkpoints",
    "spark.sql.shuffle.partitions": "4",
    "spark.executor.memory": "1g",
    "spark.driver.memory": "1g",
    "spark.jars.packages": (
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,"
        "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"
    ),
}


# Processing Configuration
STREAMING_TRIGGER_INTERVAL = "30 seconds"
NER_CONFIDENCE_THRESHOLD = 0.6
MAX_KEYWORDS_PER_ARTICLE = 15
TFIDF_MAX_FEATURES = 1000
TFIDF_MIN_DF = 2