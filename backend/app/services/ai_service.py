from sqlalchemy.orm import Session

from app.models.ai import AIConversation, AIMessage
from app.services import audit
from app.services.ai_engine import chat


def create_conversation(db: Session, workspace_id: str, user_id: str) -> AIConversation:
    """Start a new AI conversation in a workspace."""
    conv = AIConversation(workspace_id=workspace_id, user_id=user_id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db: Session, workspace_id: str) -> list[AIConversation]:
    """List a workspace's AI conversations."""
    return (
        db.query(AIConversation)
        .filter(
            AIConversation.workspace_id == workspace_id,
        )
        .all()
    )


def get_conversation(db: Session, workspace_id: str, conversation_id: str) -> AIConversation | None:
    """Fetch a conversation scoped to a workspace; None if not found."""
    return (
        db.query(AIConversation)
        .filter(
            AIConversation.id == conversation_id,
            AIConversation.workspace_id == workspace_id,
        )
        .first()
    )


def list_messages(db: Session, workspace_id: str, conversation_id: str) -> list[AIMessage]:
    """List a conversation's messages in chronological order, scoped to the workspace.
    Joins AIConversation so a conversation_id belonging to another workspace returns
    nothing rather than leaking its messages (the router only verifies workspace access,
    not that the conversation lives in that workspace)."""
    return (
        db.query(AIMessage)
        .join(AIConversation, AIConversation.id == AIMessage.conversation_id)
        .filter(
            AIMessage.conversation_id == conversation_id,
            AIConversation.workspace_id == workspace_id,
        )
        .order_by(AIMessage.created_at)
        .all()
    )


def send_message(
    db: Session, workspace_id: str, conversation_id: str, user_id: str, content: str
) -> AIMessage | None:
    """Run one chat turn: title the conversation on first message, call Claude,
    persist the user + assistant messages after the response, and audit the query.
    Returns the assistant message, or None if the conversation isn't found.
    Messages are saved only after chat() returns so history excludes the current turn."""
    conv = get_conversation(db, workspace_id, conversation_id)
    if not conv:
        return None

    if not conv.title:
        conv.title = content[:60] + ("..." if len(content) > 60 else "")
        db.commit()

    response_text = chat(workspace_id, conversation_id, content, db)

    db.add(AIMessage(conversation_id=conversation_id, role="user", content=content))
    assistant_msg = AIMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=response_text,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    audit.log(
        db,
        action="queried",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="ai_conversation",
        entity_id=conversation_id,
    )
    return assistant_msg
