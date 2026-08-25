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


# PostgreSQL Configuration
PG_HOST = os.getenv("PG_HOST", "postgres")
PG_PORT = int(os.getenv("PG_PORT", "5432"))
PG_DB = os.getenv("PG_DB", "newspulse")
PG_USER = os.getenv("PG_USER", os.getenv("POSTGRES_USER", "newspulse"))
PG_PASSWORD = os.getenv("PG_PASSWORD", os.getenv("POSTGRES_PASSWORD", "newspulse"))

POSTGRES_URL = f"jdbc:postgresql://{PG_HOST}:{PG_PORT}/{PG_DB}"

POSTGRES_PROPERTIES = {
    "user": PG_USER,
    "password": PG_PASSWORD,
    "driver": "org.postgresql.Driver",
}

# SQLAlchemy connection string (for ELT pipeline / non-Spark usage)
SQLALCHEMY_URL = (
    f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)


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
        "org.mongodb.spark:mongo-spark-connector_2.12:10.4.0,"
        "org.postgresql:postgresql:42.7.1"
    ),
}


# Processing Configuration
STREAMING_TRIGGER_INTERVAL = "30 seconds"
NER_CONFIDENCE_THRESHOLD = 0.6
MAX_KEYWORDS_PER_ARTICLE = 15
TFIDF_MAX_FEATURES = 1000
TFIDF_MIN_DF = 2