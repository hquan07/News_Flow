from api.models.schemas import EntityTypeEnum, TimeRangeEnum
from api.routers.entities import top_entities


def test_top_entities():
    data = top_entities(
        entity_type=None,
        time_range=TimeRangeEnum.week,
        limit=20,
        source=None,
        category=None,
    )
    assert data[0]["entity_name"] == "Việt Nam"


def test_top_entities_filter_by_type():
    data = top_entities(
        entity_type=EntityTypeEnum.LOC,
        time_range=TimeRangeEnum.week,
        limit=20,
        source=None,
        category=None,
    )
    assert all(entity["entity_type"] == "LOC" for entity in data)


def test_entities_with_limit():
    data = top_entities(
        entity_type=None,
        time_range=TimeRangeEnum.week,
        limit=1,
        source=None,
        category=None,
    )
    assert len(data) == 1
