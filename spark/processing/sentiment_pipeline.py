import logging
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    FloatType,
)

logger = logging.getLogger(__name__)

SENTIMENT_SCHEMA = StructType([
    StructField("sentiment_score", FloatType(), False),
    StructField("sentiment_label", StringType(), False),
])

# Global variables for Spark executors
_sentiment_pipeline = None

def _get_pipeline():
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        try:
            import os
            os.environ["HF_HOME"] = "/tmp/hf_cache"
            os.environ["TRANSFORMERS_CACHE"] = "/tmp/hf_cache"
            from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
            model_id = "wonrax/phobert-base-vietnamese-sentiment"
            logger.info(f"Loading Sentiment model {model_id}")
            # Use PyTorch pipeline for now, ready for ONNX export
            _sentiment_pipeline = pipeline("sentiment-analysis", model=model_id, tokenizer=model_id)
        except Exception as e:
            logger.error(f"Failed to load Sentiment model: {e}")
            _sentiment_pipeline = lambda x: [{"label": "NEU", "score": 1.0}]
            
    return _sentiment_pipeline


def analyze_sentiment(text: str) -> dict:
    if not text or len(text.strip()) < 10:
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}
        
    try:
        nlp = _get_pipeline()
        # Truncate text to avoid exceeding max length of 256 tokens for PhoBERT
        text = text[:1000] 
        result = nlp(text)[0] # e.g. {'label': 'POS', 'score': 0.99}
    except Exception as e:
        logger.error(f"Sentiment extraction error: {e}")
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}
        
    label_map = {
        "POS": "positive",
        "NEG": "negative",
        "NEU": "neutral"
    }
    
    label = result.get("label", "NEU")
    score = result.get("score", 0.0)
    
    # Map back to continuous score -1.0 to 1.0 for dashboard compatibility
    if label == "POS":
        mapped_score = score
    elif label == "NEG":
        mapped_score = -score
    else:
        mapped_score = 0.0
        
    return {
        "sentiment_score": float(mapped_score),
        "sentiment_label": label_map.get(label, "neutral")
    }

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
