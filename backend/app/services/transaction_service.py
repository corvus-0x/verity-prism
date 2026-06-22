from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.services import audit


def create_transaction(
    db: Session, workspace_id: str, user_id: str, payload: TransactionCreate
) -> Transaction:
    """Create a transaction and write an audit entry."""
    tx = Transaction(**payload.model_dump(), workspace_id=workspace_id, created_by=user_id)
    db.add(tx)
    db.flush()
    db.refresh(tx)
    audit.log(
        db,
        action="created",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="transaction",
        entity_id=tx.id,
        after_state={"type": tx.transaction_type, "amount": str(tx.amount_paid)},
    )
    return tx


def list_transactions(db: Session, workspace_id: str) -> list[Transaction]:
    """List active (non-deleted) transactions in a workspace."""
    return (
        db.query(Transaction)
        .filter(
            Transaction.workspace_id == workspace_id,
            Transaction.is_deleted == False,  # noqa: E712
        )
        .all()
    )
