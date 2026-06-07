import hashlib
import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
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
    Connector docs are tagged source_type='api_pull'; connector id + item_ref
    are recorded in the audit log (and on the ConnectorRun row via run_fetch)."""
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()
    existing = document_pipeline.find_existing_by_hash(workspace_id, sha256_hash, db)
    if existing is not None:
        return FetchItemResult(item_ref=item_ref, status="skipped",
                               document_id=existing.id, reason="already in workspace")

    doc = document_pipeline.create_pending_document(
        filename=filename, file_bytes=file_bytes, workspace_id=workspace_id,
        user_id=user_id, db=db, source_type="api_pull",
    )
    document_pipeline.process_upload_background(
        doc.id, file_bytes, filename, workspace_id, user_id,
    )
    try:
        audit.log(db, action="document_sourced", user_id=user_id, workspace_id=workspace_id,
                  entity_type="document", entity_id=doc.id,
                  after_state={"connector_id": connector_id, "item_ref": item_ref})
    except Exception as exc:  # noqa: BLE001 — audit failure must not break ingestion
        logger.warning("audit log failed for sourced doc %s: %s", doc.id, exc)
    return FetchItemResult(item_ref=item_ref, status="created", document_id=doc.id)


def run_fetch(run_id: str, connector_id: str, item_refs: list[str],
              workspace_id: str, user_id: str) -> None:
    """Background task: execute a connector fetch and finalize the ConnectorRun row.
    Opens its own session (request session is closed by the time this runs)."""
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
            if result.failed_count == 0:
                run.status = "complete"
            elif result.created_count == 0:
                run.status = "failed"
            else:
                run.status = "partial"  # some succeeded, some failed
        except Exception as exc:  # noqa: BLE001
            logger.exception("connector run %s failed", run_id)
            run.status = "failed"
            run.error_message = str(exc)
        finally:
            run.completed_at = datetime.now(UTC)
            db.commit()
    finally:
        db.close()
