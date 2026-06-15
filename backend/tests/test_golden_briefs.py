from tests.evals.golden_briefs import GOLDEN_CASES

_SALIENCE_TYPES = {
    "outlier",
    "entity_frequency",
    "contradiction",
    "coverage_span",
    "chronology",
    "duplicate",
    "missing_field",
}


def test_fixtures_are_structurally_valid():
    ids = [f["id"] for f in GOLDEN_CASES]
    assert len(ids) == len(set(ids)), "fixture ids must be unique"
    assert len(GOLDEN_CASES) >= 4

    for f in GOLDEN_CASES:
        keys = {d["key"] for d in f["documents"]}
        for e in f["extractions"]:
            assert e["doc"] in keys, f"{f['id']}: extraction references unknown doc {e['doc']}"
        for m in f.get("must_surface", []):
            assert m["salience_type"] in _SALIENCE_TYPES, f"{f['id']}: bad salience_type"
        if f.get("expected_clean"):
            assert f.get("must_surface", []) == [], (
                f"{f['id']}: clean fixture must have empty must_surface"
            )
    assert sum(1 for f in GOLDEN_CASES if f.get("expected_clean")) >= 2


def test_has_a_duplicate_and_a_missing_field_fixture():
    types = {m["salience_type"] for f in GOLDEN_CASES for m in f.get("must_surface", [])}
    assert "duplicate" in types
    assert "missing_field" in types
