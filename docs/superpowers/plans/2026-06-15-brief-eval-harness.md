# Brief Eval Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest eval harness that measures `synthesize_brief` quality on faithfulness (claim precision) and completeness (salience recall) over hand-authored golden fixtures, with a hybrid gate: deterministic hard asserts + temp-0 LLM-judge scores under loose floors.

**Architecture:** Eval *support modules* and the Claude-calling *runner* live under `backend/tests/evals/` (excluded from CI via `--ignore=tests/evals`). The *pure* scorer/seeder/judge-parse unit tests live at `backend/tests/test_*.py` (CI-collected) and import the support modules from `tests.evals.*` (both are packages). Scorers take an injected judge function so they unit-test without Claude. Only the runner (`@pytest.mark.eval`) makes real synthesis + judge calls.

**Tech Stack:** Python 3.12, pytest, SQLAlchemy, PostgreSQL, Anthropic Claude (`CHAT_MODEL`, temperature 0 for the judge), docker-compose.

**Spec:** `docs/superpowers/specs/2026-06-15-brief-eval-harness-design.md`. Build order = spec §9.

**Conventions:**
- Run tests in Docker: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest <path> -v`
- The Postgres container `verity-prism-db-1` must be up. Don't stop/recreate containers.
- Mock Claude by patching `app.services.claude_client.get_client`.
- Eval-only tests get `@pytest.mark.eval` (already registered in `pytest.ini`); they need a live `ANTHROPIC_API_KEY` and are excluded from CI exactly like `tests/evals/test_deed_extraction.py`.

**Reused from the merged synthesis layer:**
- `app.services.synthesis_service.synthesize_brief(workspace_id, db) -> dict` and `_assemble_evidence(workspace_id, db) -> (evidence, documents, required_by_doc)`.
- `app.services.saliences.compute_saliences(evidence, documents, required_by_doc, registered_detectors)`, and `Evidence` (has `.id`, `.field_name`, `.field_value`).
- `app.services.signal_registry.get_detectors(vertical)`.
- Model fields (verified): `Workspace(name, vertical in {fraud,insurance,general}, created_by→users.id)`; `WorkspaceMember(role in {owner,analyst,viewer})`; `Document(workspace_id, filename, original_filename, file_path, file_type in {pdf,image,csv,text,xml,other}, sha256_hash, uploaded_by→users.id, detected_doc_type, schema_id, uploaded_at)`; `DocumentExtraction(document_id, workspace_id, field_name, field_value, field_type in {name,date,currency,address,id_number,text,boolean}, confidence, attempt default 1)`; `DocumentSchema(document_type, display_name, vertical, schema_fields[list of {name,required,...}], extraction_prompt, version, is_active, parse_strategy, default_confidence_threshold)`; `User(email,password_hash,full_name)`. FKs are enforced — use `db.flush()` between parent/child inserts.

---

## File Structure

| File | Responsibility | CI? |
|------|----------------|-----|
| `backend/tests/evals/brief_seeder.py` | `seed_fixture(fixture, db) -> workspace_id` | support module |
| `backend/tests/evals/golden_briefs.py` | `GOLDEN_CASES`: the 4 fixtures | data module |
| `backend/tests/evals/brief_scorers.py` | `citation_integrity`, `faithfulness`, `completeness` (injected judges) | support module |
| `backend/tests/evals/brief_judge.py` | `judge_support`, `judge_coverage` (temp-0 Claude) | support module |
| `backend/tests/evals/test_brief_quality.py` | `@pytest.mark.eval` runner + scorecard + results JSON | eval-only |
| `backend/tests/evals/README.md` | how to run + sample scorecard | docs |
| `backend/tests/test_brief_seeder.py` | seeder unit test (DB, no Claude) | ✅ CI |
| `backend/tests/test_golden_briefs.py` | fixture structural validation | ✅ CI |
| `backend/tests/test_brief_scorers.py` | scorer unit tests (mocked judge) | ✅ CI |
| `backend/tests/test_brief_judge.py` | judge JSON-parse unit tests (mocked client) | ✅ CI |
| `.gitignore` | ignore `backend/tests/evals/results/` | — |

---

## Task 1: Fixture seeder

**Files:**
- Create: `backend/tests/evals/brief_seeder.py`
- Test: `backend/tests/test_brief_seeder.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_brief_seeder.py`:

```python
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.services.synthesis_service import _assemble_evidence
from tests.evals.brief_seeder import seed_fixture


