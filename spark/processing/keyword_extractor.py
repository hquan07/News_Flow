from typing import List, Tuple
from underthesea import word_tokenize
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    StringType,
    StructType,
    StructField,
    FloatType,
)

from config.spark_config import MAX_KEYWORDS_PER_ARTICLE

# Vietnamese stopwords (common words to exclude)
VIETNAMESE_STOPWORDS = {
    "và", "của", "có", "là", "được", "cho", "không", "một",
    "với", "các", "những", "này", "trong", "đã", "từ", "về",
    "theo", "đến", "cũng", "như", "khi", "tại", "nhưng",
    "hay", "để", "đó", "còn", "mà", "người", "nhiều",
    "năm", "sau", "trên", "vào", "ra", "lại", "đang",
    "nên", "sẽ", "rất", "ngày", "thì", "bị", "việc",
    "qua", "ông", "bà", "anh", "chị", "em", "tôi",
    "hơn", "nếu", "vì", "do", "bởi", "giữa", "dưới",
    "cần", "phải", "nào", "đều", "lên", "đi", "làm",
    "biết", "thế", "chỉ", "mới", "rồi", "khác", "trước",
}

# Schema for keyword output
KEYWORD_SCHEMA = ArrayType(
    StructType([
        StructField("keyword", StringType(), False),
        StructField("score", FloatType(), False),
    ])
)


def segment_vietnamese(text: str) -> List[str]:
    if not text:
        return []

    tokens = word_tokenize(text, format="list")

    # Filter: remove stopwords, punctuation, short tokens
    filtered = [
        token.lower().replace(" ", "_")
        for token in tokens
        if (
                token.lower() not in VIETNAMESE_STOPWORDS
                and len(token) > 1
                and not token.isdigit()
                and any(c.isalpha() for c in token)
        )
    ]

    return filtered


def extract_keywords_tfidf(text: str, max_keywords: int = MAX_KEYWORDS_PER_ARTICLE) -> List[Tuple[str, float]]:
    tokens = segment_vietnamese(text)

    if not tokens:
        return []

    # Compute term frequency
    tf = {}
    for token in tokens:
        tf[token] = tf.get(token, 0) + 1

    total_tokens = len(tokens)

    # Normalize TF scores
    scored = [
        (word, round(count / total_tokens, 4))
        for word, count in tf.items()
    ]

    # Sort by score descending, take top N
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:max_keywords]


# Register as UDF
@F.udf(returnType=KEYWORD_SCHEMA)
def extract_keywords_udf(content: str) -> list:
    if not content:
        return []

    keywords = extract_keywords_tfidf(content)
    return [{"keyword": kw, "score": score} for kw, score in keywords]


def apply_keyword_extraction(df: DataFrame) -> DataFrame:
    return (
        df
        .withColumn("keywords", extract_keywords_udf(F.col("content_clean")))
        .withColumn("keyword_count", F.size(F.col("keywords")))
    )