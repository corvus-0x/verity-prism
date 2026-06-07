from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class SearchCandidate:
    ref: str
    display_name: str
    identifier: str = ""
    location: str = ""


@dataclass
class FetchableItem:
    item_ref: str
    label: str
    year: int | None = None
    item_type: str = ""
    filed_date: str = ""


@dataclass
class FetchItemResult:
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
    """Self-describing data-source module. Three phases: search -> list -> fetch.
    fetch hands bytes to the document pipeline with provenance; it never parses/extracts."""

    id: str = ""
    name: str = ""
    description: str = ""
    verticals: list[str] = ["general"]
    search_schema: dict = {}

    @abstractmethod
    def search(self, params: dict) -> list[SearchCandidate]:
        """Phase 1 — search by human terms (name)."""

    @abstractmethod
    def list_items(self, candidate_ref: str) -> list[FetchableItem]:
        """Phase 2 — list pullable items for a chosen candidate."""

    @abstractmethod
    def fetch(self, item_refs: list[str], workspace_id: str, user_id: str,
              db: Session) -> FetchResult:
        """Phase 3 — fetch selected items, hand each to the pipeline, return outcomes."""
