from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.ai import ConversationOut, MessageCreate, MessageOut
from app.services import ai_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["ai"])


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return ai_service.create_conversation(db, workspace_id, user.id)


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return ai_service.list_conversations(db, workspace_id)


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
    msg = ai_service.send_message(db, workspace_id, conversation_id, user.id, payload.content)
    if msg is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return msg


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
    return ai_service.list_messages(db, conversation_id)
