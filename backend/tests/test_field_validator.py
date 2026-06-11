"""Field validator — pure function tests, no DB required."""
from app.services.field_validator import validate_extractions


def test_required_field_missing_raises_error():
    extractions = [{"field_name": "ein", "field_value": None}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"required": True}}]
    errors = validate_extractions(extractions, schema_fields)
    assert len(errors) == 1
    assert errors[0].field_name == "ein"
    assert errors[0].rule == "required"


def test_required_field_present_passes():
    extractions = [{"field_name": "ein", "field_value": "12-3456789"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"required": True}}]
    errors = validate_extractions(extractions, schema_fields)
    assert errors == []


def test_min_length_violation():
    extractions = [{"field_name": "ein", "field_value": "123"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"min_length": 9}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.rule == "min_length" for e in errors)


def test_max_length_violation():
    extractions = [{"field_name": "notes", "field_value": "A" * 201}]
    schema_fields = [{"name": "notes", "type": "text", "description": "Notes",
                      "validation": {"max_length": 200}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.rule == "max_length" for e in errors)


def test_regex_pattern_violation():
    extractions = [{"field_name": "ein", "field_value": "not-an-ein"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"pattern": r"^\d{2}-\d{7}$"}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.rule == "pattern" for e in errors)


def test_regex_pattern_passes():
    extractions = [{"field_name": "ein", "field_value": "12-3456789"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"pattern": r"^\d{2}-\d{7}$"}}]
    errors = validate_extractions(extractions, schema_fields)
    assert errors == []


def test_no_validation_rules_passes():
    extractions = [{"field_name": "grantor_name", "field_value": "Jane Smith"}]
    schema_fields = [{"name": "grantor_name", "type": "name", "description": "Grantor"}]
    errors = validate_extractions(extractions, schema_fields)
    assert errors == []


def test_field_not_in_extractions_but_required_is_error():
    """Required field missing entirely from extractions (Claude didn't return it)."""
    extractions = []
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"required": True}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.field_name == "ein" and e.rule == "required" for e in errors)
