import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.routers.workspaces import get_workspace_or_404
from app.schemas.audit_log import AuditLogPage
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["audit"])


@router.get("/audit-log", response_model=AuditLogPage)
def get_audit_log(
    workspace_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return paginated audit log entries for this workspace, newest first."""
    get_workspace_or_404(workspace_id, user, db)

    base = db.query(AuditLog).filter(AuditLog.workspace_id == workspace_id)
    total = base.count()
    entries = (
        base.order_by(AuditLog.timestamp.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return AuditLogPage(
        entries=entries,
        total=total,
        page=page,
        pages=max(1, math.ceil(total / limit)),
    )
