"""
Reprocess documents stuck in needs_review or misclassified.
Clears old extractions and re-runs the full pipeline on each document.

Run inside Docker: docker-compose exec backend python -m app.seeds.reprocess_documents

Safe to run multiple times — skips documents whose file is missing from disk.
"""

import logging
from pathlib import Path

from app.database import SessionLocal
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.services.document_pipeline import process_upload_background

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def reprocess_documents():
    db = SessionLocal()
    try:
        docs = (
            db.query(Document)
            .filter(
                Document.extraction_status == "needs_review",
                Document.is_deleted == False,
            )
            .all()
        )

        print(f"Found {len(docs)} documents to reprocess.")

        for doc in docs:
            file_path = Path(doc.file_path) if doc.file_path else None

            if not file_path or not file_path.exists():
                print(f"  SKIP {doc.filename} — file not on disk")
                continue

            print(f"  Reprocessing: {doc.filename}")

            # Clear old extractions so the pipeline starts clean
            db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc.id).delete()

            # Reset status to pending
            doc.extraction_status = "pending"
            doc.detected_doc_type = None
            doc.extraction_error = None
            db.commit()

            # Re-run the full pipeline synchronously
            file_bytes = file_path.read_bytes()
            process_upload_background(
                doc_id=doc.id,
                file_bytes=file_bytes,
                original_filename=doc.original_filename or doc.filename,
                workspace_id=doc.workspace_id,
                user_id=doc.uploaded_by,
            )

            # Refresh to get updated status
            db.refresh(doc)
            print(f"    → {doc.extraction_status} | {doc.detected_doc_type}")

        print("\nDone.")

    finally:
        db.close()


if __name__ == "__main__":
    reprocess_documents()
