from unittest.mock import patch

from app.services.connectors.base import FetchableItem, SearchCandidate
from app.services.connectors.irs_teos import IrsTeosConnector

_FAKE_INDEX = [
    {"ein": "123456789", "name": "Bright Future Ministries Inc", "location": "Marysville, OH",
     "object_id": "2024050001", "year": 2023, "form_type": "990", "filed_date": "2024-05-12"},
    {"ein": "311789042", "name": "Bright Future Foundation", "location": "Columbus, OH",
     "object_id": "2023040002", "year": 2022, "form_type": "990", "filed_date": "2023-04-30"},
]


def test_search_matches_by_name():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        results = conn.search({"query": "Bright Future"})
    names = {c.display_name for c in results}
    assert "Bright Future Ministries Inc" in names
    assert "Bright Future Foundation" in names
    assert all(isinstance(c, SearchCandidate) for c in results)
    assert any(c.identifier in ("12-3456789", "123456789") for c in results)


def test_search_is_case_insensitive_and_filters():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        results = conn.search({"query": "foundation"})
    assert len(results) == 1
    assert results[0].display_name == "Bright Future Foundation"


def test_list_items_returns_filings_for_ein():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        items = conn.list_items("123456789")
    assert len(items) == 1
    assert isinstance(items[0], FetchableItem)
    assert items[0].year == 2023
    assert items[0].item_type == "990"


def test_search_empty_query_returns_nothing():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        assert conn.search({"query": ""}) == []
