from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType,
    StructField,
    StringType,
    FloatType,
)

# Basic Vietnamese sentiment dictionary for a rule-based approach
POSITIVE_WORDS = {
    "tốt", "tuyệt vời", "xuất sắc", "thành công", "phát triển", "tăng", 
    "lợi nhuận", "hoàn thành", "cải thiện", "tích cực", "hiệu quả",
    "ủng hộ", "hài lòng", "hạnh phúc", "vui", "thắng", "ổn định", "cứu",
    "khen", "đỉnh", "xuất chúng", "bức phá", "bứt phá", "hoàn hảo", "tín nhiệm"
}

NEGATIVE_WORDS = {
    "xấu", "tồi tệ", "thất bại", "giảm", "lỗ", "thiệt hại", "chậm",
    "tiêu cực", "kém", "phản đối", "thất vọng", "buồn", "thua",
    "bất ổn", "khủng hoảng", "tai nạn", "chết", "bệnh", "lừa đảo",
    "phạm tội", "bắt", "phạt", "từ chức", "đình chỉ", "độc hại", "nguy hiểm",
    "bạo lực", "chiến tranh", "xung đột", "cảnh báo", "lo ngại", "rủi ro"
}


def analyze_sentiment(text: str) -> dict:
    if not text or len(text.strip()) < 10:
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}
        
    text_lower = text.lower()
    
    # Simple word counting
    pos_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    neg_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
    
    total = pos_count + neg_count
    
    if total == 0:
        return {"sentiment_score": 0.0, "sentiment_label": "neutral"}
        
    # Calculate score from -1.0 to 1.0
    score = (pos_count - neg_count) / total
    
    # Determine label
    if score >= 0.2:
        label = "positive"
    elif score <= -0.2:
        label = "negative"
    else:
        label = "neutral"
        
    return {"sentiment_score": float(score), "sentiment_label": label}


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