def test_seed_fixture_creates_queryable_workspace(db):
    fixture = {
        "id": "t", "vertical": "general",
        "documents": [{"key": "d1", "doc_type": "DEED", "sha256": "AAA", "uploaded_at": "2021-03-01"}],
        "extractions": [{"doc": "d1", "field": "sale_amount", "value": "50000",
                         "type": "currency", "confidence": 0.9}],
    }
    ws_id = seed_fixture(fixture, db)

    docs = db.query(Document).filter(Document.workspace_id == ws_id).all()
    exts = db.query(DocumentExtraction).filter(DocumentExtraction.workspace_id == ws_id).all()
    assert len(docs) == 1 and len(exts) == 1

    # the real synthesis assembly must see exactly what we seeded
    evidence, documents, required = _assemble_evidence(ws_id, db)
    assert len(evidence) == 1
    assert evidence[0].field_value == "50000"
    assert documents[0].sha256_hash == "AAA"


def test_seed_fixture_with_schema_sets_required_fields(db):
    fixture = {
        "id": "s", "vertical": "general",
        "schema": {"document_type": "DEED",
                   "fields": [{"name": "recording_date", "required": True},
                              {"name": "grantor_name", "required": True}]},
        "documents": [{"key": "d1", "doc_type": "DEED", "sha256": "H1", "uploaded_at": "2020-01-10"}],
        "extractions": [{"doc": "d1", "field": "recording_date", "value": "2020-01-10", "type": "date"}],
    }
    ws_id = seed_fixture(fixture, db)
    _, _, required = _assemble_evidence(ws_id, db)
    # the one document's required fields include both schema fields
    assert any("grantor_name" in v for v in required.values())
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_brief_seeder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.evals.brief_seeder'`

- [ ] **Step 3: Write the implementation**

`backend/tests/evals/brief_seeder.py`:

```python
"""
Seed a golden eval fixture into the test DB as a real workspace.

Inserts a User (FK), Workspace (with vertical), optional DocumentSchema (for
missing_field fixtures), Documents, and DocumentExtraction rows — so
synthesize_brief runs against it exactly as in production. FKs are enforced;
db.flush() makes each parent visible before its FK-dependent child.
"""
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace


def seed_fixture(fixture: dict, db: Session) -> str:
    """Insert the fixture's workspace/documents/extractions; return workspace_id."""
    vertical = fixture.get("vertical", "general")

    user = User(
        id=str(uuid.uuid4()), email=f"{uuid.uuid4()}@example.com",
        password_hash="x", full_name="Eval Seeder",
    )
    db.add(user)
    db.flush()

    ws = Workspace(
        id=str(uuid.uuid4()), name=f"eval-{fixture['id']}",
        vertical=vertical, created_by=user.id,
    )
    db.add(ws)
    db.flush()

    schema_id = None
    schema_def = fixture.get("schema")
    if schema_def:
        schema = DocumentSchema(
            id=str(uuid.uuid4()),
            document_type=schema_def.get("document_type", "EVAL_DOC"),
            display_name="Eval Schema",
            vertical=vertical,
            schema_fields=schema_def["fields"],
            extraction_prompt="eval",
            version=1, is_active=True, parse_strategy="claude",
            default_confidence_threshold=0.85,
        )
        db.add(schema)
        db.flush()
        schema_id = schema.id

    doc_id_by_key: dict[str, str] = {}
    for d in fixture["documents"]:
        doc = Document(
            id=str(uuid.uuid4()), workspace_id=ws.id,
            filename=f"{d['key']}.pdf", original_filename=f"{d['key']}.pdf",
            file_path=f"/eval/{d['key']}.pdf", file_type="pdf",
            sha256_hash=d["sha256"], uploaded_by=user.id,
            detected_doc_type=d.get("doc_type"),
            schema_id=schema_id,
        )
        if d.get("uploaded_at"):
            doc.uploaded_at = datetime.fromisoformat(d["uploaded_at"])
        db.add(doc)
        db.flush()
        doc_id_by_key[d["key"]] = doc.id

    for e in fixture["extractions"]:
        db.add(DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc_id_by_key[e["doc"]], workspace_id=ws.id,
            field_name=e["field"], field_value=e["value"],
            field_type=e.get("type", "text"),
            confidence=e.get("confidence", 0.95),
        ))
    db.commit()
    return ws.id
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_brief_seeder.py -v`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/evals/brief_seeder.py backend/tests/test_brief_seeder.py
git commit -m "feat: eval fixture seeder for brief quality harness"
```

---

## Task 2: Golden fixtures

**Files:**
- Create: `backend/tests/evals/golden_briefs.py`
- Test: `backend/tests/test_golden_briefs.py`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_golden_briefs.py`:

