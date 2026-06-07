"""IRS Tax-Exempt Organization Search (TEOS) connector.

Wraps the IRS 990 bulk-XML index (see scripts/fetch_990_xml.py for the original
EIN-keyed downloader) and adds a search-by-NAME layer in front: the IRS index is
keyed by EIN, but investigators start from an organization name. We download the
yearly index CSVs once, cache the parsed rows, and let the user search by name,
pick an org, list its filings, and fetch the XML into the document pipeline.
"""

import csv
import io
import logging
import re
import urllib.error
import urllib.request

from sqlalchemy.orm import Session

from app.services.connectors.base import (
    ConnectorBase,
    FetchableItem,
    FetchItemResult,
    FetchResult,
    SearchCandidate,
)

logger = logging.getLogger(__name__)

# IRS bulk-data URLs (mirrors scripts/fetch_990_xml.py).
INDEX_URL = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/index_{year}.csv"
ZIP_URL = "https://apps.irs.gov/pub/epostcard/990/xml/{year}/{year}_TEOS_XML_{suffix}.zip"
DEFAULT_YEARS = list(range(2018, 2026))


class IrsTeosConnector(ConnectorBase):
    id = "irs-teos"
    name = "IRS TEOS — 990 Filings"
    description = (
        "Search IRS Tax-Exempt Organization 990 filings by organization name "
        "and pull the raw XML returns into the case."
    )
    verticals = ["general"]
    search_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "title": "Organization name",
                "description": "Full or partial tax-exempt organization name.",
            },
        },
        "required": ["query"],
    }

    def __init__(self):
        self._index_cache: list[dict] | None = None

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _format_ein(ein: str) -> str:
        """Format a 9-digit EIN as XX-XXXXXXX; pass anything else through unchanged."""
        digits = re.sub(r"\D", "", ein or "")
        if len(digits) == 9:
            return f"{digits[:2]}-{digits[2:]}"
        return ein

    # ------------------------------------------------------------- phase 1: search
    def search(self, params: dict) -> list[SearchCandidate]:
        """Phase 1 — case-insensitive substring match on org name; one candidate per unique EIN."""
        query = (params.get("query") or "").strip().lower()
        if not query:
            return []

        candidates: dict[str, SearchCandidate] = {}
        for row in self._load_index():
            name = row.get("name", "")
            if query not in name.lower():
                continue
            ein = row.get("ein", "")
            if ein in candidates:
                continue
            candidates[ein] = SearchCandidate(
                ref=ein,
                display_name=name,
                identifier=self._format_ein(ein),
                location=row.get("location", ""),
            )
        return list(candidates.values())

    # -------------------------------------------------------- phase 2: list items
    def list_items(self, candidate_ref: str) -> list[FetchableItem]:
        """Phase 2 — list 990 filings for the chosen EIN, newest year first."""
        ein = re.sub(r"\D", "", candidate_ref or "")
        items = [
            FetchableItem(
                item_ref=f"{ein}:{row.get('year')}:{row.get('object_id')}",
                label=f"Form {row.get('form_type', '990')}",
                year=row.get("year"),
                item_type=row.get("form_type", ""),
                filed_date=row.get("filed_date", ""),
            )
            for row in self._load_index()
            if row.get("ein") == ein
        ]
        items.sort(key=lambda i: i.year or 0, reverse=True)
        return items

    # --------------------------------------------------------- phase 3: fetch
    def fetch(self, item_refs: list[str], workspace_id: str, user_id: str,
              db: Session) -> FetchResult:
        """Phase 3 — download each filing's XML and hand the bytes to the pipeline."""
        # Deferred import: connector_service is built in the next task; importing it
        # at module load time would crash this module before that task lands.
        from app.services import connector_service

        result = FetchResult()
        for ref in item_refs:
            try:
                ein, year, object_id = ref.split(":")
                xml_bytes = self._download_xml(object_id, year)
                filename = f"{year}_{ein}_990.xml"
                item_result = connector_service.ingest_bytes(
                    db=db,
                    workspace_id=workspace_id,
                    user_id=user_id,
                    filename=filename,
                    file_bytes=xml_bytes,
                    connector_id=self.id,
                    item_ref=ref,
                )
                result.items.append(item_result)
            except Exception as exc:  # noqa: BLE001 — one bad ref must not abort the batch
                result.items.append(
                    FetchItemResult(item_ref=ref, status="failed", reason=str(exc))
                )
        return result

    # ------------------------------------------------------------- live IRS scan
    def _load_index(self) -> list[dict]:
        """Download + parse the yearly IRS index CSVs into normalized rows (cached).

        IRS index CSV columns: EIN, TAXPAYER_NAME (org name), RETURN_TYPE (form
        type), OBJECT_ID, TAX_PERIOD, SUB_DATE (filed date). There is no location
        column in the index, so `location` is left blank for live data.
        Network failures for a given year are logged and skipped (return [] overall
        rather than crash). Tests patch this method, so the live path is not exercised
        in the unit suite.
        """
        if self._index_cache is not None:
            return self._index_cache

        rows: list[dict] = []
        for year in DEFAULT_YEARS:
            url = INDEX_URL.format(year=year)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
            except (urllib.error.URLError, urllib.error.HTTPError, Exception) as exc:  # noqa: BLE001
                logger.warning("IRS index download failed for %s: %s", year, exc)
                continue

            text = data.decode("utf-8", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            for r in reader:
                ein = re.sub(r"\D", "", (r.get("EIN") or r.get("ein") or "").strip())
                if not ein:
                    continue
                rows.append({
                    "ein": ein,
                    "name": (r.get("TAXPAYER_NAME") or "").strip(),
                    "location": "",  # no location column in the IRS index CSV
                    "object_id": (r.get("OBJECT_ID") or "").strip(),
                    "year": year,
                    "form_type": (r.get("RETURN_TYPE") or r.get("FORM_TYPE") or "").strip(),
                    "filed_date": (r.get("SUB_DATE") or "").strip(),
                })

        self._index_cache = rows
        return rows

    def _download_xml(self, object_id: str, year: str) -> bytes:
        """Download a single filing's XML by OBJECT_ID from the IRS public mirror.
        Year is required to construct the correct per-year directory path."""
        url = (
            "https://apps.irs.gov/pub/epostcard/990/xml/"
            f"{year}/{object_id}_public.xml"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
