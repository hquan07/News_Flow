from pyspark.sql import SparkSession
from config.spark_config import (
    SPARK_APP_NAME,
    SPARK_MASTER,
    SPARK_CONF,
)

def create_spark_session(
        app_name: str = SPARK_APP_NAME,
        master: str = SPARK_MASTER,
        is_streaming: bool = False,
) -> SparkSession:
    builder = SparkSession.builder.appName(app_name).master(master)

    # Apply base config
    for key, value in SPARK_CONF.items():
        builder = builder.config(key, value)

    # Streaming-specific config
    if is_streaming:
        builder = builder.config(
            "spark.sql.streaming.forceDeleteTempCheckpointLocation", "true"
        ).config(
            "spark.sql.legacy.timeParserPolicy", "LEGACY"
        )

    session = builder.getOrCreate()

    # Set log level to reduce noise
    session.sparkContext.setLogLevel("WARN")

    return session