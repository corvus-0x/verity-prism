from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


def get_workspace_or_404(
    workspace_id: str,
    user: User,
    db: Session,
    required_roles: list[str] | set[str] | None = None,
    require_active: bool = False,
) -> Workspace:
    """Verify user membership and return the workspace, or raise 404.
    Optionally enforce specific roles and active status.
    Called at the start of every workspace-scoped endpoint as an authz gate.
    """
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if required_roles and membership.role not in required_roles:
        raise HTTPException(status_code=403, detail="Insufficient workspace permissions")

    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    if require_active and workspace.status != "active":
        raise HTTPException(status_code=403, detail=f"Workspace is {workspace.status}")

    return workspace