```python
from tests.evals.golden_briefs import GOLDEN_CASES

_SALIENCE_TYPES = {
    "outlier", "entity_frequency", "contradiction", "coverage_span",
    "chronology", "duplicate", "missing_field",
}


def test_fixtures_are_structurally_valid():
    ids = [f["id"] for f in GOLDEN_CASES]
    assert len(ids) == len(set(ids)), "fixture ids must be unique"
    assert len(GOLDEN_CASES) >= 4

    doc_keys_seen = set()
    for f in GOLDEN_CASES:
        keys = {d["key"] for d in f["documents"]}
        for e in f["extractions"]:
            assert e["doc"] in keys, f"{f['id']}: extraction references unknown doc {e['doc']}"
        for m in f.get("must_surface", []):
            assert m["salience_type"] in _SALIENCE_TYPES, f"{f['id']}: bad salience_type"
        if f.get("expected_clean"):
            assert f.get("must_surface", []) == [], f"{f['id']}: clean fixture must have empty must_surface"
        doc_keys_seen |= keys
    # at least two negative controls
    assert sum(1 for f in GOLDEN_CASES if f.get("expected_clean")) >= 2


def test_has_a_duplicate_and_a_missing_field_fixture():
    types = {m["salience_type"] for f in GOLDEN_CASES for m in f.get("must_surface", [])}
    assert "duplicate" in types
    assert "missing_field" in types
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_golden_briefs.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.evals.golden_briefs'`

- [ ] **Step 3: Write the fixtures**

`backend/tests/evals/golden_briefs.py`:

```python
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
            {"fact": "the $1,200,000 sale is the largest value in the set", "salience_type": "outlier"},
            {"fact": "Oak Ridge LLC appears across all three deeds", "salience_type": "entity_frequency"},
            {"fact": "two of the deeds are duplicate documents", "salience_type": "duplicate"},
            {"fact": "the deeds disagree on recording county (Tulsa vs Creek)", "salience_type": "contradiction"},
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
            {"doc": "deedA", "field": "grantor_name", "value": "Alpha Holdings LLC", "type": "name"},
            {"doc": "deedB", "field": "recording_date", "value": "2023-06-01", "type": "date"},
            # deedB intentionally missing required grantor_name -> missing_field fires
        ],
        "must_surface": [
            {"fact": "the deeds form a timeline from 2020 to 2023", "salience_type": "chronology"},
            {"fact": "deedB is missing its required grantor name", "salience_type": "missing_field"},
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
            {"doc": "docA", "field": "legal_description", "value": "Lot 1, Block A", "type": "text"},
            {"doc": "docB", "field": "legal_description", "value": "Lot 7, Block Q", "type": "text"},
            {"doc": "docC", "field": "legal_description", "value": "Lot 3, Block M", "type": "text"},
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_golden_briefs.py -v`
Expected: PASS — 2 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/evals/golden_briefs.py backend/tests/test_golden_briefs.py
git commit -m "feat: golden brief eval fixtures (4, domain-neutral)"
```

---

## Task 3: Scorers

**Files:**
- Create: `backend/tests/evals/brief_scorers.py`
- Test: `backend/tests/test_brief_scorers.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_brief_scorers.py`:

```python
from app.services.saliences import Evidence
from tests.evals.brief_scorers import citation_integrity, completeness, faithfulness


def _ev(id, field="sale_amount", value="100", ftype="currency", doc="d1"):
    return Evidence(id=id, document_id=doc, filename="f.pdf", doc_type="DEED",
                    field_name=field, field_value=value, field_type=ftype)


def test_citation_integrity_detects_fake_id():
    assert citation_integrity({"claims": [{"text": "x", "sources": ["e1", "ghost"]}]},
                              {"e1": _ev("e1")}) is False
    assert citation_integrity({"claims": [{"text": "x", "sources": ["e1"]}]},
                              {"e1": _ev("e1")}) is True


