"""Schema proposal backbone: server-side validation and atomic supersession.

validate_proposal() is the apply gate — it runs regardless of who edited the
draft, because a human reviewer is necessary but not sufficient for an
engine-contract change. supersede_schema() performs the v1->v2 swap in one
transaction so the active-schema invariant is never momentarily violated.
"""

import re

from sqlalchemy.orm import Session

from app.models.document_schema import DocumentSchema
from app.models.schema_proposal import SchemaChangeProposal

VALID_FIELD_TYPES = {"name", "date", "currency", "address", "id_number", "text", "boolean"}
RESERVED_FIELD_NAMES = {
    "id",
    "document_id",
    "workspace_id",
    "schema_id",
    "field_name",
    "field_value",
    "field_type",
    "confidence",
    "ocr_confidence",
    "attempt",
}
_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
_DOC_TYPE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
_THRESHOLD_KEYS = ("confidence_threshold", "ai_threshold", "ocr_threshold")


def validate_proposal(proposal: SchemaChangeProposal, db: Session) -> list[str]:
    """Return a list of validation errors for a proposal; empty list means valid.

    Enforced on apply (not just at draft time): field-name shape/uniqueness,
    known field types, threshold ranges, descriptions, and — for new schemas —
    a normalized document_type with no active collision.
    """
    errors: list[str] = []
    meta = proposal.proposed_schema or {}
    fields = proposal.proposed_fields or []

    if proposal.proposal_type == "new_schema":
        doc_type = meta.get("document_type") or ""
        vertical = meta.get("vertical") or "general"
        if not _DOC_TYPE.match(doc_type):
            errors.append(f"document_type '{doc_type}' must be UPPER-KEBAB (e.g. PARCEL-RECORD)")
        if not (meta.get("display_name") or "").strip():
            errors.append("display_name is required")
        if doc_type:
            existing = (
                db.query(DocumentSchema)
                .filter(
                    DocumentSchema.document_type == doc_type,
                    DocumentSchema.vertical == vertical,
                    DocumentSchema.is_active == True,  # noqa: E712
                )
                .first()
            )
            if existing:
                errors.append(
                    f"an active schema already exists for ({doc_type}, {vertical}) — "
                    "use a schema_extension instead"
                )

    base_names: set[str] = set()
    if proposal.proposal_type == "schema_extension" and proposal.base_schema_id:
        base = db.query(DocumentSchema).filter(DocumentSchema.id == proposal.base_schema_id).first()
        if base:
            base_names = {f.get("name") for f in (base.schema_fields or [])}

    if not fields:
        errors.append("proposal must contain at least one field")

    seen: set[str] = set()
    for f in fields:
        name = f.get("name") or ""
        if not _SNAKE_CASE.match(name):
            errors.append(f"field '{name}' must be snake_case")
        if name in RESERVED_FIELD_NAMES:
            errors.append(f"field '{name}' is a reserved name")
        if name in seen or name in base_names:
            errors.append(f"duplicate field name '{name}'")
        seen.add(name)
        if f.get("type") not in VALID_FIELD_TYPES:
            errors.append(
                f"field '{name}' has invalid field_type '{f.get('type')}' "
                f"(allowed: {', '.join(sorted(VALID_FIELD_TYPES))})"
            )
        if not (f.get("description") or "").strip():
            errors.append(f"field '{name}' is missing a description")
        for key in _THRESHOLD_KEYS:
            if key in f:
                val = f[key]
                if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                    errors.append(f"field '{name}' {key} must be between 0.0 and 1.0")

    return errors


def supersede_schema(db: Session, base: DocumentSchema, new_fields: list[dict]) -> DocumentSchema:
    """Deactivate `base` and insert its successor (version+1) in one transaction.

    Why one transaction: the partial unique index forbids two active schemas for
    the same (document_type, vertical). Deactivating the base and inserting the
    successor must commit together, or the insert would either collide (if base
    stays active) or leave a window with no active schema.
    """
    base.is_active = False
    db.flush()  # release the active slot before inserting the successor
    successor = DocumentSchema(
        document_type=base.document_type,
        vertical=base.vertical,
        display_name=base.display_name,
        schema_fields=new_fields,
        extraction_prompt=base.extraction_prompt,
        version=base.version + 1,
        is_active=True,
        parse_strategy=base.parse_strategy,
        default_confidence_threshold=base.default_confidence_threshold,
    )
    db.add(successor)
    db.commit()
    db.refresh(successor)
    return successor
