import os
import json
from pyspark.sql import DataFrame
from pyspark.sql.functions import udf
from pyspark.sql.types import FloatType
from loguru import logger
from groq import Groq

# Initialize Groq client only once per executor
_groq_client = None

def get_groq_client():
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None
        _groq_client = Groq(api_key=api_key)
    return _groq_client

def detect_clickbait(title: str) -> float:
    if not title or len(title.strip()) < 10:
        return 0.0
        
    client = get_groq_client()
    if not client:
        return 0.0
        
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a highly accurate clickbait detector for Vietnamese news. "
                               "Return ONLY a float number from 0.0 to 1.0 representing the probability that the title is clickbait, sensational, or misleading. "
                               "0.0 means completely objective and factual, 1.0 means extremely sensational clickbait."
                },
                {
                    "role": "user",
                    "content": f"Title: {title}"
                }
            ],
            model="llama3-8b-8192",
            temperature=0.0,
            max_tokens=10,
        )
        
        response_text = chat_completion.choices[0].message.content.strip()
        score = float(response_text)
        return min(max(score, 0.0), 1.0)
    except Exception as e:
        logger.error(f"Groq API error for clickbait detection: {e}")
        return 0.0

# Register as UDF
clickbait_udf = udf(detect_clickbait, FloatType())

def apply_clickbait_detection(df: DataFrame) -> DataFrame:
    """
    Applies Llama 3 clickbait detection to the 'title_clean' column.
    """
    if os.getenv("GROQ_API_KEY"):
        logger.info("Applying Clickbait Detection with Groq API (Llama 3)")
        return df.withColumn("clickbait_score", clickbait_udf("title_clean"))
    else:
        logger.warning("GROQ_API_KEY not found. Skipping clickbait detection.")
        from pyspark.sql.functions import lit
        return df.withColumn("clickbait_score", lit(0.0).cast(FloatType()))
