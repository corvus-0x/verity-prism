"""
Field validator — applies per-field validation rules defined in schema_fields JSON.

validate_extractions() is a pure function: no DB access, no side effects.
Called in the pipeline after extraction and before confidence evaluation.
"""
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    field_name: str
    rule: str        # "required" | "min_length" | "max_length" | "pattern"
    message: str


def validate_extractions(
    extractions: list[dict],
    schema_fields: list[dict],
) -> list[ValidationError]:
    """
    Validate extracted field values against per-field validation rules.

    schema_fields entries may include a "validation" dict with keys:
      required: bool — field must have a non-empty value
      min_length: int — minimum character count
      max_length: int — maximum character count
      pattern: str — regex the value must fully match

    Fields without a "validation" key are skipped.
    Returns a list of ValidationErrors (empty = all passed).
    """
    latest: dict[str, str | None] = {}
    for e in extractions:
        name = e.get("field_name")
        if name:
            latest[name] = e.get("field_value")

    errors: list[ValidationError] = []

    for field in schema_fields:
        name = field.get("name")
        rules = field.get("validation")
        if not name or not rules:
            continue

        value = latest.get(name)

        if rules.get("required") and not value:
            errors.append(ValidationError(
                field_name=name,
                rule="required",
                message=f"'{name}' is required but was not extracted",
            ))
            continue

        if not value:
            continue

        if "min_length" in rules and len(value) < rules["min_length"]:
            errors.append(ValidationError(
                field_name=name,
                rule="min_length",
                message=f"'{name}' must be at least {rules['min_length']} characters (got {len(value)})",
            ))

        if "max_length" in rules and len(value) > rules["max_length"]:
            errors.append(ValidationError(
                field_name=name,
                rule="max_length",
                message=f"'{name}' must be at most {rules['max_length']} characters (got {len(value)})",
            ))

        if "pattern" in rules:
            try:
                if not re.fullmatch(rules["pattern"], value):
                    errors.append(ValidationError(
                        field_name=name,
                        rule="pattern",
                        message=f"'{name}' value '{value}' does not match required pattern",
                    ))
            except re.error as exc:
                logger.warning(f"Invalid regex pattern for field '{name}': {exc}")

    return errors
