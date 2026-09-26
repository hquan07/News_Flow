from api.models.schemas import TimeRangeEnum
from api.routers.trending import trending_keywords


def test_trending_keywords():
    data = trending_keywords(
        time_range=TimeRangeEnum.week,
        limit=20,
        source=None,
        category=None,
    )
    assert data == [{"keyword": "AI", "count": 2}]


def test_trending_keywords_with_limit():
    data = trending_keywords(
        time_range=TimeRangeEnum.week,
        limit=1,
        source=None,
        category=None,
    )
    assert len(data) == 1
