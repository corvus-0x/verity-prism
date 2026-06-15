# Synthesis Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the engine-level synthesis layer that turns a workspace's `document_extractions` into a grounded brief — a summary plus structured claims, each citing the extraction rows it came from — exposed via a versioned, persisted API.

**Architecture:** A `synthesis_service` assembles a citable evidence set from `document_extractions` (+ document metadata), computes seven domain-agnostic *saliences* (cross-document facts a pure extractor can't produce), then makes one constrained Claude call that may cite *only* the supplied evidence IDs. Citations are validated deterministically and annotated with a grounding confidence derived from the cited rows. A `signal_registry` seam lets vertical caps register extra detectors later without touching the engine. Domain-agnostic throughout — reads only the universal IDP table.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Anthropic Claude API (`claude-sonnet-4-6` via `claude_client.CHAT_MODEL`), pytest.

**Scope note:** This plan covers spec build-order items 1–4 and 7 (model + migration, evidence/saliences, synthesize/validate, router, signal_registry seam). The **eval harness** (spec items 5–6: faithfulness/completeness scorers + golden fixtures) is a **separate follow-up plan** that depends on this one being merged. Spec: `docs/superpowers/specs/2026-06-15-synthesis-layer-eval-harness-design.md`.

**Conventions to follow (from CLAUDE.md):**
- Tests run in Docker against `catalyst_test`:
  `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest <path> -v`
- Services get a concise docstring. Routers/models/schemas do not.
- Mock Claude by patching `app.services.claude_client.get_client` (the single documented patch target).
- Soft deletes: filter `is_deleted == False`. Audit every meaningful action via `audit.log(...)`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `backend/app/models/brief.py` (create) | `Brief` ORM — one row per generated brief version |
| `backend/alembic/versions/<auto>_add_briefs_table.py` (create) | Migration creating `briefs` |
| `backend/app/services/saliences.py` (create) | `Evidence`, `DocumentMeta`, `Salience` dataclasses + `compute_saliences()` and the seven detectors. Pure — no DB, no Claude |
| `backend/app/services/signal_registry.py` (create) | Extension seam: caps register `(evidence, documents) -> list[Salience]` detectors per vertical |
| `backend/app/services/synthesis_service.py` (create) | `_assemble_evidence`, `synthesize_brief`, `store_brief`, `_synthesize`, `_validate_and_annotate` |
| `backend/app/routers/briefs.py` (create) | Thin endpoints: POST generate, GET latest, GET history |
| `backend/app/main.py` (modify) | Register the briefs router |
| `backend/tests/test_saliences.py` (create) | Pure unit tests for every detector |
| `backend/tests/test_synthesis_service.py` (create) | Citation validation + annotation; end-to-end with mocked Claude |
| `backend/tests/test_briefs_api.py` (create) | API: generate/latest/history, versioning, 404, scoping |

---

## Task 1: `Brief` model + migration

**Files:**
- Create: `backend/app/models/brief.py`
- Create: `backend/alembic/versions/<auto>_add_briefs_table.py` (via autogenerate)

- [ ] **Step 1: Write the model**

`backend/app/models/brief.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(
        String, ForeignKey("workspaces.id"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # claims: [{text, sources:[extraction_id...], signal_type, grounding_confidence}]
    claims: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Make the model importable so Alembic and the test truncation see it**

Add to `backend/app/models/__init__.py` (append a line; match existing import style there). If the file does not import models explicitly, skip — the briefs router (Task 6) imports `Brief`, and `main.py` imports the router, so it is registered on `Base.metadata` through that chain. Verify with:

Run: `docker-compose run --rm backend python -c "from app.models.brief import Brief; print(Brief.__tablename__)"`
Expected: prints `briefs`

- [ ] **Step 3: Autogenerate the migration**

Run:
```bash
docker-compose run --rm backend alembic revision --autogenerate -m "add briefs table"
```
Expected: a new file under `backend/alembic/versions/` whose `upgrade()` calls `op.create_table("briefs", ...)` with the columns above and `down_revision` set to the current head. Open it and confirm `create_table("briefs")` is present and no unrelated tables are dropped.

- [ ] **Step 4: Apply the migration**

Run:
```bash
docker-compose run --rm backend alembic upgrade head
```
Expected: `Running upgrade ... -> <rev>, add briefs table`. No errors.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/brief.py backend/app/models/__init__.py backend/alembic/versions/
git commit -m "feat: add briefs table and Brief model"
```

---

## Task 2: Saliences module (pure, no DB / no Claude)

**Files:**
- Create: `backend/app/services/saliences.py`
- Test: `backend/tests/test_saliences.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_saliences.py`:

```python
from app.services.saliences import (
    DocumentMeta,
    Evidence,
    Salience,
    compute_saliences,
)


def _ev(id, doc, field, value, ftype="text", filename="d.pdf", doc_type="DEED", conf=1.0):
    return Evidence(
        id=id, document_id=doc, filename=filename, doc_type=doc_type,
        field_name=field, field_value=value, field_type=ftype, confidence=conf,
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
    assert chrono and chrono[0].description.index("2022-09-06") < chrono[0].description.index("2024-01-22")


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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker-compose run --rm backend pytest tests/test_saliences.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.saliences'`

- [ ] **Step 3: Write the implementation**

`backend/app/services/saliences.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker-compose run --rm backend pytest tests/test_saliences.py -v`
Expected: PASS — all 9 tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/saliences.py backend/tests/test_saliences.py
git commit -m "feat: universal saliences over extraction data"
```

---

## Task 3: `signal_registry` seam

**Files:**
- Create: `backend/app/services/signal_registry.py`
- Test: `backend/tests/test_saliences.py` (extend — registry round-trip)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_saliences.py`:

```python
def test_signal_registry_round_trip():
    from app.services import signal_registry
    from app.services.saliences import Salience

    def detector(evidence, documents):
        return [Salience("below_appraisal", "fired", [], [])]

    signal_registry.register("fraud", detector)
    try:
        assert signal_registry.get_detectors("fraud") == [detector]
        assert signal_registry.get_detectors("insurance") == []
        assert signal_registry.get_detectors(None) == []
    finally:
        signal_registry._registry["fraud"].clear()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `docker-compose run --rm backend pytest tests/test_saliences.py::test_signal_registry_round_trip -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.signal_registry'`

- [ ] **Step 3: Write the implementation**

`backend/app/services/signal_registry.py`:

```python
"""
Signal registry — extension seam for vertical cap signal detectors.

The engine ships the universal saliences (saliences.py). A vertical cap
registers additional domain detectors here over time (e.g. a fraud
"below-appraisal transfer" rule), keyed by vertical. The synthesis engine
and its eval harness never change when a cap adds a detector — open for
extension, closed for modification.

A detector is a callable: (evidence, documents) -> list[Salience].
No detectors are registered by the engine; this is the seam only.
"""
from collections import defaultdict

_registry: dict[str, list] = defaultdict(list)


def register(vertical: str, detector) -> None:
    """Register a cap signal detector under a vertical."""
    _registry[vertical].append(detector)


def get_detectors(vertical: str | None) -> list:
    """Return registered detectors for a vertical (empty list if none/unknown)."""
    if not vertical:
        return []
    return list(_registry.get(vertical, []))
```

- [ ] **Step 4: Run it to verify it passes**

Run: `docker-compose run --rm backend pytest tests/test_saliences.py::test_signal_registry_round_trip -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/signal_registry.py backend/tests/test_saliences.py
git commit -m "feat: signal_registry extension seam for cap detectors"
```

---

## Task 4: `synthesis_service` — validation + annotation (no Claude yet)

**Files:**
- Create: `backend/app/services/synthesis_service.py` (partial — `_validate_and_annotate`)
- Test: `backend/tests/test_synthesis_service.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_synthesis_service.py`:

```python
from app.services.saliences import Evidence
from app.services.synthesis_service import _validate_and_annotate


def _ev(id, conf=1.0):
    return Evidence(
        id=id, document_id="d1", filename="d.pdf", doc_type="DEED",
        field_name="f", field_value="v", field_type="text", confidence=conf,
    )


def test_validate_drops_claims_with_no_valid_citation():
    evidence = [_ev("e1")]
    raw = {
        "summary": "s",
        "claims": [
            {"text": "valid", "sources": ["e1"], "signal_type": "general"},
            {"text": "fabricated", "sources": ["does-not-exist"], "signal_type": "general"},
            {"text": "uncited", "sources": [], "signal_type": "general"},
        ],
    }
    out = _validate_and_annotate(raw, evidence)
    texts = [c["text"] for c in out["claims"]]
    assert texts == ["valid"]
    assert out["summary"] == "s"


def test_validate_filters_unknown_ids_but_keeps_valid_ones():
    evidence = [_ev("e1"), _ev("e2")]
    raw = {"summary": "", "claims": [
        {"text": "mixed", "sources": ["e1", "ghost", "e2"], "signal_type": "general"},
    ]}
    out = _validate_and_annotate(raw, evidence)
    assert out["claims"][0]["sources"] == ["e1", "e2"]


def test_grounding_confidence_is_min_of_cited_rows():
    evidence = [_ev("e1", conf=0.95), _ev("e2", conf=0.40)]
    raw = {"summary": "", "claims": [
        {"text": "c", "sources": ["e1", "e2"], "signal_type": "general"},
    ]}
    out = _validate_and_annotate(raw, evidence)
    assert out["claims"][0]["grounding_confidence"] == 0.4


def test_validate_handles_missing_keys_gracefully():
    out = _validate_and_annotate({}, [])
    assert out == {"summary": "", "claims": []}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker-compose run --rm backend pytest tests/test_synthesis_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.synthesis_service'`

- [ ] **Step 3: Write the partial implementation**

`backend/app/services/synthesis_service.py`:

```python
"""
Synthesis service — the engine's post-extraction intelligence layer.

Turns a workspace's document_extractions into a grounded brief: a summary
plus structured claims, each citing the extraction rows it came from.
Commodity extractors stop at fields; this reads across documents.

Pipeline: _assemble_evidence (DB read + universal saliences) -> _synthesize
(one constrained Claude call that may cite only supplied evidence ids) ->
_validate_and_annotate (drop fabricated citations, attach grounding
confidence from the cited rows).
"""
import logging

from app.services.saliences import Evidence

logger = logging.getLogger(__name__)


def _validate_and_annotate(brief: dict, evidence: list[Evidence]) -> dict:
    """Drop claims that cite no valid evidence id, strip unknown ids from the
    rest, and annotate each surviving claim with grounding_confidence = the
    minimum confidence of its cited rows (so the brief can hedge weak claims).
    """
    by_id = {e.id: e for e in evidence}
    claims = []
    for claim in brief.get("claims", []) or []:
        sources = [s for s in (claim.get("sources") or []) if s in by_id]
        if not sources:
            continue  # unfalsifiable — a claim with no real citation is dropped
        claim["sources"] = sources
        claim["grounding_confidence"] = round(min(by_id[s].confidence for s in sources), 4)
        claims.append(claim)
    return {"summary": brief.get("summary", "") or "", "claims": claims}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker-compose run --rm backend pytest tests/test_synthesis_service.py -v`
Expected: PASS — 4 tests green.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/synthesis_service.py backend/tests/test_synthesis_service.py
git commit -m "feat: brief citation validation + grounding confidence"
```

---

## Task 5: `synthesis_service` — evidence assembly, synthesis call, persistence

**Files:**
- Modify: `backend/app/services/synthesis_service.py` (add `_assemble_evidence`, `_required_fields_by_doc`, `_synthesize`, `synthesize_brief`, `store_brief`)
- Test: `backend/tests/test_synthesis_service.py` (extend — end-to-end with seeded DB + mocked Claude)

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_synthesis_service.py`:

```python
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.models.brief import Brief
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.models.workspace import Workspace
from app.services.synthesis_service import store_brief, synthesize_brief


def _fake_response(payload: dict):
    return SimpleNamespace(
        content=[SimpleNamespace(text=json.dumps(payload))],
        usage=SimpleNamespace(input_tokens=11, output_tokens=22),
    )


def _seed_workspace(db):
    # FKs are enforced (real Postgres) — create a User for created_by/uploaded_by.
    user = User(
        id=str(uuid.uuid4()), email=f"{uuid.uuid4()}@example.com",
        password_hash="x", full_name="Seed User",
    )
    db.add(user)
    ws = Workspace(id=str(uuid.uuid4()), name="Case A", vertical="fraud", created_by=user.id)
    db.add(ws)
    doc = Document(
        id=str(uuid.uuid4()), workspace_id=ws.id, filename="deed1.pdf",
        original_filename="deed1.pdf", file_path="/x", file_type="pdf",
        sha256_hash="HASH1", uploaded_by=user.id, detected_doc_type="DEED",
    )
    db.add(doc)
    ext = DocumentExtraction(
        id="ext-1", document_id=doc.id, workspace_id=ws.id,
        field_name="sale_amount", field_value="1250000", field_type="currency",
        confidence=0.9,
    )
    db.add(ext)
    db.commit()
    return ws, doc, ext


@patch("app.services.claude_client.get_client")
def test_synthesize_brief_end_to_end(mock_get_client, db):
    ws, doc, ext = _seed_workspace(db)
    mock_get_client.return_value.messages.create.return_value = _fake_response(
        {"summary": "One deed.", "claims": [
            {"text": "Sale was 1,250,000", "sources": ["ext-1"], "signal_type": "outlier"},
            {"text": "hallucinated", "sources": ["ghost"], "signal_type": "general"},
        ]}
    )

    brief = synthesize_brief(ws.id, db)

    assert brief["summary"] == "One deed."
    assert [c["text"] for c in brief["claims"]] == ["Sale was 1,250,000"]  # ghost dropped
    assert brief["claims"][0]["grounding_confidence"] == 0.9
    assert brief["model"]  # set from CHAT_MODEL
    assert brief["input_tokens"] == 11 and brief["output_tokens"] == 22
    assert brief["latency_ms"] is not None


@patch("app.services.claude_client.get_client")
def test_store_brief_versions_increment(mock_get_client, db):
    ws, _, _ = _seed_workspace(db)
    b1 = store_brief(ws.id, {"summary": "v1", "claims": []}, db)
    b2 = store_brief(ws.id, {"summary": "v2", "claims": []}, db)
    assert b1.version == 1 and b2.version == 2
    assert db.query(Brief).filter(Brief.workspace_id == ws.id).count() == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `docker-compose run --rm backend pytest tests/test_synthesis_service.py::test_synthesize_brief_end_to_end tests/test_synthesis_service.py::test_store_brief_versions_increment -v`
Expected: FAIL — `ImportError: cannot import name 'synthesize_brief'`

- [ ] **Step 3: Add the implementation**

Add to the top imports of `backend/app/services/synthesis_service.py`:

```python
import time

from sqlalchemy.orm import Session

from app.models.brief import Brief
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace
from app.services import claude_client, signal_registry
from app.services.claude_client import CHAT_MODEL
from app.services.saliences import DocumentMeta, Salience, compute_saliences
from app.utils.json_helpers import strip_json_fences
```

Append the rest to `backend/app/services/synthesis_service.py`:

```python
_SYNTHESIS_SYSTEM = (
    "You are the synthesis layer of a document-intelligence platform. You receive "
    "EVIDENCE (extracted fields, each with an id) and SALIENCES (notable "
    "cross-document facts already computed for you). Write a brief for an operator: "
    "a short summary plus a list of claims. EVERY claim MUST cite one or more "
    "evidence ids in its \"sources\" array, and you may cite ONLY ids that appear in "
    "the evidence. Never assert anything the evidence does not support. If nothing is "
    "notable, say so plainly and return few or no claims. Respond with JSON only: "
    '{"summary": "...", "claims": [{"text": "...", "sources": ["<evidence_id>"], '
    '"signal_type": "<salience type or general>"}]}'
)


def _required_fields_by_doc(docs: list[Document], db: Session) -> dict[str, set]:
    schema_ids = {d.schema_id for d in docs if d.schema_id}
    if not schema_ids:
        return {}
    schemas = {
        s.id: s
        for s in db.query(DocumentSchema).filter(DocumentSchema.id.in_(schema_ids)).all()
    }
    out: dict[str, set] = {}
    for d in docs:
        schema = schemas.get(d.schema_id)
        if not schema:
            continue
        required = {
            f.get("name")
            for f in (schema.schema_fields or [])
            if f.get("required") and f.get("name")
        }
        if required:
            out[d.id] = required
    return out


def _assemble_evidence(workspace_id: str, db: Session):
    """Read the workspace's non-deleted documents and their extraction rows into
    the citable evidence set + document metadata + required-field map. Reads only
    the universal IDP table (document_extractions) plus document/schema metadata —
    no transactions/entities/findings, which are cap-flavored.
    """
    docs = (
        db.query(Document)
        .filter(Document.workspace_id == workspace_id, Document.is_deleted == False)  # noqa: E712
        .all()
    )
    doc_by_id = {d.id: d for d in docs}
    documents = [
        DocumentMeta(
            id=d.id, filename=d.filename, doc_type=d.detected_doc_type,
            sha256_hash=d.sha256_hash,
            uploaded_at=d.uploaded_at.isoformat() if d.uploaded_at else None,
        )
        for d in docs
    ]
    rows = (
        db.query(DocumentExtraction)
        .filter(DocumentExtraction.workspace_id == workspace_id)
        .all()
    )
    evidence = [
        Evidence(
            id=r.id, document_id=r.document_id,
            filename=doc_by_id[r.document_id].filename,
            doc_type=doc_by_id[r.document_id].detected_doc_type,
            field_name=r.field_name, field_value=r.field_value,
            field_type=r.field_type or "text",
            confidence=r.confidence, ocr_confidence=r.ocr_confidence,
        )
        for r in rows
        if r.document_id in doc_by_id  # skip rows whose document is soft-deleted
    ]
    return evidence, documents, _required_fields_by_doc(docs, db)


def _synthesize(evidence: list[Evidence], saliences: list[Salience]) -> tuple[dict, dict]:
    """One constrained Claude call. Returns (parsed_brief, meta). Degrades to an
    empty brief (never raises) if Claude returns unparseable JSON.
    """
    import json

    payload = {
        "evidence": [
            {"id": e.id, "document": e.filename, "doc_type": e.doc_type,
             "field": e.field_name, "value": e.field_value}
            for e in evidence
        ],
        "saliences": [{"type": s.type, "fact": s.description} for s in saliences],
    }
    response = claude_client.get_client().messages.create(
        model=CHAT_MODEL,
        max_tokens=2048,
        system=_SYNTHESIS_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    usage = getattr(response, "usage", None)
    meta = {
        "model": CHAT_MODEL,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    try:
        parsed = json.loads(strip_json_fences(response.content[0].text))
    except Exception as e:
        logger.warning(f"Brief synthesis returned unparseable JSON: {e}")
        parsed = {"summary": "", "claims": []}
    return parsed, meta


def synthesize_brief(workspace_id: str, db: Session) -> dict:
    """Generate a brief dict (summary, claims, model/usage/latency meta) for a
    workspace. No persistence — the eval harness and the router both call this.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    vertical = getattr(workspace, "vertical", None) if workspace else None

    evidence, documents, required_by_doc = _assemble_evidence(workspace_id, db)
    saliences = compute_saliences(
        evidence, documents, required_by_doc, signal_registry.get_detectors(vertical)
    )

    start = time.perf_counter()
    raw, meta = _synthesize(evidence, saliences)
    meta["latency_ms"] = int((time.perf_counter() - start) * 1000)

    brief = _validate_and_annotate(raw, evidence)
    brief.update(meta)
    return brief


def store_brief(workspace_id: str, brief: dict, db: Session) -> Brief:
    """Persist a brief as the next version for the workspace; prior versions are
    retained. Returns the stored row.
    """
    last = (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .first()
    )
    row = Brief(
        workspace_id=workspace_id,
        version=(last.version + 1) if last else 1,
        summary=brief.get("summary", ""),
        claims=brief.get("claims", []),
        model=brief.get("model"),
        latency_ms=brief.get("latency_ms"),
        input_tokens=brief.get("input_tokens"),
        output_tokens=brief.get("output_tokens"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
```

Note: `Evidence` is already imported at the top of the file from Task 4. Leave that import as-is.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `docker-compose run --rm backend pytest tests/test_synthesis_service.py -v`
Expected: PASS — all tests green (the 4 from Task 4 plus the 2 new ones).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/synthesis_service.py backend/tests/test_synthesis_service.py
git commit -m "feat: evidence assembly, constrained synthesis call, brief persistence"
```

---

## Task 6: Briefs router + registration

**Files:**
- Create: `backend/app/routers/briefs.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_briefs_api.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_briefs_api.py`:

```python
import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.workspace import Workspace, WorkspaceMember


def _fake_response(payload):
    return SimpleNamespace(
        content=[SimpleNamespace(text=json.dumps(payload))],
        usage=SimpleNamespace(input_tokens=5, output_tokens=7),
    )


def _seed(db, owner_user_id):
    ws = Workspace(id=str(uuid.uuid4()), name="Case", vertical="fraud", created_by=owner_user_id)
    db.add(ws)
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_user_id, role="owner"))
    doc = Document(
        id=str(uuid.uuid4()), workspace_id=ws.id, filename="d.pdf",
        original_filename="d.pdf", file_path="/x", file_type="pdf",
        sha256_hash="H1", uploaded_by=owner_user_id, detected_doc_type="DEED",
    )
    db.add(doc)
    db.add(DocumentExtraction(
        id="x1", document_id=doc.id, workspace_id=ws.id,
        field_name="sale_amount", field_value="500000", field_type="currency", confidence=0.8,
    ))
    db.commit()
    return ws


def _user_id(client, auth_headers):
    return client.get("/auth/me", headers=auth_headers).json()["id"]


@patch("app.services.claude_client.get_client")
def test_generate_and_get_latest_brief(mock_client, client, auth_headers, db):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {"summary": "ok", "claims": [
            {"text": "sale 500000", "sources": ["x1"], "signal_type": "outlier"},
        ]}
    )
    ws = _seed(db, _user_id(client, auth_headers))

    gen = client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert gen.status_code == 200
    body = gen.json()
    assert body["version"] == 1
    assert body["claims"][0]["sources"] == ["x1"]
    assert body["claims"][0]["grounding_confidence"] == 0.8

    latest = client.get(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["version"] == 1


@patch("app.services.claude_client.get_client")
def test_regenerate_increments_version_and_history(mock_client, client, auth_headers, db):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {"summary": "ok", "claims": []}
    )
    ws = _seed(db, _user_id(client, auth_headers))

    client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)

    history = client.get(f"/workspaces/{ws.id}/briefs", headers=auth_headers)
    assert history.status_code == 200
    versions = [b["version"] for b in history.json()["briefs"]]
    assert versions == [2, 1]  # newest first


def test_latest_brief_404_when_none(client, auth_headers, db):
    ws = _seed(db, _user_id(client, auth_headers))
    resp = client.get(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert resp.status_code == 404


def test_brief_requires_membership(client, auth_headers, db):
    # workspace exists but has NO WorkspaceMember row for this user
    ws = Workspace(
        id=str(uuid.uuid4()), name="Foreign", vertical="fraud",
        created_by=_user_id(client, auth_headers),
    )
    db.add(ws)
    db.commit()
    resp = client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert resp.status_code == 404
```

> Note: `GET /auth/me` returns the authenticated user (`UserOut`, includes `id`) — verified in `backend/app/routers/auth.py`. The seeded `WorkspaceMember.user_id` and `Workspace.created_by` must reference this same id so membership resolves and FK constraints hold.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker-compose run --rm backend pytest tests/test_briefs_api.py -v`
Expected: FAIL — 404s / route not found (`briefs` router not registered).

- [ ] **Step 3: Write the router**

`backend/app/routers/briefs.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.brief import Brief
from app.models.user import User
from app.services import audit
from app.services.auth import get_current_user
from app.services.synthesis_service import store_brief, synthesize_brief

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["briefs"])


def _serialize(row: Brief) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "version": row.version,
        "summary": row.summary,
        "claims": row.claims,
        "model": row.model,
        "latency_ms": row.latency_ms,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


@router.post("/brief")
def generate_brief(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    brief = synthesize_brief(workspace_id, db)
    row = store_brief(workspace_id, brief, db)
    audit.log(
        db, action="brief_generated", user_id=user.id, workspace_id=workspace_id,
        entity_type="brief", entity_id=row.id,
        after_state={"version": row.version, "claim_count": len(row.claims)},
    )
    return _serialize(row)


@router.get("/brief")
def latest_brief(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    row = (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No brief generated yet")
    return _serialize(row)


@router.get("/briefs")
def brief_history(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    rows = (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .all()
    )
    return {"briefs": [_serialize(r) for r in rows], "count": len(rows)}
```

- [ ] **Step 4: Register the router in `backend/app/main.py`**

Add `briefs` to the import block (alphabetical, after `audit`):

```python
from app.routers import (
    ai,
    audit,
    auth,
    briefs,
    connectors,
    documents,
    entities,
    findings,
    leads,
    notes,
    observability,
    review,
    schemas,
    search,
    transactions,
    workspaces,
)
```

And add the include line near the other `include_router` calls:

```python
app.include_router(briefs.router)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker-compose run --rm backend pytest tests/test_briefs_api.py -v`
Expected: PASS — all 4 tests green.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/briefs.py backend/app/main.py backend/tests/test_briefs_api.py
git commit -m "feat: briefs API (generate, latest, history) with audit + versioning"
```

---

## Task 7: Full suite + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the whole backend test suite**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ --ignore=tests/evals -v
```
Expected: PASS — all tests, including the three new files, green. No regressions.

- [ ] **Step 2: Run ruff**

Run: `docker-compose run --rm backend ruff check app/ tests/`
Expected: no errors. Fix any reported issues, then re-run.

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit -m "chore: ruff clean for synthesis layer"
```

(Skip this commit if ruff reported nothing.)

---

## Done criteria

- `briefs` table exists; migration applies cleanly up and down.
- `POST /workspaces/{id}/brief` generates a grounded brief, persists it as the next version, and audits it.
- `GET /workspaces/{id}/brief` returns the latest; `GET /workspaces/{id}/briefs` returns history newest-first.
- Every claim cites real extraction-row ids; fabricated citations are dropped; each claim carries `grounding_confidence`.
- Seven universal saliences computed deterministically; `signal_registry` seam present with no cap detectors registered.
- Full suite green, ruff clean.

## Follow-up (separate plans)
- **Plan 2 — Eval harness:** faithfulness + completeness scorers, hand-authored golden fixtures, `test_brief_quality.py` (spec §7). Depends on this plan merged.
- **Frontend "Case Brief" panel** (spec out-of-scope note).
- **Auto-generation on pipeline events** (spec future work; needs this persistence layer).