def test_faithfulness_fraction_supported():
    brief = {"claims": [{"text": "a", "sources": ["e1"]}, {"text": "b", "sources": ["e2"]}]}
    score, flags = faithfulness(brief, {"e1": _ev("e1"), "e2": _ev("e2")},
                                judge_support=lambda claims, ev: [True, False])
    assert score == 0.5 and flags == [True, False]


def test_faithfulness_empty_claims_is_one():
    score, flags = faithfulness({"claims": []}, {}, judge_support=lambda c, e: [])
    assert score == 1.0 and flags == []


def test_completeness_engine_layer_fires_for_outlier():
    evidence = [_ev("e1", value="1200000", doc="d1"), _ev("e2", value="50000", doc="d2")]
    must = [{"fact": "the 1.2M sale is the outlier", "salience_type": "outlier"}]
    brief = {"claims": [{"text": "the $1.2M sale is largest", "sources": ["e1"]}]}
    eng, brf, detail = completeness(must, evidence, [], {}, "general", brief,
                                    judge_coverage=lambda facts, claims: [True])
    assert eng == 1.0          # outlier salience fired over the evidence
    assert brf == 1.0          # judge said the fact was covered
    assert detail["engine"] == [True]


def test_completeness_engine_layer_misses_absent_salience():
    evidence = [_ev("e1", value="100", doc="d1")]   # single number -> no outlier
    must = [{"fact": "outlier", "salience_type": "outlier"}]
    eng, brf, detail = completeness(must, evidence, [], {}, "general",
                                    {"claims": []}, judge_coverage=lambda f, c: [False])
    assert eng == 0.0
    assert detail["engine"] == [False]


def test_completeness_empty_must_surface_is_one():
    eng, brf, detail = completeness([], [], [], {}, "general", {"claims": []},
                                    judge_coverage=lambda f, c: [])
    assert eng == 1.0 and brf == 1.0
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_brief_scorers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.evals.brief_scorers'`

- [ ] **Step 3: Write the implementation**

`backend/tests/evals/brief_scorers.py`:

```python
"""
Brief eval scorers. Deterministic checks are pure; judged checks take an
injected judge function so the scorers unit-test without Claude.

  citation_integrity(brief, evidence_by_id) -> bool          # grounding guarantee guard
  faithfulness(brief, evidence_by_id, judge_support) -> (score, flags)
  completeness(must_surface, evidence, documents, required_by_doc, vertical,
               brief, judge_coverage) -> (engine_score, brief_score, detail)
"""
from app.services import signal_registry
from app.services.saliences import compute_saliences


def citation_integrity(brief: dict, evidence_by_id: dict) -> bool:
    """True iff every cited source id in every claim exists in the evidence set."""
    for claim in brief.get("claims", []):
        for src in claim.get("sources", []):
            if src not in evidence_by_id:
                return False
    return True


def faithfulness(brief: dict, evidence_by_id: dict, judge_support):
    """Fraction of claims whose cited evidence supports the claim text.
    judge_support(claims, evidence_by_id) -> list[bool], one per claim.
    Returns (score, per-claim flags). Score is 1.0 when there are no claims.
    """
    claims = brief.get("claims", [])
    if not claims:
        return 1.0, []
    flags = judge_support(claims, evidence_by_id)
    score = sum(1 for f in flags if f) / len(flags)
    return score, flags


def completeness(must_surface, evidence, documents, required_by_doc, vertical,
                 brief, judge_coverage):
    """Two layers of recall over the planted must_surface facts:
      engine_score: fraction whose salience_type is produced by compute_saliences
                    over the evidence (did the detector fire?).
      brief_score:  fraction asserted by some claim (judge).
    Both are 1.0 when must_surface is empty (negative control — nothing to recall).
    Returns (engine_score, brief_score, detail{engine:[bool], brief:[bool]}).
    """
    if not must_surface:
        return 1.0, 1.0, {"engine": [], "brief": []}

    saliences = compute_saliences(
        evidence, documents, required_by_doc, signal_registry.get_detectors(vertical)
    )
    present_types = {s.type for s in saliences}
    engine_flags = [m["salience_type"] in present_types for m in must_surface]
    engine_score = sum(1 for f in engine_flags if f) / len(must_surface)

    brief_flags = judge_coverage([m["fact"] for m in must_surface], brief.get("claims", []))
    brief_score = (sum(1 for f in brief_flags if f) / len(brief_flags)) if brief_flags else 0.0
    return engine_score, brief_score, {"engine": engine_flags, "brief": brief_flags}
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_brief_scorers.py -v`
Expected: PASS — 6 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/evals/brief_scorers.py backend/tests/test_brief_scorers.py
git commit -m "feat: brief eval scorers (faithfulness + two-layer completeness)"
```

---

## Task 4: LLM judge (temperature 0)

**Files:**
- Create: `backend/tests/evals/brief_judge.py`
- Test: `backend/tests/test_brief_judge.py`

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_brief_judge.py`:

