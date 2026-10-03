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
KAFKA_DLQ_TOPIC = os.getenv("KAFKA_DLQ_TOPIC", "newspulse.dlq")

# Keep raw ingestion responsive while bounding the CPU-heavy NLP backlog.
RAW_MAX_OFFSETS_PER_TRIGGER = max(int(os.getenv("RAW_MAX_OFFSETS_PER_TRIGGER", "500")), 1)
NLP_ENABLED = os.getenv("NLP_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
NLP_MAX_OFFSETS_PER_TRIGGER = max(int(os.getenv("NLP_MAX_OFFSETS_PER_TRIGGER", "20")), 1)
NLP_PROCESSING_PARTITIONS = max(int(os.getenv("NLP_PROCESSING_PARTITIONS", "2")), 1)
CLICKBAIT_ENABLED = os.getenv("CLICKBAIT_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on"
}
SOCIAL_MAX_OFFSETS_PER_TRIGGER = max(int(os.getenv("SOCIAL_MAX_OFFSETS_PER_TRIGGER", "250")), 1)
RAW_STARTING_OFFSETS = os.getenv("RAW_STARTING_OFFSETS", "latest")
NLP_STARTING_OFFSETS = os.getenv("NLP_STARTING_OFFSETS", "earliest")
SOCIAL_STARTING_OFFSETS = os.getenv("SOCIAL_STARTING_OFFSETS", "earliest")


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
SPARK_CHECKPOINT_ROOT = os.getenv("SPARK_CHECKPOINT_ROOT", "/tmp/spark-checkpoints")
SPARK_SINGLETON_LOCK = os.getenv(
    "SPARK_SINGLETON_LOCK",
    f"{SPARK_CHECKPOINT_ROOT}/.newspulse-streaming.lock",
)

CHECKPOINT_PATHS = {
    "news_raw": f"{SPARK_CHECKPOINT_ROOT}/news-raw-v1",
    # Preserve the original path so an existing deployment resumes its NLP offsets.
    "news_nlp": f"{SPARK_CHECKPOINT_ROOT}/main",
    "news_dlq": f"{SPARK_CHECKPOINT_ROOT}/articles-dlq",
    "social": f"{SPARK_CHECKPOINT_ROOT}/social",
    "social_dlq": f"{SPARK_CHECKPOINT_ROOT}/social-dlq",
}

SPARK_CONF = {
    "spark.sql.streaming.checkpointLocation": "/tmp/spark-checkpoints",
    "spark.sql.shuffle.partitions": os.getenv("SPARK_SQL_SHUFFLE_PARTITIONS", "8"),
    "spark.scheduler.mode": "FAIR",
    "spark.executor.cores": os.getenv("SPARK_EXECUTOR_CORES", "4"),
    "spark.executor.memory": os.getenv("SPARK_EXECUTOR_MEMORY", "2g"),
    "spark.driver.memory": os.getenv("SPARK_DRIVER_MEMORY", "2g"),
    "spark.jars.packages": (
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3,"
        "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0"
    ),
}


# Processing Configuration
RAW_STREAMING_TRIGGER_INTERVAL = os.getenv("RAW_STREAMING_TRIGGER_INTERVAL", "5 seconds")
NLP_STREAMING_TRIGGER_INTERVAL = os.getenv("NLP_STREAMING_TRIGGER_INTERVAL", "60 seconds")
SOCIAL_STREAMING_TRIGGER_INTERVAL = os.getenv("SOCIAL_STREAMING_TRIGGER_INTERVAL", "10 seconds")
# Backward-compatible alias for batch utilities that still import the old name.
STREAMING_TRIGGER_INTERVAL = NLP_STREAMING_TRIGGER_INTERVAL
NER_CONFIDENCE_THRESHOLD = 0.6
MAX_KEYWORDS_PER_ARTICLE = 15
TFIDF_MAX_FEATURES = 1000
TFIDF_MIN_DF = 2
CLICKHOUSE_INSERT_BATCH_SIZE = int(os.getenv("CLICKHOUSE_INSERT_BATCH_SIZE", "1000"))
CLICKHOUSE_WRITE_RETRIES = max(int(os.getenv("CLICKHOUSE_WRITE_RETRIES", "3")), 1)
RETRY_BASE_DELAY_SECONDS = float(os.getenv("RETRY_BASE_DELAY_SECONDS", "0.5"))
