from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claude_call_log import ClaudeCallLog


def get_workspace_usage(
    workspace_id: str, billing_period_start: datetime, db: Session
) -> dict:
    """Sum tokens and count documents processed for a workspace since a period start.

    Reads claude_call_logs only — no new table. Data layer for Phase 4A tier
    enforcement; answers "how much has this workspace used this period."
    documents_processed counts distinct document_ids with at least one logged call.
    Uses SQL aggregation to avoid loading all rows into Python memory.
    """
    base_filter = [
        ClaudeCallLog.workspace_id == workspace_id,
        ClaudeCallLog.called_at >= billing_period_start,
    ]

    totals = db.query(
        func.coalesce(func.sum(ClaudeCallLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(ClaudeCallLog.output_tokens), 0).label("output_tokens"),
    ).filter(*base_filter).one()

    doc_count = db.query(
        func.count(func.distinct(ClaudeCallLog.document_id))
    ).filter(
        *base_filter,
        ClaudeCallLog.document_id.isnot(None),
    ).scalar()

    input_tokens = int(totals.input_tokens)
    output_tokens = int(totals.output_tokens)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "documents_processed": doc_count or 0,
        "period_start": billing_period_start,
    }
