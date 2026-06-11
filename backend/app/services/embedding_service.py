"""
Embedding Service — generates and stores document-level vector embeddings.

Embeddings enable semantic similarity search alongside FTS in the hybrid
search layer. One embedding per document, generated after extraction
completes. Disabled gracefully when OPENAI_API_KEY is not configured.
"""

import logging

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

_openai_client = None


def _get_openai_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI

        _openai_client = OpenAI(api_key=settings.openai_api_key)
    return _openai_client


def is_available() -> bool:
    """Return True if embedding generation is configured (settings.openai_api_key)."""
    return bool(settings.openai_api_key)


def build_text_representation(document_id: str, db: Session) -> str:
    """
    Build an embeddable text string from a document's extracted fields.
    Format: "Type: DEED | grantor_name: Oak Ridge LLC | sale_amount: 1250000.00 | ..."
    """
    from app.models.document import Document
    from app.models.document_extraction import DocumentExtraction

    doc = db.query(Document).filter(Document.id == document_id).first()
    extractions = (
        db.query(DocumentExtraction).filter(DocumentExtraction.document_id == document_id).all()
    )

    parts = []
    if doc and doc.detected_doc_type:
        parts.append(f"Type: {doc.detected_doc_type}")
    for e in extractions:
        if e.field_value:
            parts.append(f"{e.field_name}: {e.field_value}")

    return " | ".join(parts)


def generate_embedding(text: str) -> list[float]:
    """Generate a 1536-dim vector using OpenAI text-embedding-3-small."""
    response = _get_openai_client().embeddings.create(
        input=text,
        model="text-embedding-3-small",
    )
    return response.data[0].embedding


def embed_document(document_id: str, workspace_id: str, db: Session) -> None:
    """
    Build text representation, generate embedding, store on documents.embedding.
    No-op if OPENAI_API_KEY is not configured. Never raises — embedding
    failure must not fail a document.
    """
    # WALKTHROUGH: this is OPTIONAL enrichment, and two design choices say so.
    # (1) Graceful degradation: no OpenAI key -> this returns immediately and the
    #     document simply has no embedding. Hybrid search notices the missing
    #     embedding and falls back to keyword-only FTS (see search_service). The
    #     feature degrades, the product doesn't break.
    # (2) Never-raise contract: the pipeline calls this in a non-fatal step, so a
    #     failure here must not fail an already-extracted document. The embedding
    #     is a nice-to-have layered on top of saved data — losing it costs some
    #     semantic recall, never the document itself.
    if not is_available():
        return

    from app.models.document import Document

    text = build_text_representation(document_id, db)
    if not text.strip():
        return

    embedding = generate_embedding(text)

    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc:
        doc.embedding = embedding
        db.commit()
        logger.info("Embedded document %s (%d chars)", document_id, len(text))
