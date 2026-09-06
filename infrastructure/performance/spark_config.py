from pyspark.sql import SparkSession


def get_optimized_spark_session(
    app_name: str = "NewsPulse-Streaming",
    master: str = "spark://spark-master:7077",
    kafka_bootstrap: str = "kafka:9092",
    total_ram_gb: int = 8,
) -> SparkSession:
    # ── Memory allocation ──
    # Rule of thumb: Spark dùng ~50-60% RAM, còn lại cho OS + other services
    driver_mem = max(1, total_ram_gb // 4)           # 25% cho driver
    executor_mem = max(1, total_ram_gb * 3 // 8)     # 37.5% cho executor
    overhead_mem = max(384, executor_mem * 1024 // 10)  # 10% overhead (MB)

    builder = (
        SparkSession.builder
        .appName(app_name)
        .master(master)

        # ── Memory ──
        .config("spark.driver.memory", f"{driver_mem}g")
        .config("spark.executor.memory", f"{executor_mem}g")
        .config("spark.executor.memoryOverhead", f"{overhead_mem}m")
        .config("spark.memory.fraction", "0.6")          # Default 0.6
        .config("spark.memory.storageFraction", "0.3")    # Giảm từ 0.5 — ưu tiên execution

        # ── Parallelism ──
        .config("spark.executor.cores", "2")
        .config("spark.default.parallelism", "6")         # 3 partitions/topic × 2
        .config("spark.sql.shuffle.partitions", "6")      # Match parallelism

        # ── Kafka Structured Streaming ──
        .config("spark.sql.streaming.kafka.consumer.cache.capacity", "64")
        .config("spark.streaming.kafka.maxRatePerPartition", "500")
        .config("spark.sql.streaming.minBatchesToRetain", "2")

        # Micro-batch interval: trigger every 30s (balance latency vs throughput)
        # Set in readStream, not here — but document for reference

        # ── Serialization ──
        .config("spark.serializer", "org.apache.spark.serializer.KryoSerializer")
        .config("spark.kryoserializer.buffer.max", "256m")

        # ── Adaptive Query Execution (Spark 3.x) ──
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.sql.adaptive.skewJoin.enabled", "true")

        # ── Write optimization ──
        .config("spark.sql.sources.partitionOverwriteMode", "dynamic")

        # ── UI ──
        .config("spark.ui.port", "8082")
        .config("spark.ui.retainedJobs", "50")
        .config("spark.ui.retainedStages", "50")

        # ── Logging ──
        .config("spark.eventLog.enabled", "true")
        .config("spark.eventLog.dir", "/opt/spark/logs")

        # ── Checkpointing (required for Structured Streaming) ──
        .config("spark.sql.streaming.checkpointLocation", "/opt/spark/checkpoints")

        # ── GC tuning ──
        .config("spark.executor.extraJavaOptions",
                "-XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35 "
                "-XX:+ParallelRefProcEnabled")
        .config("spark.driver.extraJavaOptions",
                "-XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35")
    )

    return builder.getOrCreate()


# Streaming read helpers with optimized configs
def read_kafka_stream(spark: SparkSession, topics: str, kafka_bootstrap: str = "kafka:9092"):
    return (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", kafka_bootstrap)
        .option("subscribe", topics)
        .option("startingOffsets", "latest")
        .option("maxOffsetsPerTrigger", 1000)       # Limit batch size
        .option("failOnDataLoss", "false")           # Don't crash on topic changes
        .option("kafka.consumer.request.timeout.ms", "60000")
        .option("kafka.consumer.session.timeout.ms", "30000")
        .option("kafka.consumer.max.poll.records", "500")
        .load()
    )


# spark-defaults.conf content (for spark-submit)
SPARK_DEFAULTS_CONF = """
# NewsPulse Spark Defaults — optimized for on-premise (8-16GB RAM)
# File: $SPARK_HOME/conf/spark-defaults.conf

spark.master                            spark://spark-master:7077
spark.driver.memory                     2g
spark.executor.memory                   3g
spark.executor.cores                    2
spark.executor.memoryOverhead           384m

spark.default.parallelism               6
spark.sql.shuffle.partitions            6

spark.serializer                        org.apache.spark.serializer.KryoSerializer
spark.kryoserializer.buffer.max         256m

spark.sql.adaptive.enabled              true
spark.sql.adaptive.coalescePartitions.enabled  true
spark.sql.adaptive.skewJoin.enabled     true

spark.memory.fraction                   0.6
spark.memory.storageFraction            0.3

spark.ui.port                           8082
spark.ui.retainedJobs                   50
spark.ui.retainedStages                 50

spark.eventLog.enabled                  true
spark.eventLog.dir                      /opt/spark/logs

spark.sql.streaming.checkpointLocation  /opt/spark/checkpoints
spark.sql.streaming.minBatchesToRetain  2

spark.executor.extraJavaOptions         -XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35 -XX:+ParallelRefProcEnabled
spark.driver.extraJavaOptions           -XX:+UseG1GC -XX:InitiatingHeapOccupancyPercent=35
""".strip()


if __name__ == "__main__":
    # Generate spark-defaults.conf file
    import sys
    output_path = sys.argv[1] if len(sys.argv) > 1 else "spark-defaults.conf"
    with open(output_path, "w") as f:
        f.write(SPARK_DEFAULTS_CONF + "\n")
    print(f"Written to {output_path}")