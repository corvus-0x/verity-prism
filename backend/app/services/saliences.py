"""
Universal saliences — domain-agnostic cross-document facts computed
deterministically over a workspace's extraction data.

A salience is the middle layer between raw data and judgment: not
"field X = 1250000" (data) and not "this is fraud" (cap judgment), but
"this value is an outlier / these two documents disagree / this entity
recurs". Membership test: it belongs here only if it can be computed
WITHOUT knowing the vertical. Domain rules (e.g. below-appraisal) are cap
detectors registered via signal_registry, never saliences.

Pure module: no DB, no Claude. Callers assemble Evidence/DocumentMeta and
pass them in.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

_NUMERIC = re.compile(r"^-?\d+(\.\d+)?$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")


@dataclass
class Evidence:
    """One extracted field — the citable unit a brief claim references."""

    id: str
    document_id: str
    filename: str
    doc_type: str | None
    field_name: str
    field_value: str | None
    field_type: str = "text"
    confidence: float = 1.0
    ocr_confidence: float = 1.0


@dataclass
class DocumentMeta:
    """Document-level facts (hash, date) saliences need beyond field rows."""

    id: str
    filename: str
    doc_type: str | None
    sha256_hash: str
    uploaded_at: str | None  # ISO-8601 string


@dataclass
class Salience:
    type: str
    description: str
    evidence_ids: list[str] = field(default_factory=list)
    document_ids: list[str] = field(default_factory=list)


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    s = str(value).replace(",", "").replace("$", "").strip()
    return float(s) if _NUMERIC.match(s) else None


def _outlier(evidence: list[Evidence]) -> list[Salience]:
    numeric = [(e, _to_float(e.field_value)) for e in evidence]
    numeric = [(e, n) for e, n in numeric if n is not None]
    if len(numeric) < 2:
        return []
    e, _ = max(numeric, key=lambda t: t[1])
    return [
        Salience(
            "outlier",
            f"Largest numeric value across the set: {e.field_name}={e.field_value} ({e.filename})",
            [e.id],
            [e.document_id],
        )
    ]


def _entity_frequency(evidence: list[Evidence]) -> list[Salience]:
    docs_by_value: dict[str, set] = defaultdict(set)
    ids_by_value: dict[str, list] = defaultdict(list)
    for e in evidence:
        if e.field_type == "name" and e.field_value and e.field_value.strip():
            key = e.field_value.strip().lower()
            docs_by_value[key].add(e.document_id)
            ids_by_value[key].append(e.id)
    out = []
    for key, docs in sorted(docs_by_value.items(), key=lambda kv: -len(kv[1])):
        if len(docs) > 1:
            out.append(
                Salience(
                    "entity_frequency",
                    f"Entity '{key}' appears across {len(docs)} documents",
                    ids_by_value[key],
                    sorted(docs),
                )
            )
    return out


def _contradiction(evidence: list[Evidence]) -> list[Salience]:
    groups: dict[tuple, list] = defaultdict(list)
    for e in evidence:
        if e.field_value and e.field_value.strip():
            groups[(e.doc_type, e.field_name)].append(e)
    out = []
    for (doc_type, field_name), items in groups.items():
        values = {i.field_value.strip().lower() for i in items}
        docs = {i.document_id for i in items}
        if len(values) > 1 and len(docs) > 1:
            out.append(
                Salience(
                    "contradiction",
                    f"Field '{field_name}' disagrees across {len(docs)} "
                    f"{doc_type or 'documents'}: {sorted(values)}",
                    [i.id for i in items],
                    sorted(docs),
                )
            )
    return out


def _dated(evidence: list[Evidence]) -> list[tuple[str, Evidence]]:
    out = []
    for e in evidence:
        if e.field_type == "date" and e.field_value and _ISO_DATE.match(e.field_value.strip()):
            out.append((e.field_value.strip()[:10], e))
    return sorted(out, key=lambda t: t[0])


def _coverage_span(evidence: list[Evidence]) -> list[Salience]:
    dated = _dated(evidence)
    if len(dated) < 2:
        return []
    return [
        Salience(
            "coverage_span",
            f"Document set spans {dated[0][0]} to {dated[-1][0]}",
        )
    ]


def _chronology(evidence: list[Evidence]) -> list[Salience]:
    dated = _dated(evidence)
    if len(dated) < 2:
        return []
    seq = "; ".join(f"{d}: {e.field_name} ({e.filename})" for d, e in dated)
    return [
        Salience(
            "chronology",
            f"Event sequence — {seq}",
            [e.id for _, e in dated],
            sorted({e.document_id for _, e in dated}),
        )
    ]


def _duplicate(documents: list[DocumentMeta]) -> list[Salience]:
    by_hash: dict[str, list] = defaultdict(list)
    for d in documents:
        by_hash[d.sha256_hash].append(d)
    out = []
    for docs in by_hash.values():
        if len(docs) > 1:
            names = ", ".join(d.filename for d in docs)
            out.append(
                Salience(
                    "duplicate",
                    f"Duplicate documents (identical content): {names}",
                    [],
                    [d.id for d in docs],
                )
            )
    return out


def _missing_field(evidence: list[Evidence], required_by_doc: dict[str, set]) -> list[Salience]:
    present: dict[str, set] = defaultdict(set)
    for e in evidence:
        if e.field_value and e.field_value.strip():
            present[e.document_id].add(e.field_name)
    out = []
    for doc_id, required in required_by_doc.items():
        for fname in sorted(required - present.get(doc_id, set())):
            out.append(
                Salience(
                    "missing_field",
                    f"Document {doc_id} missing required field '{fname}'",
                    [],
                    [doc_id],
                )
            )
    return out


def compute_saliences(
    evidence: list[Evidence],
    documents: list[DocumentMeta],
    required_by_doc: dict[str, set] | None = None,
    registered_detectors: list | None = None,
) -> list[Salience]:
    """Compute all universal saliences over the evidence set, then append any
    cap-registered detector output. Deterministic; no DB, no Claude.
    """
    required_by_doc = required_by_doc or {}
    saliences: list[Salience] = []
    saliences += _outlier(evidence)
    saliences += _entity_frequency(evidence)
    saliences += _contradiction(evidence)
    saliences += _coverage_span(evidence)
    saliences += _chronology(evidence)
    saliences += _duplicate(documents)
    saliences += _missing_field(evidence, required_by_doc)
    for detector in registered_detectors or []:
        saliences += detector(evidence, documents)
    return saliences
