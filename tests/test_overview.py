from api.models.schemas import TimeRangeEnum
from api.routers.overview import overview


def test_overview_default():
    data = overview(
        time_range=TimeRangeEnum.week,
        source=None,
        category=None,
    ).model_dump()
    assert "kpi_cards" in data
    assert "articles_by_hour" in data
    assert "category_distribution" in data
    assert "source_speed" in data


def test_overview_kpi_cards():
    data = overview(
        time_range=TimeRangeEnum.today,
        source=None,
        category=None,
    ).model_dump()
    labels = [card["label"] for card in data["kpi_cards"]]
    assert labels == ["Total articles", "Active sources", "Top category", "Avg latency"]


def test_overview_aggregations():
    data = overview(
        time_range=TimeRangeEnum.today,
        source=None,
        category=None,
    ).model_dump()
    assert data["articles_by_hour"][10] == {"hour": "10", "count": 2}
    assert data["category_distribution"] == [{"category": "tech", "count": 2}]
    assert data["sentiment_distribution"] == [{"sentiment": "Positive", "count": 2}]
