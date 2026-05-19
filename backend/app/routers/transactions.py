from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.auth import get_current_user
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}/transactions", tags=["transactions"])


@router.post("/", response_model=TransactionOut, status_code=201)
def create_transaction(workspace_id: str, payload: TransactionCreate,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    tx = Transaction(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="transaction", entity_id=tx.id,
              after_state={"type": tx.transaction_type, "amount": str(tx.amount_paid)})
    return tx


@router.get("/", response_model=list[TransactionOut])
def list_transactions(workspace_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Transaction).filter(Transaction.workspace_id == workspace_id).all()
