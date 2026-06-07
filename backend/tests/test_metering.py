from datetime import UTC, datetime

from app.models.claude_call_log import ClaudeCallLog
from app.services.metering import get_workspace_usage


def _log(db, workspace_id, input_tokens, output_tokens, when, document_id="doc-1"):
    row = ClaudeCallLog(
        call_type="extraction_batch",
        workspace_id=workspace_id,
        document_id=document_id,
        model="claude-haiku-4-5-20251001",
        attempt=1,
        latency_ms=100,
        prompt_chars=0,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        success=True,
    )
    row.called_at = when
    db.add(row)
    db.commit()
    return row


def test_usage_sums_tokens_within_period(db):
    ws = "ws-meter-1"
    period_start = datetime(2026, 5, 1, tzinfo=UTC)
    inside = datetime(2026, 5, 15, tzinfo=UTC)
    before = datetime(2026, 4, 20, tzinfo=UTC)

    _log(db, ws, 100, 50, inside, document_id="doc-a")
    _log(db, ws, 200, 80, inside, document_id="doc-b")
    _log(db, ws, 0, 0, inside, document_id="doc-a")   # duplicate doc — should not increase count
    _log(db, ws, 0, 0, inside, document_id=None)       # null doc — should not be counted
    _log(db, ws, 999, 999, before, document_id="doc-old")  # excluded — before period

    usage = get_workspace_usage(ws, period_start, db)

    assert usage["input_tokens"] == 300
    assert usage["output_tokens"] == 130
    assert usage["total_tokens"] == 430
    assert usage["documents_processed"] == 2   # doc-a + doc-b only; duplicate + null excluded
    assert usage["period_start"] == period_start


def test_usage_empty_for_workspace_with_no_calls(db):
    usage = get_workspace_usage("ws-none", datetime(2026, 5, 1, tzinfo=UTC), db)
    assert usage["input_tokens"] == 0
    assert usage["output_tokens"] == 0
    assert usage["total_tokens"] == 0
    assert usage["documents_processed"] == 0
