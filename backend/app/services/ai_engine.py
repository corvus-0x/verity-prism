"""
AI Chat Engine — Claude with full workspace context.

build_workspace_context() loads everything in the workspace into a text
block that becomes the system prompt. The richer the workspace data,
the more accurate and specific Claude's answers.
"""
import logging
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.workspace import Workspace
from app.models.entity import Entity
from app.models.transaction import Transaction
from app.models.finding import Finding
from app.models.lead import InvestigationLead
from app.models.document import Document
from app.models.ai import AIMessage

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)


def build_workspace_context(workspace_id: str, db: Session) -> str:
    """
    Build a structured text summary of the entire workspace — entities,
    transactions, findings, leads, and documents. This is what Claude reads
    before answering any question. Richer workspace data = better answers.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    entities = db.query(Entity).filter(
        Entity.workspace_id == workspace_id, Entity.is_deleted == False
    ).all()
    transactions = db.query(Transaction).filter(
        Transaction.workspace_id == workspace_id
    ).all()
    findings = db.query(Finding).filter(Finding.workspace_id == workspace_id).all()
    leads = db.query(InvestigationLead).filter(
        InvestigationLead.workspace_id == workspace_id
    ).all()
    docs = db.query(Document).filter(Document.workspace_id == workspace_id).all()

    lines = [
        f"WORKSPACE: {workspace.name}",
        f"Subject: {workspace.subject_name or 'Not specified'}",
        f"Jurisdiction: {workspace.jurisdiction or 'Not specified'}",
        f"Vertical: {workspace.vertical}",
        f"Status: {workspace.status}",
        "",
        f"ENTITIES ({len(entities)}):",
    ]

    for e in entities:
        lines.append(f"  [{e.type.upper()}] {e.name} — status: {e.status}")
        if e.data:
            for k, v in e.data.items():
                lines.append(f"    {k}: {v}")

    lines.append(f"\nTRANSACTIONS ({len(transactions)}):")
    for t in transactions:
        overpay = ""
        if t.amount_paid and t.appraised_value and float(t.appraised_value) > 0:
            pct = int(
                ((float(t.amount_paid) - float(t.appraised_value)) / float(t.appraised_value))
                * 100
            )
            overpay = f" ({'+' if pct > 0 else ''}{pct}% vs appraised)"
        lines.append(
            f"  {t.transaction_type} | paid: ${t.amount_paid} | "
            f"appraised: ${t.appraised_value}{overpay} | "
            f"date: {t.transaction_date} | instrument: {t.instrument_number}"
        )
        if t.notes:
            lines.append(f"    note: {t.notes}")

    lines.append(f"\nFINDINGS ({len(findings)}):")
    for f in findings:
        lines.append(f"  [{f.severity.upper()}] {f.title} — {f.status}")
        if f.description:
            lines.append(f"    {f.description}")

    open_leads = [lead for lead in leads if lead.status in ("pending", "in_progress")]
    lines.append(f"\nOPEN LEADS ({len(open_leads)}):")
    for lead in open_leads:
        lines.append(f"  • {lead.question} (source: {lead.source or 'not specified'})")

    lines.append(f"\nDOCUMENTS ({len(docs)}):")
    for doc in docs:
        lines.append(f"  {doc.filename} [{doc.detected_doc_type or 'unknown type'}]")

    return "\n".join(lines)


def get_conversation_history(
    conversation_id: str, db: Session, limit: int = 20
) -> list[dict]:
    """
    Return the last N messages in chronological order.
    Fetched newest-first then reversed so Claude sees the natural flow.
    """
    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


def chat(
    workspace_id: str,
    conversation_id: str,
    user_message: str,
    db: Session,
) -> str:
    """
    Send a message to Claude with full workspace context and conversation history.
    Returns Claude's response as a plain string.

    The system prompt injects the full workspace data so Claude answers
    accurately from evidence, not from speculation.
    """
    workspace_context = build_workspace_context(workspace_id, db)
    history = get_conversation_history(conversation_id, db)

    system_prompt = (
        "You are an investigation assistant helping analyze documents and case data. "
        "You have access to the complete workspace data below. Answer questions accurately "
        "based on this data only — do not speculate beyond what the data shows.\n\n"
        "Be precise with numbers, dates, names, and document references. "
        "When you identify something that has not been investigated yet, mention it at the "
        'end as "Next lead to consider: [question]".\n\n'
        f"WORKSPACE DATA:\n{workspace_context}"
    )

    messages = history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text
