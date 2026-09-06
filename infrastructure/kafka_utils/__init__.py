"""
Kafka topic definitions for NewsPulse.
Each news category maps to a dedicated topic for parallel processing.
"""

# Topic prefix
PREFIX = "news"

# Category → Topic mapping
CATEGORY_TOPIC_MAP: dict[str, str] = {
    # Vietnamese category names → topics
    "thể thao": f"{PREFIX}.sports",
    "the-thao": f"{PREFIX}.sports",
    "sports": f"{PREFIX}.sports",

    "công nghệ": f"{PREFIX}.tech",
    "cong-nghe": f"{PREFIX}.tech",
    "khoa học": f"{PREFIX}.tech",
    "khoa-hoc": f"{PREFIX}.tech",
    "số hóa": f"{PREFIX}.tech",
    "so-hoa": f"{PREFIX}.tech",
    "technology": f"{PREFIX}.tech",

    "kinh doanh": f"{PREFIX}.economy",
    "kinh-doanh": f"{PREFIX}.economy",
    "kinh tế": f"{PREFIX}.economy",
    "kinh-te": f"{PREFIX}.economy",
    "tài chính": f"{PREFIX}.economy",
    "tai-chinh": f"{PREFIX}.economy",
    "economy": f"{PREFIX}.economy",

    "thời sự": f"{PREFIX}.politics",
    "thoi-su": f"{PREFIX}.politics",
    "chính trị": f"{PREFIX}.politics",
    "chinh-tri": f"{PREFIX}.politics",
    "politics": f"{PREFIX}.politics",

    "giải trí": f"{PREFIX}.entertainment",
    "giai-tri": f"{PREFIX}.entertainment",
    "văn hóa": f"{PREFIX}.entertainment",
    "van-hoa": f"{PREFIX}.entertainment",
    "entertainment": f"{PREFIX}.entertainment",

    "sức khỏe": f"{PREFIX}.health",
    "suc-khoe": f"{PREFIX}.health",
    "health": f"{PREFIX}.health",

    "giáo dục": f"{PREFIX}.education",
    "giao-duc": f"{PREFIX}.education",
    "education": f"{PREFIX}.education",

    "thế giới": f"{PREFIX}.world",
    "the-gioi": f"{PREFIX}.world",
    "world": f"{PREFIX}.world",

    "pháp luật": f"{PREFIX}.law",
    "phap-luat": f"{PREFIX}.law",
    "law": f"{PREFIX}.law",
}

# Default topic for unmapped categories
DEFAULT_TOPIC = f"{PREFIX}.general"

# All topics (for Kafka init)
ALL_TOPICS = sorted(set(CATEGORY_TOPIC_MAP.values()) | {DEFAULT_TOPIC})


def get_topic(category: str) -> str:
    """Resolve a category string to its Kafka topic."""
    if not category:
        return DEFAULT_TOPIC
    normalized = category.strip().lower()
    return CATEGORY_TOPIC_MAP.get(normalized, DEFAULT_TOPIC)