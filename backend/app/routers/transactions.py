from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services import transaction_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}/transactions", tags=["transactions"])


@router.post("/", response_model=TransactionOut, status_code=201)
def create_transaction(
    workspace_id: str,
    payload: TransactionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return transaction_service.create_transaction(db, workspace_id, user.id, payload)


@router.get("/", response_model=list[TransactionOut])
def list_transactions(
    workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)
    return transaction_service.list_transactions(db, workspace_id)
