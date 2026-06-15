from app.services.saliences import (
    DocumentMeta,
    Evidence,
    Salience,
    compute_saliences,
)


def _ev(id, doc, field, value, ftype="text", filename="d.pdf", doc_type="DEED", conf=1.0):
    return Evidence(
        id=id,
        document_id=doc,
        filename=filename,
        doc_type=doc_type,
        field_name=field,
        field_value=value,
        field_type=ftype,
        confidence=conf,
    )


def _types(saliences):
    return {s.type for s in saliences}


def test_outlier_picks_largest_numeric():
    evidence = [
        _ev("e1", "d1", "sale_amount", "1,250,000.00", "currency"),
        _ev("e2", "d2", "sale_amount", "90000", "currency"),
    ]
    out = [s for s in compute_saliences(evidence, [], {}) if s.type == "outlier"]
    assert len(out) == 1
    assert "1,250,000.00" in out[0].description
    assert out[0].evidence_ids == ["e1"]


def test_outlier_needs_at_least_two_numbers():
    evidence = [_ev("e1", "d1", "sale_amount", "1000", "currency")]
    assert not [s for s in compute_saliences(evidence, [], {}) if s.type == "outlier"]


def test_entity_frequency_across_documents():
    evidence = [
        _ev("e1", "d1", "grantor_name", "Oak Ridge LLC", "name"),
        _ev("e2", "d2", "grantee_name", "Oak Ridge LLC", "name"),
        _ev("e3", "d3", "grantor_name", "Someone Else", "name"),
    ]
    out = [s for s in compute_saliences(evidence, [], {}) if s.type == "entity_frequency"]
    assert len(out) == 1
    assert "oak ridge llc" in out[0].description.lower()
    assert set(out[0].document_ids) == {"d1", "d2"}


def test_contradiction_same_field_differs_across_docs():
    evidence = [
        _ev("e1", "d1", "recording_county", "Tulsa"),
        _ev("e2", "d2", "recording_county", "Creek"),
    ]
    out = [s for s in compute_saliences(evidence, [], {}) if s.type == "contradiction"]
    assert len(out) == 1
    assert "recording_county" in out[0].description


def test_coverage_span_and_chronology_from_date_fields():
    evidence = [
        _ev("e1", "d1", "recording_date", "2022-09-06", "date"),
        _ev("e2", "d2", "recording_date", "2024-01-22", "date"),
    ]
    out = compute_saliences(evidence, [], {})
    span = [s for s in out if s.type == "coverage_span"]
    chrono = [s for s in out if s.type == "chronology"]
    assert span and "2022-09-06" in span[0].description and "2024-01-22" in span[0].description
    assert chrono and chrono[0].description.index("2022-09-06") < chrono[0].description.index(
        "2024-01-22"
    )


def test_duplicate_documents_by_hash():
    docs = [
        DocumentMeta("d1", "a.pdf", "DEED", "HASH_X", "2024-01-01T00:00:00"),
        DocumentMeta("d2", "b.pdf", "DEED", "HASH_X", "2024-01-02T00:00:00"),
        DocumentMeta("d3", "c.pdf", "DEED", "HASH_Y", "2024-01-03T00:00:00"),
    ]
    out = [s for s in compute_saliences([], docs, {}) if s.type == "duplicate"]
    assert len(out) == 1
    assert set(out[0].document_ids) == {"d1", "d2"}


def test_missing_required_field():
    evidence = [_ev("e1", "d1", "grantor_name", "Oak Ridge LLC", "name")]
    required_by_doc = {"d1": {"grantor_name", "recording_date"}}
    out = [s for s in compute_saliences(evidence, [], required_by_doc) if s.type == "missing_field"]
    assert len(out) == 1
    assert "recording_date" in out[0].description


def test_registered_detectors_are_invoked():
    def fake_detector(evidence, documents):
        return [Salience("cap_signal", "fraud rule fired", [], [])]

    out = compute_saliences([], [], {}, registered_detectors=[fake_detector])
    assert "cap_signal" in {s.type for s in out}


def test_clean_set_produces_no_saliences():
    evidence = [_ev("e1", "d1", "grantor_name", "Solo Party", "name")]
    out = compute_saliences(evidence, [], {})
    assert out == []
