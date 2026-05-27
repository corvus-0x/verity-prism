from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ai import AIConversation, AIMessage
from app.models.user import User
from app.schemas.ai import MessageCreate, ConversationOut, MessageOut
from app.services.auth import get_current_user
from app.services.ai_engine import chat
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["ai"])


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    conv = AIConversation(workspace_id=workspace_id, user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return (
        db.query(AIConversation)
        .filter(AIConversation.workspace_id == workspace_id)
        .all()
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=MessageOut,
    status_code=201,
)
def send_message(
    workspace_id: str,
    conversation_id: str,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    conv = db.query(AIConversation).filter(
        AIConversation.id == conversation_id,
        AIConversation.workspace_id == workspace_id,
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Title auto-set from the first message (no DB query needed — just reads payload)
    if not conv.title:
        conv.title = payload.content[:60] + ("..." if len(payload.content) > 60 else "")
        db.commit()

    # Get Claude's response — history is loaded inside chat(), save messages after
    response_text = chat(workspace_id, conversation_id, payload.content, db)

    # Save both messages after chat() completes so history doesn't include current turn
    user_msg = AIMessage(
        conversation_id=conversation_id, role="user", content=payload.content
    )
    db.add(user_msg)
    assistant_msg = AIMessage(
        conversation_id=conversation_id, role="assistant", content=response_text
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    audit.log(
        db,
        action="queried",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="ai_conversation",
        entity_id=conversation_id,
    )
    return assistant_msg


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageOut],
)
def list_messages(
    workspace_id: str,
    conversation_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at)
        .all()
    )
