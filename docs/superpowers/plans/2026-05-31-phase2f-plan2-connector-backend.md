# Phase 2F Plan 2 — Connector Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the two-phase connector framework (search → list → fetch), the IRS TEOS connector, document provenance + automatic dedup, and the connector API — a working backend testable via `/docs` before any UI exists.

**Architecture:** A `ConnectorBase` abstract class defines a three-method contract (`search`, `list_items`, `fetch`). A registry surfaces connectors by vertical (parallel to `agent_registry.py`). `fetch` hands bytes to the existing document pipeline with provenance tags — no second ingestion path. A `connector_service` orchestrates fetch (loop items, dedup by SHA-256, assemble per-item results). `ConnectorRun` rows persist pull history. Endpoints stay thin.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, pytest. Tests run in Docker against `catalyst_test`.

**Spec:** `docs/superpowers/specs/2026-05-31-phase2f-connectors-design.md` (Parts B, C; provenance in B4)

**Dependencies:** None. Independent of Plan 1 — can run in parallel.

**Key existing patterns to follow (verified against source):**
- `app/services/document_pipeline.py`:
  - `create_pending_document(filename, file_bytes, workspace_id, user_id, db) -> Document` — computes `sha256_hash` inline, stores file, sets `source_type="upload"`, `original_filename`, `file_path`, `uploaded_by`, returns the Document. **Note the arg order — `db` is LAST.**
  - `process_upload_background(doc_id, file_bytes, original_filename, workspace_id, user_id)` — background entry; opens its OWN `SessionLocal`. Takes the bytes + names, NOT a db session. The fetch path calls these two exactly as the upload router does.
- **The Document model already has `source_type` (String, default "upload")** and `sha256_hash`. We REUSE `source_type` for the connector id (set it to e.g. `"irs-teos"`) and only ADD a new `source_ref` column. Do not add a parallel `source` column.
- `app/services/agent_registry.py` — registry shape to mirror.
- `app/deps.py` — `get_workspace_or_404`. `app/services/auth.py` — `get_current_user`.
- `scripts/fetch_990_xml.py` — IRS TEOS fetch logic to wrap (HTTPRangeFile, index CSV scan, ZIP_SUFFIXES).
- Migration head is `a1b2c3d4e5f6` (per build inventory) — new migration's `down_revision` is the current head; verify with `alembic heads`.

---

## File Structure

**Create:**
- `backend/app/services/connectors/__init__.py` — package marker
- `backend/app/services/connectors/base.py` — `ConnectorBase`, `SearchCandidate`, `FetchableItem`, `FetchItemResult`, `FetchResult` dataclasses
- `backend/app/services/connectors/irs_teos.py` — IRS TEOS connector
- `backend/app/services/connector_registry.py` — registry
- `backend/app/services/connector_service.py` — fetch orchestration + dedup
- `backend/app/models/connector_run.py` — `ConnectorRun` model
- `backend/app/schemas/connector.py` — Pydantic request/response models
- `backend/app/routers/connectors.py` — endpoints
- `backend/alembic/versions/*_phase2f_connectors_provenance.py` — migration
- `backend/tests/test_connector_base.py`, `test_connector_registry.py`, `test_connector_service.py`, `test_connector_irs_teos.py`, `test_connectors_api.py`

**Modify:**
- `backend/app/services/document_pipeline.py` — `source`/`source_ref` params on `create_pending_document`; dedup helper
- `backend/app/models/document.py` — `source`, `source_ref` columns
- `backend/app/schemas/document.py` — expose `source`, `source_ref`
- `backend/app/main.py` — register connectors router

---

## Task 1: Migration — provenance columns + connector_runs table

**Files:**
- Create: `backend/app/models/connector_run.py`
- Modify: `backend/app/models/document.py`
- Create: `backend/alembic/versions/<rev>_phase2f_connectors_provenance.py`

- [ ] **Step 1: Add the source_ref column to the Document model**

The Document model ALREADY has `source_type = Column(..., default="upload")` — reuse it for
the connector id. Add only ONE new column. In `backend/app/models/document.py`, match the
column style already used for ids in that file:

```python
    source_ref = Column(String, nullable=True)  # ConnectorRun.id that produced this doc (null for uploads)
```

> Use whatever type the file uses for other id columns. If ids are plain `String`, use
> `String` as shown. Do NOT add a `source` column — `source_type` is the provenance field.

- [ ] **Step 2: Create the ConnectorRun model**

