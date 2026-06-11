import pytest

from app.services.connectors.base import (
    ConnectorBase,
    FetchableItem,
    FetchItemResult,
    FetchResult,
    SearchCandidate,
)


def test_dataclasses_carry_expected_fields():
    cand = SearchCandidate(ref="ein-1", display_name="Bright Future Ministries Inc",
                           identifier="12-3456789", location="Marysville, OH")
    assert cand.ref == "ein-1"
    assert cand.display_name.startswith("Bright Future")

    item = FetchableItem(item_ref="2023", label="Form 990", year=2023,
                         item_type="990", filed_date="2024-05-12")
    assert item.year == 2023

    res = FetchResult(items=[
        FetchItemResult(item_ref="2023", status="created", document_id="doc-1"),
        FetchItemResult(item_ref="2021", status="skipped", reason="already in workspace"),
    ])
    assert res.created_count == 1
    assert res.skipped_count == 1
    assert res.failed_count == 0


def test_connectorbase_is_abstract():
    with pytest.raises(TypeError):
        ConnectorBase()