```python
from types import SimpleNamespace
from unittest.mock import patch

from app.services.saliences import Evidence
from tests.evals.brief_judge import judge_coverage, judge_support


def _resp(text):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


@patch("app.services.claude_client.get_client")
def test_judge_support_parses_results_and_uses_temp_0(mock_client):
    mock_client.return_value.messages.create.return_value = _resp('{"results": [true, false]}')
    ev = {"e1": Evidence(id="e1", document_id="d", filename="f", doc_type="DEED",
                         field_name="amt", field_value="100", field_type="currency")}
    claims = [{"text": "a", "sources": ["e1"]}, {"text": "b", "sources": ["e1"]}]

    assert judge_support(claims, ev) == [True, False]
    kwargs = mock_client.return_value.messages.create.call_args.kwargs
    assert kwargs["temperature"] == 0


@patch("app.services.claude_client.get_client")
def test_judge_coverage_parses_results(mock_client):
    mock_client.return_value.messages.create.return_value = _resp('{"results": [true]}')
    assert judge_coverage(["a fact"], [{"text": "a claim"}]) == [True]


def test_judge_support_no_claims_makes_no_call():
    # no patch needed: must short-circuit before touching the client
    assert judge_support([], {}) == []


def test_judge_coverage_no_facts_makes_no_call():
    assert judge_coverage([], [{"text": "x"}]) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_brief_judge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tests.evals.brief_judge'`

- [ ] **Step 3: Write the implementation**

`backend/tests/evals/brief_judge.py`:

```python
"""
LLM judge for brief evals (Claude, temperature 0 for reproducibility).

Two batched calls:
  judge_support(claims, evidence_by_id) -> list[bool]   # one per claim
  judge_coverage(facts, claims)         -> list[bool]   # one per fact
Strict JSON; raises on parse failure (a broken judge must fail loudly, not pass).
"""
import json

from app.services import claude_client
from app.services.claude_client import CHAT_MODEL
from app.utils.json_helpers import strip_json_fences

_JUDGE_TEMPERATURE = 0

_SUPPORT_SYSTEM = (
    "You are a strict evaluation judge. For each CLAIM, decide whether the cited "
    "EVIDENCE actually supports the claim's text. Judge only from the evidence "
    "given; if the evidence does not substantiate the claim, it is unsupported. "
    'Respond with JSON only: {"results": [true, false, ...]} with exactly one '
    "boolean per claim, in the same order."
)

_COVERAGE_SYSTEM = (
    "You are a strict evaluation judge. For each FACT, decide whether ANY of the "
    "CLAIMS asserts that fact (paraphrase counts; the claim must convey the same "
    'substance). Respond with JSON only: {"results": [true, false, ...]} with '
    "exactly one boolean per fact, in the same order."
)


def _call(system: str, payload: dict) -> list:
    response = claude_client.get_client().messages.create(
        model=CHAT_MODEL,
        max_tokens=1024,
        temperature=_JUDGE_TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    parsed = json.loads(strip_json_fences(response.content[0].text))
    return [bool(x) for x in parsed["results"]]


def judge_support(claims: list[dict], evidence_by_id: dict) -> list[bool]:
    if not claims:
        return []
    items = []
    for c in claims:
        cited = [
            {"field": evidence_by_id[s].field_name, "value": evidence_by_id[s].field_value}
            for s in c.get("sources", []) if s in evidence_by_id
        ]
        items.append({"claim": c.get("text", ""), "evidence": cited})
    return _call(_SUPPORT_SYSTEM, {"claims": items})


def judge_coverage(facts: list[str], claims: list[dict]) -> list[bool]:
    if not facts:
        return []
    payload = {"facts": facts, "claims": [c.get("text", "") for c in claims]}
    return _call(_COVERAGE_SYSTEM, payload)
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_brief_judge.py -v`
Expected: PASS — 4 tests.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/evals/brief_judge.py backend/tests/test_brief_judge.py
git commit -m "feat: temp-0 LLM judge for brief faithfulness + coverage"
```

---

## Task 5: Eval runner + scorecard + results

**Files:**
- Create: `backend/tests/evals/test_brief_quality.py`
- Create: `backend/tests/evals/README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Add the results dir to `.gitignore`**