Create `backend/app/models/connector_run.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base  # match the Base import other models use


class ConnectorRun(Base):
    __tablename__ = "connector_runs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(UUID(as_uuid=False), nullable=False, index=True)
    connector_id = Column(String, nullable=False)        # machine key, e.g. "irs-teos"
    search_query = Column(String, nullable=True)         # human terms entered
    candidate_label = Column(String, nullable=True)      # resolved org label
    params = Column(JSONB, nullable=True)                # candidate_ref + item_refs
    status = Column(String, nullable=False, default="running")  # running|complete|failed
    result = Column(JSONB, nullable=True)               # per-item outcomes
    error_message = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
```

> Match `Base` import path and the UUID style to the existing models (check
> `backend/app/models/document.py` imports). If other models use `from app.models.base import Base`,
> use that instead.

- [ ] **Step 3: Generate the migration**

Run:
```bash
docker-compose run --rm backend alembic revision --autogenerate -m "phase2f connectors provenance"
```
Then open the generated file and verify it: (a) creates `connector_runs` with all columns + index on `workspace_id`, (b) adds `source_ref` to `documents` (the `source_type` column already exists — only `source_ref` is new). Confirm `down_revision` equals the current head.

- [ ] **Step 4: Apply and verify the migration on a fresh DB**

Run:
```bash
docker-compose run --rm backend alembic upgrade head
docker-compose run --rm backend alembic downgrade -1
docker-compose run --rm backend alembic upgrade head
```
Expected: upgrade, downgrade, upgrade all succeed with no errors (proves the migration is reversible).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/connector_run.py backend/app/models/document.py backend/alembic/versions/
git commit -m "feat: connector_runs table + document provenance columns

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: ConnectorBase contract + dataclasses

**Files:**
- Create: `backend/app/services/connectors/__init__.py`
- Create: `backend/app/services/connectors/base.py`
- Test: `backend/tests/test_connector_base.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_connector_base.py`:

```python
import pytest

from app.services.connectors.base import (
    ConnectorBase,
    SearchCandidate,
    FetchableItem,
    FetchItemResult,
    FetchResult,
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
        ConnectorBase()  # abstract — cannot instantiate directly
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_base.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement base**

Create `backend/app/services/connectors/__init__.py` (empty file).

Create `backend/app/services/connectors/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class SearchCandidate:
    """One match from a connector search — enough detail for the operator to pick."""
    ref: str            # opaque key the connector uses to list/fetch (e.g. an EIN)
    display_name: str   # full legal name
    identifier: str = ""  # EIN, parcel number, etc.
    location: str = ""    # city/state


@dataclass
class FetchableItem:
    """One pullable item under a chosen candidate."""
    item_ref: str       # opaque key for fetch
    label: str          # human label, e.g. "Form 990"
    year: int | None = None
    item_type: str = ""  # "990", "990-EZ", ...
    filed_date: str = ""


@dataclass
class FetchItemResult:
    """Outcome of fetching one item."""
    item_ref: str
    status: str               # "created" | "skipped" | "failed"
    document_id: str | None = None
    reason: str | None = None


@dataclass
class FetchResult:
    items: list[FetchItemResult] = field(default_factory=list)

    @property
    def created_count(self) -> int:
        return sum(1 for i in self.items if i.status == "created")

    @property
    def skipped_count(self) -> int:
        return sum(1 for i in self.items if i.status == "skipped")

    @property
    def failed_count(self) -> int:
        return sum(1 for i in self.items if i.status == "failed")


