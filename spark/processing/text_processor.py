import re
import unicodedata
from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType, IntegerType


@F.udf(returnType=StringType())
def clean_html_udf(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"&#\d+;", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


@F.udf(returnType=IntegerType())
def word_count_udf(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


@F.udf(returnType=StringType())
def normalize_category_udf(category: str) -> str:
    """Map Vietnamese category names to standardized English keys."""
    if not category:
        return "general"

    category = category.lower().strip()

    category_map = {
        "thể thao": "sports", "the-thao": "sports", "bóng đá": "sports", "sports": "sports",
        "công nghệ": "tech", "cong-nghe": "tech", "số hóa": "tech", "khoa học": "tech",
        "khoa-hoc": "tech", "so-hoa": "tech", "tech": "tech", "technology": "tech",
        "kinh doanh": "economy", "kinh-doanh": "economy", "kinh tế": "economy",
        "tài chính": "economy", "bất động sản": "economy", "economy": "economy",
        "thời sự": "politics", "thoi-su": "politics", "chính trị": "politics", "politics": "politics",
        "giải trí": "entertainment", "giai-tri": "entertainment", "entertainment": "entertainment",
        "sức khỏe": "health", "suc-khoe": "health", "health": "health",
        "giáo dục": "education", "giao-duc": "education", "education": "education",
        "thế giới": "world", "the-gioi": "world", "world": "world",
        "pháp luật": "law", "phap-luat": "law", "law": "law",
        "đời sống": "general", "du lịch": "general",
    }

    return category_map.get(category, "general")


def apply_text_cleaning(df: DataFrame) -> DataFrame:
    return (
        df
        .withColumn("title_clean", clean_html_udf(F.col("title")))
        .withColumn("content_clean", clean_html_udf(F.col("content")))
        .withColumn("category_normalized", normalize_category_udf(F.col("category")))
        .withColumn("word_count", word_count_udf(F.col("content_clean")))
        .withColumn(
            "publish_timestamp",
            F.coalesce(
                F.to_timestamp(F.col("publish_time")),
                F.to_timestamp(F.col("publish_time"), "dd/MM/yyyy HH:mm"),
            )
        )
        .withColumn("publish_hour", F.hour(F.col("publish_timestamp")))
        .withColumn("crawled_timestamp", F.to_timestamp(F.col("crawl_time")))
        .withColumn(
            "crawl_latency_minutes",
            F.when(
                F.col("publish_timestamp").isNotNull() & F.col("crawled_timestamp").isNotNull(),
                F.round(
                    (F.unix_timestamp("crawled_timestamp") - F.unix_timestamp("publish_timestamp")) / 60, 1
                ),
            ).otherwise(F.lit(None)),
        )
    )