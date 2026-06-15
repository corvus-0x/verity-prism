"""
Golden fixtures for the brief eval harness. Each is a small, hand-authored
workspace whose notable facts are known by construction. Domain-neutral
(engine-level); Catalyst fraud fixtures come later, reusing this harness.

Fixture shape:
  id, vertical, documents[{key, doc_type, sha256, uploaded_at}],
  extractions[{doc, field, value, type, confidence?}],
  must_surface[{fact, salience_type}], expected_clean, thresholds.
"""

GOLDEN_CASES = [
    {
        "id": "outlier_dupe_contradiction",
        "vertical": "general",
        "documents": [
            {"key": "deed1", "doc_type": "DEED", "sha256": "AAA", "uploaded_at": "2021-03-01"},
            {"key": "deed2", "doc_type": "DEED", "sha256": "BBB", "uploaded_at": "2022-07-15"},
            {"key": "deed3", "doc_type": "DEED", "sha256": "AAA", "uploaded_at": "2023-01-04"},
        ],
        "extractions": [
            {"doc": "deed1", "field": "sale_amount", "value": "50000", "type": "currency"},
            {"doc": "deed1", "field": "grantor_name", "value": "Oak Ridge LLC", "type": "name"},
            {"doc": "deed1", "field": "recording_county", "value": "Tulsa", "type": "text"},
            {"doc": "deed1", "field": "recording_date", "value": "2021-03-01", "type": "date"},
            {"doc": "deed2", "field": "sale_amount", "value": "1200000", "type": "currency"},
            {"doc": "deed2", "field": "grantor_name", "value": "Oak Ridge LLC", "type": "name"},
            {"doc": "deed2", "field": "recording_date", "value": "2022-07-15", "type": "date"},
            {"doc": "deed3", "field": "grantor_name", "value": "Oak Ridge LLC", "type": "name"},
            {"doc": "deed3", "field": "recording_county", "value": "Creek", "type": "text"},
        ],
        "must_surface": [
            {
                "fact": "the $1,200,000 sale is the largest value in the set",
                "salience_type": "outlier",
            },
            {
                "fact": "Oak Ridge LLC appears across all three deeds",
                "salience_type": "entity_frequency",
            },
            {"fact": "two of the deeds are duplicate documents", "salience_type": "duplicate"},
            {
                "fact": "the deeds disagree on recording county (Tulsa vs Creek)",
                "salience_type": "contradiction",
            },
            {"fact": "the documents span 2021 to 2022", "salience_type": "coverage_span"},
        ],
        "expected_clean": False,
        "thresholds": {"faithfulness": 0.70, "completeness": 0.60},
    },
    {
        "id": "chronology_missing_field",
        "vertical": "general",
        "schema": {
            "document_type": "DEED",
            "fields": [
                {"name": "recording_date", "type": "date", "required": True},
                {"name": "grantor_name", "type": "name", "required": True},
            ],
        },
        "documents": [
            {"key": "deedA", "doc_type": "DEED", "sha256": "C1", "uploaded_at": "2020-01-10"},
            {"key": "deedB", "doc_type": "DEED", "sha256": "C2", "uploaded_at": "2023-06-01"},
        ],
        "extractions": [
            {"doc": "deedA", "field": "recording_date", "value": "2020-01-10", "type": "date"},
            {
                "doc": "deedA",
                "field": "grantor_name",
                "value": "Alpha Holdings LLC",
                "type": "name",
            },
            {"doc": "deedB", "field": "recording_date", "value": "2023-06-01", "type": "date"},
        ],
        "must_surface": [
            {"fact": "the deeds form a timeline from 2020 to 2023", "salience_type": "chronology"},
            {
                "fact": "deedB is missing its required grantor name",
                "salience_type": "missing_field",
            },
        ],
        "expected_clean": False,
        "thresholds": {"faithfulness": 0.70, "completeness": 0.60},
    },
    {
        "id": "multi_doc_clean",
        "vertical": "general",
        "documents": [
            {"key": "docA", "doc_type": "DEED", "sha256": "Z1", "uploaded_at": "2021-05-01"},
            {"key": "docB", "doc_type": "DEED", "sha256": "Z2", "uploaded_at": "2021-05-02"},
            {"key": "docC", "doc_type": "DEED", "sha256": "Z3", "uploaded_at": "2021-05-03"},
        ],
        "extractions": [
            {
                "doc": "docA",
                "field": "legal_description",
                "value": "Lot 1, Block A",
                "type": "text",
            },
            {"doc": "docB", "field": "survey_reference", "value": "Survey ref 7-Q", "type": "text"},
            {"doc": "docC", "field": "plat_title", "value": "Plat C", "type": "text"},
        ],
        "must_surface": [],
        "expected_clean": True,
        "thresholds": {"faithfulness": 0.70, "completeness": 0.60},
    },
    {
        "id": "single_doc_minimal",
        "vertical": "general",
        "documents": [
            {"key": "docX", "doc_type": "DEED", "sha256": "Y1", "uploaded_at": "2022-02-02"},
        ],
        "extractions": [
            {"doc": "docX", "field": "grantor_name", "value": "Solo Holdings LLC", "type": "name"},
        ],
        "must_surface": [],
        "expected_clean": True,
        "thresholds": {"faithfulness": 0.70, "completeness": 0.60},
    },
]