class ConnectorBase(ABC):
    """A self-describing data-source module. Three phases: search -> list -> fetch.

    Subclasses set class attributes (id, name, description, verticals, search_schema)
    and implement the three methods. fetch hands bytes to the document pipeline with
    provenance — it never parses or extracts.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    verticals: list[str] = ["general"]
    search_schema: dict = {}

    @abstractmethod
    def search(self, params: dict) -> list[SearchCandidate]:
        """Phase 1 — search the source by human-friendly terms (name)."""

    @abstractmethod
    def list_items(self, candidate_ref: str) -> list[FetchableItem]:
        """Phase 2 — list pullable items for a chosen candidate."""

    @abstractmethod
    def fetch(self, item_refs: list[str], workspace_id: str, user_id: str,
              db: Session) -> FetchResult:
        """Phase 3 — fetch selected items, hand each to the pipeline, return outcomes."""
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_base.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/connectors/__init__.py backend/app/services/connectors/base.py backend/tests/test_connector_base.py
git commit -m "feat: ConnectorBase contract + result dataclasses

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Connector registry

**Files:**
- Create: `backend/app/services/connector_registry.py`
- Test: `backend/tests/test_connector_registry.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_connector_registry.py`:

```python
from app.services import connector_registry
from app.services.connectors.base import (
    ConnectorBase, SearchCandidate, FetchableItem, FetchResult,
)


class _FakeGeneral(ConnectorBase):
    id = "fake-general"
    name = "Fake General"
    verticals = ["general"]
    def search(self, params): return []
    def list_items(self, candidate_ref): return []
    def fetch(self, item_refs, workspace_id, user_id, db): return FetchResult()


class _FakeFraud(ConnectorBase):
    id = "fake-fraud"
    name = "Fake Fraud"
    verticals = ["fraud"]
    def search(self, params): return []
    def list_items(self, candidate_ref): return []
    def fetch(self, item_refs, workspace_id, user_id, db): return FetchResult()


def test_general_connector_visible_to_all_verticals(monkeypatch):
    monkeypatch.setattr(connector_registry, "_REGISTRY",
                        {"fake-general": _FakeGeneral(), "fake-fraud": _FakeFraud()})
    fraud = {c.id for c in connector_registry.get_connectors_for_vertical("fraud")}
    general = {c.id for c in connector_registry.get_connectors_for_vertical("general")}
    assert "fake-general" in fraud and "fake-fraud" in fraud   # fraud sees both
    assert "fake-general" in general and "fake-fraud" not in general  # general sees only general


def test_get_connector_by_id(monkeypatch):
    monkeypatch.setattr(connector_registry, "_REGISTRY", {"fake-general": _FakeGeneral()})
    assert connector_registry.get_connector("fake-general").id == "fake-general"
    assert connector_registry.get_connector("nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_registry.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the registry**

Create `backend/app/services/connector_registry.py`:

```python
from app.services.connectors.base import ConnectorBase
from app.services.connectors.irs_teos import IrsTeosConnector

# Connectors live in code, registered by id. Add a line here to ship a connector.
_REGISTRY: dict[str, ConnectorBase] = {
    IrsTeosConnector.id: IrsTeosConnector(),
}


def get_connectors_for_vertical(vertical: str) -> list[ConnectorBase]:
    """Connectors available to a workspace: those serving this vertical or 'general'."""
    return [
        c for c in _REGISTRY.values()
        if vertical in c.verticals or "general" in c.verticals
    ]


def get_connector(connector_id: str) -> ConnectorBase | None:
    return _REGISTRY.get(connector_id)
```

> This imports `IrsTeosConnector` from Task 4. If implementing strictly in order, create
> `irs_teos.py` first (Task 4) or temporarily stub the import. The tests above use
> `monkeypatch` on `_REGISTRY`, so they pass regardless of what's registered by default.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_registry.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/connector_registry.py backend/tests/test_connector_registry.py
git commit -m "feat: connector registry with vertical filtering

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: IRS TEOS connector

**Files:**
- Create: `backend/app/services/connectors/irs_teos.py`
- Test: `backend/tests/test_connector_irs_teos.py`

Wrap `scripts/fetch_990_xml.py` logic. The script is EIN-keyed; add the name-search layer.

> **Design decision (spec Part C, the one flagged risk):** the IRS bulk index CSVs include
> the organization NAME and EIN per row. `search(name)` scans the yearly index CSVs and
> returns candidates whose name matches (case-insensitive substring). `list_items(ein)`
> returns the filing rows for that EIN. This reuses the exact data the script already
> downloads — no new external dependency. Cache index CSVs in memory per process to avoid
> re-downloading on every search.

- [ ] **Step 1: Write the failing test (network mocked)**

Create `backend/tests/test_connector_irs_teos.py`:

```python
from unittest.mock import patch

from app.services.connectors.irs_teos import IrsTeosConnector
from app.services.connectors.base import SearchCandidate, FetchableItem


# Two fake index rows: (ein, name, city_state, object_id, year, form_type, filed_date)
_FAKE_INDEX = [
    {"ein": "123456789", "name": "Bright Future Ministries Inc", "location": "Marysville, OH",
     "object_id": "2024050001", "year": 2023, "form_type": "990", "filed_date": "2024-05-12"},
    {"ein": "311789042", "name": "Bright Future Foundation", "location": "Columbus, OH",
     "object_id": "2023040002", "year": 2022, "form_type": "990", "filed_date": "2023-04-30"},
]


def test_search_matches_by_name():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        results = conn.search({"query": "Bright Future"})
    names = {c.display_name for c in results}
    assert "Bright Future Ministries Inc" in names
    assert "Bright Future Foundation" in names
    assert all(isinstance(c, SearchCandidate) for c in results)
    # EIN surfaced as identifier so the operator can confirm the right org
    assert any(c.identifier == "12-3456789" or c.identifier == "123456789" for c in results)


def test_search_is_case_insensitive_and_filters():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        results = conn.search({"query": "foundation"})
    assert len(results) == 1
    assert results[0].display_name == "Bright Future Foundation"


def test_list_items_returns_filings_for_ein():
    conn = IrsTeosConnector()
    with patch.object(conn, "_load_index", return_value=_FAKE_INDEX):
        items = conn.list_items("123456789")
    assert len(items) == 1
    assert isinstance(items[0], FetchableItem)
    assert items[0].year == 2023
    assert items[0].item_type == "990"
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_irs_teos.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement the connector**

Create `backend/app/services/connectors/irs_teos.py`:

```python
import logging

from sqlalchemy.orm import Session

from app.services.connectors.base import (
    ConnectorBase, SearchCandidate, FetchableItem, FetchItemResult, FetchResult,
)

logger = logging.getLogger(__name__)


def _format_ein(ein: str) -> str:
    digits = "".join(ch for ch in ein if ch.isdigit())
    return f"{digits[:2]}-{digits[2:]}" if len(digits) == 9 else ein


class IrsTeosConnector(ConnectorBase):
    id = "irs-teos"
    name = "IRS TEOS — 990 Filings"
    description = (
        "Fetch nonprofit 990 tax filings by organization name from IRS bulk data. "
        "XML parsed at full confidence — no OCR needed."
    )
    verticals = ["general"]
    search_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Organization name to search"},
        },
        "required": ["query"],
    }

    def _load_index(self) -> list[dict]:
        """Load IRS index rows: ein, name, location, object_id, year, form_type, filed_date.

        Wraps scripts/fetch_990_xml.py index-CSV download + parse. Cached per process.
        Patched in tests. Implement by importing/adapting the script's index logic.
        """
        # Implementation: download/parse the IRS index CSVs (see scripts/fetch_990_xml.py),
        # normalize to the dict shape above, cache in a module/instance attribute.
        raise NotImplementedError("wire to scripts/fetch_990_xml.py index logic")

    def search(self, params: dict) -> list[SearchCandidate]:
        query = (params.get("query") or "").strip().lower()
        if not query:
            return []
        seen = {}
        for row in self._load_index():
            if query in row["name"].lower():
                ein = row["ein"]
                if ein not in seen:  # one candidate per org
                    seen[ein] = SearchCandidate(
                        ref=ein,
                        display_name=row["name"],
                        identifier=_format_ein(ein),
                        location=row.get("location", ""),
                    )
        return list(seen.values())

    def list_items(self, candidate_ref: str) -> list[FetchableItem]:
        ein = "".join(ch for ch in candidate_ref if ch.isdigit())
        items = []
        for row in self._load_index():
            if row["ein"] == ein:
                items.append(FetchableItem(
                    item_ref=f"{ein}:{row['year']}:{row['object_id']}",
                    label=f"Form {row['form_type']}",
                    year=row["year"],
                    item_type=row["form_type"],
                    filed_date=row.get("filed_date", ""),
                ))
        return sorted(items, key=lambda i: i.year or 0, reverse=True)

    def fetch(self, item_refs: list[str], workspace_id: str, user_id: str,
              db: Session) -> FetchResult:
        """Download each selected XML and hand to the pipeline with provenance.

        Dedup + pipeline handoff are done by connector_service.ingest_bytes. Here we
        download bytes per item and delegate ingestion.
        """
        from app.services import connector_service
        result = FetchResult()
        for ref in item_refs:
            try:
                ein, year, object_id = ref.split(":")
                xml_bytes = self._download_xml(object_id)  # wraps script's XML fetch
                filename = f"{year}_{ein}_990.xml"
                outcome = connector_service.ingest_bytes(
                    db=db, workspace_id=workspace_id, user_id=user_id,
                    filename=filename, file_bytes=xml_bytes,
                    connector_id=self.id, item_ref=ref,
                )
                result.items.append(outcome)
            except Exception as exc:  # noqa: BLE001 — one item's failure must not kill the run
                logger.warning("IRS TEOS fetch failed for %s: %s", ref, exc)
                result.items.append(FetchItemResult(item_ref=ref, status="failed", reason=str(exc)))
        return result

    def _download_xml(self, object_id: str) -> bytes:
        """Download a single 990 XML by IRS object id. Wraps scripts/fetch_990_xml.py."""
        raise NotImplementedError("wire to scripts/fetch_990_xml.py XML download")
```

> **Two `NotImplementedError` stubs (`_load_index`, `_download_xml`) are deliberate seams,
> not placeholders.** The tested behavior (search/list logic) is fully implemented and
> green via mocking. Wiring the two stubs to `scripts/fetch_990_xml.py` is the last
> sub-step — do it in Step 5 with a live-network integration check, kept out of the unit
> suite so CI never hits the IRS.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_irs_teos.py -v
```
Expected: PASS (search + list_items tested with mocked `_load_index`)

- [ ] **Step 5: Wire the two network seams to the script**

Implement `_load_index` and `_download_xml` by importing/adapting the index-scan and XML-download logic from `scripts/fetch_990_xml.py` (HTTPRangeFile, ZIP_SUFFIXES, index_{year}.csv parsing). Cache the index in an instance attribute so repeated searches don't re-download. Verify manually (NOT in the unit suite) against a known EIN:

```bash
docker-compose run --rm backend python -c "from app.services.connectors.irs_teos import IrsTeosConnector as C; c=C(); print([x.display_name for x in c.search({'query':'red cross'})][:3])"
```
Expected: prints a few matching org names (confirms live index scan works).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/connectors/irs_teos.py backend/tests/test_connector_irs_teos.py
git commit -m "feat: IRS TEOS connector with search-by-name

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Connector service — ingest + dedup orchestration

**Files:**
- Create: `backend/app/services/connector_service.py`
- Modify: `backend/app/services/document_pipeline.py` (provenance params + dedup helper)
- Test: `backend/tests/test_connector_service.py`

- [ ] **Step 1: Add provenance params + dedup helper to the pipeline**

In `backend/app/services/document_pipeline.py` (verified signature:
`create_pending_document(filename, file_bytes, workspace_id, user_id, db)`, hash field is
`sha256_hash`, provenance field is `source_type`):

1. Extend `create_pending_document` with optional provenance kwargs at the END (keeps the
existing positional callers working):

```python
def create_pending_document(
    filename: str,
    file_bytes: bytes,
    workspace_id: str,
    user_id: str,
    db: Session,
    source_type: str = "upload",
    source_ref: str | None = None,
) -> Document:
```

In the `Document(...)` construction inside that function, change the existing
`source_type="upload",` line to use the param and add `source_ref`:

```python
        source_type=source_type,   # was hardcoded "upload"
        source_ref=source_ref,
```

2. Add a dedup lookup helper (note the real hash field is `sha256_hash`; confirm the
soft-delete column name — it is `is_deleted` per the Phase 4 audit work):

```python
def find_existing_by_hash(workspace_id: str, sha256_hash: str, db: Session) -> Document | None:
    """Return a non-deleted document in this workspace with a matching hash, or None.

    The SHA-256 hash is the evidence lock — identical bytes are the same evidence.
    Used by the connector flow to skip re-ingesting a document already in the workspace.
    """
    return (
        db.query(Document)
        .filter(
            Document.workspace_id == workspace_id,
            Document.sha256_hash == sha256_hash,
            Document.is_deleted == False,
        )
        .first()
    )
```

> If `Document` has no `is_deleted` column (check the model — it was added in migration
> `a3b8e1f92d44`), drop that filter line.

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_connector_service.py`:

```python
from unittest.mock import patch

from app.services import connector_service
from app.services.connectors.base import FetchItemResult


def test_ingest_bytes_creates_document_with_provenance(db_session, sample_workspace, sample_user):
    with patch("app.services.document_pipeline.process_upload_background"):
        outcome = connector_service.ingest_bytes(
            db=db_session, workspace_id=sample_workspace.id, user_id=sample_user.id,
            filename="2023_123456789_990.xml", file_bytes=b"<Return>x</Return>",
            connector_id="irs-teos", item_ref="123456789:2023:obj",
        )
    assert isinstance(outcome, FetchItemResult)
    assert outcome.status == "created"
    assert outcome.document_id is not None


def test_ingest_bytes_skips_duplicate_by_hash(db_session, sample_workspace, sample_user):
    payload = b"<Return>same</Return>"
    with patch("app.services.document_pipeline.process_upload_background"):
        first = connector_service.ingest_bytes(
            db=db_session, workspace_id=sample_workspace.id, user_id=sample_user.id,
            filename="a.xml", file_bytes=payload, connector_id="irs-teos", item_ref="r1",
        )
        second = connector_service.ingest_bytes(
            db=db_session, workspace_id=sample_workspace.id, user_id=sample_user.id,
            filename="b.xml", file_bytes=payload, connector_id="irs-teos", item_ref="r2",
        )
    assert first.status == "created"
    assert second.status == "skipped"
    assert "already in workspace" in (second.reason or "")
    assert second.document_id == first.document_id  # points at the existing doc
```

> `db_session`, `sample_workspace`, `sample_user` are conftest fixtures — match their real
> names (check `backend/tests/conftest.py`). If a fixture doesn't exist, create the row
> inline at the top of each test. `create_pending_document` requires a real `user_id` and
> writes a file to disk under `UPLOAD_DIR/workspace_id` — the test DB + tmp upload dir
> handle this; `process_upload_background` is patched so no pipeline runs.

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_service.py -v
```
Expected: FAIL — `connector_service` does not exist.

- [ ] **Step 4: Implement the connector service**

Create `backend/app/services/connector_service.py`. Note the real pipeline contract:
hashing is inline `hashlib.sha256(...).hexdigest()` (no `compute_file_hash` helper);
`create_pending_document(filename, file_bytes, workspace_id, user_id, db, source_type=, source_ref=)`;
`process_upload_background(doc_id, file_bytes, original_filename, workspace_id, user_id)` takes
the bytes and opens its own session; `audit.log(db, action=, user_id=, workspace_id=, entity_type=, entity_id=, after_state=)`.

```python
import hashlib
import logging
from datetime import UTC, datetime

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models.connector_run import ConnectorRun
from app.services import audit, document_pipeline
from app.services.connector_registry import get_connector
from app.services.connectors.base import FetchItemResult

logger = logging.getLogger(__name__)


def ingest_bytes(
    db: Session, workspace_id: str, user_id: str, filename: str, file_bytes: bytes,
    connector_id: str, item_ref: str,
) -> FetchItemResult:
    """Hand fetched bytes to the pipeline with provenance, deduping by SHA-256.

    Dedup: if the workspace already holds a document with the same hash, skip —
    no duplicate evidence row. Otherwise create the pending doc (tagged with the
    connector id as source_type) and kick off the same background pipeline an upload uses.
    """
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = document_pipeline.find_existing_by_hash(workspace_id, sha256_hash, db)
    if existing is not None:
        return FetchItemResult(item_ref=item_ref, status="skipped",
                               document_id=existing.id, reason="already in workspace")

    doc = document_pipeline.create_pending_document(
        filename=filename, file_bytes=file_bytes, workspace_id=workspace_id,
        user_id=user_id, db=db, source_type=connector_id,
    )
    # Same background entry point as the upload router. Runs after this returns; opens
    # its own SessionLocal. Pass the bytes + names it expects.
    document_pipeline.process_upload_background(
        doc.id, file_bytes, filename, workspace_id, user_id,
    )
    audit.log(db, action="document_sourced", user_id=user_id, workspace_id=workspace_id,
              entity_type="document", entity_id=doc.id,
              after_state={"source_type": connector_id, "item_ref": item_ref})
    return FetchItemResult(item_ref=item_ref, status="created", document_id=doc.id)


def run_fetch(run_id: str, connector_id: str, item_refs: list[str],
              workspace_id: str, user_id: str) -> None:
    """Background task: execute a connector fetch and finalize the ConnectorRun row.

    Opens its OWN session — like process_upload_background — because the request
    session is closed by the time this runs (BackgroundTasks fire after the response).
    """
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        run = db.query(ConnectorRun).filter(ConnectorRun.id == run_id).first()
        connector = get_connector(connector_id)
        if run is None or connector is None:
            logger.error("run_fetch: missing run %s or connector %s", run_id, connector_id)
            return
        try:
            result = connector.fetch(item_refs, workspace_id, user_id, db)
            run.result = [
                {"item_ref": i.item_ref, "status": i.status,
                 "document_id": i.document_id, "reason": i.reason}
                for i in result.items
            ]
            run.status = "failed" if result.created_count == 0 and result.failed_count > 0 else "complete"
        except Exception as exc:  # noqa: BLE001
            logger.exception("connector run %s failed", run_id)
            run.status = "failed"
            run.error_message = str(exc)
        finally:
            run.completed_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()
```

> **Signature ripples from threading `user_id` (already reflected in Tasks 2, 4, 6):**
> `ConnectorBase.fetch(self, item_refs, workspace_id, user_id, db)`, `IrsTeosConnector.fetch`
> matches, the fetch endpoint passes `user.id` to `run_fetch`, and `run_fetch` opens its own
> `SessionLocal` (no `db` arg) since it runs after the request session closes.

- [ ] **Step 5: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connector_service.py -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/connector_service.py backend/app/services/document_pipeline.py backend/tests/test_connector_service.py
git commit -m "feat: connector service — provenance ingest + SHA-256 dedup

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Pydantic schemas + endpoints

**Files:**
- Create: `backend/app/schemas/connector.py`
- Create: `backend/app/routers/connectors.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/schemas/document.py` (expose source/source_ref)
- Test: `backend/tests/test_connectors_api.py`

- [ ] **Step 1: Create the Pydantic schemas**

Create `backend/app/schemas/connector.py`:

```python
from pydantic import BaseModel


class ConnectorOut(BaseModel):
    id: str
    name: str
    description: str
    verticals: list[str]
    search_schema: dict


class SearchRequest(BaseModel):
    params: dict


class CandidateOut(BaseModel):
    ref: str
    display_name: str
    identifier: str = ""
    location: str = ""


class ListItemsRequest(BaseModel):
    candidate_ref: str


class FetchableItemOut(BaseModel):
    item_ref: str
    label: str
    year: int | None = None
    item_type: str = ""
    filed_date: str = ""


class FetchRequest(BaseModel):
    candidate_ref: str
    candidate_label: str = ""
    search_query: str = ""
    item_refs: list[str]


class RunOut(BaseModel):
    id: str
    connector_id: str
    search_query: str | None = None
    candidate_label: str | None = None
    status: str
    result: list | None = None
    error_message: str | None = None

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Write the failing API test**

Create `backend/tests/test_connectors_api.py`:

```python
from unittest.mock import patch

from app.services.connectors.base import SearchCandidate, FetchableItem


def test_list_connectors_for_workspace(client, auth_headers, sample_workspace):
    r = client.get(f"/workspaces/{sample_workspace.id}/connectors", headers=auth_headers)
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert "irs-teos" in ids


def test_search_endpoint_returns_candidates(client, auth_headers, sample_workspace):
    fake = [SearchCandidate(ref="123456789", display_name="Bright Future Ministries Inc",
                            identifier="12-3456789", location="Marysville, OH")]
    with patch("app.services.connector_registry.get_connector") as gc:
        gc.return_value.search.return_value = fake
        r = client.post(
            f"/workspaces/{sample_workspace.id}/connectors/irs-teos/search",
            json={"params": {"query": "Bright Future"}}, headers=auth_headers,
        )
    assert r.status_code == 200
    assert r.json()[0]["display_name"] == "Bright Future Ministries Inc"


def test_fetch_creates_run_and_returns_running(client, auth_headers, sample_workspace):
    with patch("app.routers.connectors.BackgroundTasks.add_task"):
        r = client.post(
            f"/workspaces/{sample_workspace.id}/connectors/irs-teos/fetch",
            json={"candidate_ref": "123456789", "candidate_label": "Bright Future",
                  "search_query": "Bright Future", "item_refs": ["123456789:2023:obj"]},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert "run_id" in body
```

- [ ] **Step 3: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connectors_api.py -v
```
Expected: FAIL — router not registered (404s).

- [ ] **Step 4: Implement the router**

Create `backend/app/routers/connectors.py`:

```python
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.connector_run import ConnectorRun
from app.schemas.connector import (
    ConnectorOut, SearchRequest, CandidateOut, ListItemsRequest,
    FetchableItemOut, FetchRequest, RunOut,
)
from app.services import connector_registry, connector_service
from app.services.auth import get_current_user

router = APIRouter(tags=["connectors"])


@router.get("/workspaces/{workspace_id}/connectors", response_model=list[ConnectorOut])
def list_connectors(workspace_id: str, db: Session = Depends(get_db),
                    user=Depends(get_current_user)):
    ws = get_workspace_or_404(workspace_id, db)
    conns = connector_registry.get_connectors_for_vertical(ws.vertical)
    return [ConnectorOut(id=c.id, name=c.name, description=c.description,
                         verticals=c.verticals, search_schema=c.search_schema) for c in conns]


@router.post("/workspaces/{workspace_id}/connectors/{connector_id}/search",
             response_model=list[CandidateOut])
def search(workspace_id: str, connector_id: str, body: SearchRequest,
           db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_workspace_or_404(workspace_id, db)
    conn = connector_registry.get_connector(connector_id)
    if conn is None:
        raise HTTPException(404, "Unknown connector")
    return [CandidateOut(ref=c.ref, display_name=c.display_name,
                         identifier=c.identifier, location=c.location)
            for c in conn.search(body.params)]


@router.post("/workspaces/{workspace_id}/connectors/{connector_id}/list",
             response_model=list[FetchableItemOut])
def list_items(workspace_id: str, connector_id: str, body: ListItemsRequest,
               db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_workspace_or_404(workspace_id, db)
    conn = connector_registry.get_connector(connector_id)
    if conn is None:
        raise HTTPException(404, "Unknown connector")
    return [FetchableItemOut(item_ref=i.item_ref, label=i.label, year=i.year,
                             item_type=i.item_type, filed_date=i.filed_date)
            for i in conn.list_items(body.candidate_ref)]


@router.post("/workspaces/{workspace_id}/connectors/{connector_id}/fetch")
def fetch(workspace_id: str, connector_id: str, body: FetchRequest,
          background: BackgroundTasks, db: Session = Depends(get_db),
          user=Depends(get_current_user)):
    get_workspace_or_404(workspace_id, db)
    conn = connector_registry.get_connector(connector_id)
    if conn is None:
        raise HTTPException(404, "Unknown connector")
    run = ConnectorRun(
        id=str(uuid.uuid4()), workspace_id=workspace_id, connector_id=connector_id,
        search_query=body.search_query, candidate_label=body.candidate_label,
        params={"candidate_ref": body.candidate_ref, "item_refs": body.item_refs},
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(connector_service.run_fetch, run.id, connector_id,
                        body.item_refs, workspace_id, user.id)
    return {"run_id": run.id, "status": "running"}


@router.get("/workspaces/{workspace_id}/connector-runs", response_model=list[RunOut])
def list_runs(workspace_id: str, page: int = 1, limit: int = 20,
              db: Session = Depends(get_db), user=Depends(get_current_user)):
    get_workspace_or_404(workspace_id, db)
    return (db.query(ConnectorRun)
            .filter(ConnectorRun.workspace_id == workspace_id,
                    ConnectorRun.is_deleted == False)
            .order_by(ConnectorRun.started_at.desc())
            .offset((page - 1) * limit).limit(limit).all())


@router.get("/workspaces/{workspace_id}/connector-runs/{run_id}", response_model=RunOut)
def get_run(workspace_id: str, run_id: str, db: Session = Depends(get_db),
            user=Depends(get_current_user)):
    get_workspace_or_404(workspace_id, db)
    run = (db.query(ConnectorRun)
           .filter(ConnectorRun.id == run_id,
                   ConnectorRun.workspace_id == workspace_id).first())
    if run is None:
        raise HTTPException(404, "Run not found")
    return run
```

> Match `get_db`, `get_workspace_or_404`, and `get_current_user` import paths to the real
> codebase (check another router like `app/routers/review.py` for the exact imports and
> dependency style).

- [ ] **Step 5: Register the router**

In `backend/app/main.py`, import and include the connectors router alongside the others:

```python
from app.routers import connectors
app.include_router(connectors.router)
```

- [ ] **Step 6: Expose provenance on document responses**

In `backend/app/schemas/document.py`, add to the document-out schema (the model field is
`source_type`, which already exists and defaults to "upload" — expose it plus the new ref):

```python
    source_type: str = "upload"
    source_ref: str | None = None
```

> If `source_type` is already in the document-out schema, only add `source_ref`.

- [ ] **Step 7: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_connectors_api.py -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/connector.py backend/app/routers/connectors.py backend/app/main.py backend/app/schemas/document.py backend/tests/test_connectors_api.py
git commit -m "feat: connector API endpoints (search/list/fetch/runs)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Full suite + manual smoke + inventory

- [ ] **Step 1: Run the entire backend suite**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```
Expected: All green.

- [ ] **Step 2: Manual smoke via API docs**

```bash
docker-compose up -d
```
Open `http://localhost:8000/docs`. Confirm the connector endpoints appear. With a workspace id and auth, call `GET /workspaces/{id}/connectors` and confirm IRS TEOS is listed.

- [ ] **Step 3: Update build inventory**

In `docs/build-inventory.md`: add entries for `connectors/` (now built — base, registry, irs_teos), `connector_service.py`, `connector_run.py` model, `connectors.py` router (move from 🔲 to ✅), the new migration in the Alembic list, and an Update Log row. Note document provenance columns (`source`, `source_ref`).

- [ ] **Step 4: Commit**

```bash
git add docs/build-inventory.md
git commit -m "docs: build inventory — connector backend foundation

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** B1 base (T2), B2 registry (T3), B3 ConnectorRun + migration (T1), B4 provenance + dedup (T1, T5), B5 endpoints (T6), Part C IRS TEOS (T4). All covered.
- **Type consistency:** `FetchItemResult` / `FetchResult` defined in T2, used in T4/T5. `ingest_bytes` signature defined in T5, called from T4's `fetch`. `RunOut`/`ConnectorRun` fields align between T1 model, T6 schema.
- **The flagged risk (IRS name search):** resolved in T4 — index CSVs carry name+EIN, so `search` scans them; the two network seams (`_load_index`, `_download_xml`) are isolated, mocked in unit tests, wired + manually verified in T4 Step 5 so CI never hits the IRS.
- **Adjustment points flagged inline (not placeholders):** conftest fixture names (`db_session`, `sample_workspace`), `audit.log` arg names, and dependency import paths — each call-out names exactly what to check against the real code.
- **Order note:** T3's registry imports `IrsTeosConnector` (T4). Build T4 before wiring T3's default `_REGISTRY`, or stub the import temporarily — flagged in T3 Step 3.