Append to `.gitignore` (repo root):

```
# Eval run outputs (vary per run; sample lives in tests/evals/README.md)
backend/tests/evals/results/
```

- [ ] **Step 2: Write the eval runner**

`backend/tests/evals/test_brief_quality.py`:

```python
"""
Brief quality eval — runs synthesize_brief over golden fixtures and scores
faithfulness + completeness. Real Claude (synthesis + judge); run separately:

    docker-compose run --rm \
        -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test \
        -e ANTHROPIC_API_KEY=sk-ant-... \
        backend pytest tests/evals/test_brief_quality.py -v -m eval

Hybrid gate: deterministic checks are hard asserts; judge scores are measured
and asserted only against the per-fixture loose floors.
"""
import json
import os

import pytest

from app.services.synthesis_service import _assemble_evidence, synthesize_brief
from tests.evals.brief_judge import judge_coverage, judge_support
from tests.evals.brief_scorers import citation_integrity, completeness, faithfulness
from tests.evals.brief_seeder import seed_fixture
from tests.evals.golden_briefs import GOLDEN_CASES

_RESULTS: list[dict] = []


@pytest.mark.eval
@pytest.mark.parametrize("fixture", GOLDEN_CASES, ids=[f["id"] for f in GOLDEN_CASES])
def test_brief_quality(fixture, db):
    ws_id = seed_fixture(fixture, db)
    brief = synthesize_brief(ws_id, db)

    evidence, documents, required = _assemble_evidence(ws_id, db)
    evidence_by_id = {e.id: e for e in evidence}

    # HARD: grounding guarantee — a stored claim can never cite a fake id.
    assert citation_integrity(brief, evidence_by_id), \
        f"{fixture['id']}: brief cites a non-existent evidence id"

    # HARD: hallucination negative control.
    # NOTE: this asserts a clean fixture invents NO claims. If this proves
    # brittle (the model emits a benign, faithful restatement on clean input),
    # relax to: assert all(c.get("signal_type", "general") == "general"
    #                       for c in brief["claims"]) — i.e. no INVENTED saliences.
    if fixture.get("expected_clean"):
        assert len(brief["claims"]) == 0, \
            f"{fixture['id']}: clean fixture should invent no claims, got {len(brief['claims'])}"

    # MEASURED.
    faith, _ = faithfulness(brief, evidence_by_id, judge_support)
    eng, brf, detail = completeness(
        fixture.get("must_surface", []), evidence, documents, required,
        fixture.get("vertical", "general"), brief, judge_coverage,
    )

    # HARD: every planted salience must be detected by the engine (rule fired).
    for m, fired in zip(fixture.get("must_surface", []), detail["engine"]):
        assert fired, f"{fixture['id']}: engine did not detect salience '{m['salience_type']}'"

    print(f"\n── {fixture['id']} ──")
    print(f"  claims={len(brief['claims'])}  faithfulness={faith:.2f}  "
          f"completeness(brief)={brf:.2f}  completeness(engine)={eng:.2f}")
    _RESULTS.append({
        "id": fixture["id"], "claims": len(brief["claims"]),
        "faithfulness": round(faith, 3),
        "completeness_brief": round(brf, 3),
        "completeness_engine": round(eng, 3),
    })

    th = fixture.get("thresholds", {})
    assert faith >= th.get("faithfulness", 0.70), \
        f"{fixture['id']}: faithfulness {faith:.2f} below floor {th.get('faithfulness', 0.70)}"
    assert brf >= th.get("completeness", 0.60), \
        f"{fixture['id']}: completeness {brf:.2f} below floor {th.get('completeness', 0.60)}"


def teardown_module(module):
    """Write the accumulated scorecard to results/brief_eval.json (gitignored)."""
    if not _RESULTS:
        return
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "brief_eval.json"), "w") as f:
        json.dump(_RESULTS, f, indent=2)
```

- [ ] **Step 3: Write the README**

`backend/tests/evals/README.md`:

