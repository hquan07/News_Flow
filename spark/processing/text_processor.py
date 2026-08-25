import re
import unicodedata
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, IntegerType


# UDFs for text processing
@F.udf(returnType=StringType())
def clean_html_udf(text: str) -> str:
    if not text:
        return ""

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Remove HTML entities
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)

    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)

    # Normalize Unicode (NFC form for Vietnamese)
    text = unicodedata.normalize("NFC", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


@F.udf(returnType=IntegerType())
def word_count_udf(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


@F.udf(returnType=StringType())
def normalize_category_udf(category: str) -> str:
    if not category:
        return "general"

    category = category.lower().strip()

    category_map = {
        # Sports
        "thể thao": "sports",
        "the-thao": "sports",
        "bóng đá": "sports",
        "sports": "sports",
        # Technology
        "công nghệ": "tech",
        "cong-nghe": "tech",
        "số hóa": "tech",
        "khoa học": "tech",
        "khoa-hoc": "tech",
        "so-hoa": "tech",
        "tech": "tech",
        "technology": "tech",
        # Economy
        "kinh doanh": "economy",
        "kinh-doanh": "economy",
        "kinh tế": "economy",
        "tài chính": "economy",
        "bất động sản": "economy",
        "economy": "economy",
        # Politics
        "thời sự": "politics",
        "thoi-su": "politics",
        "chính trị": "politics",
        "politics": "politics",
        # Entertainment
        "giải trí": "entertainment",
        "giai-tri": "entertainment",
        "entertainment": "entertainment",
        # Health
        "sức khỏe": "health",
        "suc-khoe": "health",
        "health": "health",
        # Education
        "giáo dục": "education",
        "giao-duc": "education",
        "education": "education",
        # World
        "thế giới": "world",
        "the-gioi": "world",
        "world": "world",
        # Law
        "pháp luật": "law",
        "phap-luat": "law",
        "law": "law",
        # General
        "đời sống": "general",
        "du lịch": "general",
    }

    return category_map.get(category, "general")


# Transformation functions
def apply_text_cleaning(df: DataFrame) -> DataFrame:
    cleaned = (
        df
        # Clean HTML from text fields
        .withColumn("title_clean", clean_html_udf(F.col("title")))
        .withColumn("content_clean", clean_html_udf(F.col("content")))
        # Normalize category (Vietnamese → English key)
        .withColumn("category_normalized", normalize_category_udf(F.col("category")))
        # Word count on cleaned content
        .withColumn("word_count", word_count_udf(F.col("content_clean")))
        # Parse publish_time to proper timestamp
        # Phase 1 sends ISO format from datetime.isoformat()
        .withColumn(
            "publish_timestamp",
            F.coalesce(
                F.to_timestamp(F.col("publish_time"), "yyyy-MM-dd'T'HH:mm:ssXXX"),
                F.to_timestamp(F.col("publish_time"), "yyyy-MM-dd'T'HH:mm:ss"),
                F.to_timestamp(F.col("publish_time"), "yyyy-MM-dd HH:mm:ss"),
                F.to_timestamp(F.col("publish_time"), "dd/MM/yyyy HH:mm"),
            )
        )
        # Extract publish hour from parsed timestamp
        .withColumn("publish_hour", F.hour(F.col("publish_timestamp")))
        # Parse crawl_time (field name from Phase 1, not crawled_at)
        .withColumn(
            "crawled_timestamp",
            F.coalesce(
                F.to_timestamp(F.col("crawl_time"), "yyyy-MM-dd'T'HH:mm:ssXXX"),
                F.to_timestamp(F.col("crawl_time"), "yyyy-MM-dd'T'HH:mm:ss"),
                F.to_timestamp(F.col("crawl_time"), "yyyy-MM-dd HH:mm:ss"),
            )
        )
        # Crawl latency in minutes
        .withColumn(
            "crawl_latency_minutes",
            F.when(
                F.col("publish_timestamp").isNotNull()
                & F.col("crawled_timestamp").isNotNull(),
                F.round(
                    (
                        F.unix_timestamp("crawled_timestamp")
                        - F.unix_timestamp("publish_timestamp")
                    )
                    / 60,
                    1,
                ),
            ).otherwise(F.lit(None)),
        )
    )

    return cleaned