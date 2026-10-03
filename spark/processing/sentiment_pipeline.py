from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    FloatType,
)

from spark.processing.sentiment_core import (
    SentimentModelUnavailable,
    _get_pipeline,
    analyze_sentiment,
)

SENTIMENT_SCHEMA = StructType([
    StructField("sentiment_score", FloatType(), False),
    StructField("sentiment_label", StringType(), False),
])

@F.udf(returnType=SENTIMENT_SCHEMA)
def analyze_sentiment_udf(content: str):
    return analyze_sentiment(content)


def apply_sentiment_analysis(df: DataFrame) -> DataFrame:
    # Analyze sentiment on the combined title and content
    enriched = df.withColumn(
        "sentiment_result", 
        analyze_sentiment_udf(F.concat_ws(" ", F.col("title"), F.col("content_clean")))
    )
    
    # Extract score and label
    enriched = (
        enriched
        .withColumn("sentiment_score", F.col("sentiment_result.sentiment_score"))
        .withColumn("sentiment_label", F.col("sentiment_result.sentiment_label"))
        .drop("sentiment_result")
    )
    
    return enriched

def apply_social_sentiment_analysis(df: DataFrame) -> DataFrame:
    enriched = df.withColumn(
        "social_text_combined",
        F.concat_ws(" ", F.col("title"), F.col("content"), F.array_join(F.col("top_comments"), " "))
    )
    enriched = enriched.withColumn(
        "sentiment_result", 
        analyze_sentiment_udf(F.col("social_text_combined"))
    )
    
    enriched = (
        enriched
        .withColumn("sentiment_score", F.col("sentiment_result.sentiment_score"))
        .withColumn("sentiment_label", F.col("sentiment_result.sentiment_label"))
        .drop("sentiment_result", "social_text_combined")
    )
    return enriched