```markdown
# Brief Eval Harness

Measures `synthesize_brief` quality on **faithfulness** (claim precision) and
**completeness** (salience recall) over hand-authored golden fixtures.

## Run

```bash
docker-compose run --rm \
  -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  backend pytest tests/evals/test_brief_quality.py -v -m eval
```

Real Claude (synthesis + temp-0 judge); excluded from CI. Writes a scorecard to
`results/brief_eval.json` (gitignored).

## Hybrid gate
- **Hard asserts:** every claim cites a real evidence id; clean fixtures invent
  no claims; every planted salience is detected by the engine.
- **Measured (loose floors):** faithfulness ≥ 0.70, completeness ≥ 0.60.

## Sample scorecard
```
── outlier_dupe_contradiction ──
  claims=5  faithfulness=1.00  completeness(brief)=0.80  completeness(engine)=1.00
── chronology_missing_field ──
  claims=2  faithfulness=1.00  completeness(brief)=1.00  completeness(engine)=1.00
── multi_doc_clean ──
  claims=0  faithfulness=1.00  completeness(brief)=1.00  completeness(engine)=1.00
── single_doc_minimal ──
  claims=0  faithfulness=1.00  completeness(brief)=1.00  completeness(engine)=1.00
```
(Illustrative — actual judge scores vary per run.)

## Pure unit tests (CI)
The seeder, fixtures, scorers, and judge JSON-parsing have ordinary unit tests
under `backend/tests/test_brief_*.py` and `test_golden_briefs.py` that run in CI
(no Claude). Only this runner needs a live key.
```

- [ ] **Step 4: Verify the runner collects (cannot fully run without a live key)**

Run (collection only, no API call): `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/evals/test_brief_quality.py --collect-only -q`
Expected: collects 4 parametrized `test_brief_quality[...]` items (one per fixture id). No errors.

If a live `ANTHROPIC_API_KEY` is available, optionally run the full eval per the README command and confirm a scorecard prints and `results/brief_eval.json` is written.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/evals/test_brief_quality.py backend/tests/evals/README.md .gitignore
git commit -m "feat: brief quality eval runner + scorecard + README"
```

---

## Task 6: Full pure-suite + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the CI-collected suite (no Claude) to confirm no regressions**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ --ignore=tests/evals -q`
Expected: PASS — the prior 248 plus the new `test_brief_seeder`, `test_golden_briefs`, `test_brief_scorers`, `test_brief_judge` tests. No failures.

- [ ] **Step 2: Run ruff**

Run (host install, since ruff is not in the Docker image): `ruff check backend/app backend/tests` (or the host path `/c/Users/tjcol/AppData/Local/Programs/Python/Python314/Scripts/ruff.exe check backend/app backend/tests`)
Expected: no errors. Fix any reported in the new files, then re-run.

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit -m "chore: ruff clean for brief eval harness"
```
(Skip if ruff reported nothing.)

---

## Done criteria
- `seed_fixture` builds a real workspace `synthesize_brief` can read (DB unit test passes).
- 4 domain-neutral fixtures (2 negative controls), structurally validated in CI.
- `faithfulness`, `completeness` (two-layer), `citation_integrity` unit-tested with mocked judges in CI.
- `judge_support`/`judge_coverage` parse strict JSON at temperature 0; JSON-parse unit-tested with a mocked client in CI.
- `test_brief_quality.py` collects 4 parametrized eval cases; hard asserts on citation integrity, negative controls, engine detection; measured faithfulness/completeness under loose floors; writes `results/brief_eval.json`; README documents the run.
- CI-collected suite green; ruff clean.

## Notes for the implementer
- **Negative-control brittleness:** Task 5 Step 2 hard-asserts clean fixtures yield 0 claims. The synthesis layer's own call is not temperature 0, so a benign restatement is possible. The exact one-line relaxation (assert no claim carries a salience `signal_type`) is written in a code comment there — apply it only if the strict assert proves flaky against a live key; do not change the synthesis layer.
- **Don't touch `tests/evals/test_deed_extraction.py`** — the new runner is additive.

## Follow-ups (out of scope)
- Catalyst fraud-flavored fixtures (reuse this harness when the fraud cap is built).
- Plan 3 (citation-resolve endpoint, ClaudeCallLog/metering wiring, dropped-citation logging).
- Salience tuning driven by what this harness reveals.
