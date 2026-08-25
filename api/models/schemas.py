from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional
from enum import Enum

# Enum
class CategoryEnum(str, Enum):
    sports = "sports"
    tech = "tech"
    economy = "economy"
    politics = "politics"
    general = "general"
    entertainment = "entertainment"
    health = "health"
    education = "education"
    world = "world"
    law = "law"


class SourceEnum(str, Enum):
    vnexpress = "vnexpress"
    tuoitre = "tuoitre"
    thanhnien = "thanhnien"


class EntityTypeEnum(str, Enum):
    PER = "PER"
    LOC = "LOC"
    ORG = "ORG"


class TimeRangeEnum(str, Enum):
    today = "today"
    week = "7d"
    month = "30d"
    all = "all"

# Pagination
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    data: list

# Article schemas
class ArticleBase(BaseModel):
    title: str
    url: str
    source: str
    category: str
    publish_time: Optional[datetime] = None
    word_count: Optional[int] = None


class ArticleDetail(ArticleBase):
    article_id: int
    author: Optional[str] = None
    keyword_count: Optional[int] = None
    crawl_latency_minutes: Optional[float] = None
    keywords: list[str] = []
    entities: list[dict] = []


class ArticleSearchParams(BaseModel):
    q: Optional[str] = Field(default=None, description="Search query (title)")
    source: Optional[SourceEnum] = None
    category: Optional[CategoryEnum] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None

# Overview schemas
class KPICard(BaseModel):
    label: str
    value: int | float | str
    change_pct: Optional[float] = Field(
        default=None, description="% change vs previous period"
    )


class OverviewResponse(BaseModel):
    kpi_cards: list[KPICard]
    articles_by_hour: list[dict]
    category_distribution: list[dict]
    source_speed: list[dict]
    sentiment_distribution: Optional[list[dict]] = []

# Trending schemas
class TrendingKeyword(BaseModel):
    keyword: str
    count: int
    trend: Optional[str] = Field(
        default=None, description="up / down / stable"
    )
    sparkline: list[int] = Field(
        default_factory=list, description="Hourly counts for sparkline"
    )


class KeywordTimeline(BaseModel):
    keyword: str
    data: list[dict] = Field(
        description="List of {date, count} objects"
    )


class CoOccurrence(BaseModel):
    keyword_a: str
    keyword_b: str
    co_count: int


class TrendingResponse(BaseModel):
    top_keywords: list[TrendingKeyword]
    keyword_timeline: Optional[KeywordTimeline] = None
    co_occurrences: list[CoOccurrence] = []

# Source comparison schemas
class SourceCategorySplit(BaseModel):
    source: str
    category: str
    count: int
    percentage: float


class SourceOverlap(BaseModel):
    source_a: str
    source_b: str
    overlap_count: int
    overlap_rate: float


class ReactionTime(BaseModel):
    event_keyword: str
    source: str
    first_published: datetime
    rank: int


class SourceComparisonResponse(BaseModel):
    category_split: list[SourceCategorySplit]
    avg_word_count: list[dict]
    overlap: list[SourceOverlap]
    reaction_times: list[ReactionTime] = []

# Alerts schemas
class SpikeAlert(BaseModel):
    category: str
    current_count: int
    baseline_avg: float
    spike_ratio: float
    window_start: datetime
    window_end: datetime


class NewKeyword(BaseModel):
    keyword: str
    first_seen: datetime
    article_count: int
    source: str


class AlertsResponse(BaseModel):
    spikes: list[SpikeAlert]
    new_keywords: list[NewKeyword]
    category_anomalies: list[dict] = []

# Entity schemas
class EntityStat(BaseModel):
    entity_name: str
    entity_type: str
    mention_count: int
    sources: list[str] = []


class EntityTimeline(BaseModel):
    entity_name: str
    entity_type: str
    data: list[dict] = Field(description="List of {date, count}")


class EntityResponse(BaseModel):
    top_entities: list[EntityStat]
    entity_timeline: Optional[EntityTimeline] = None
    entity_by_category: list[dict] = []