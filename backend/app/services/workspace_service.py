from sqlalchemy.orm import Session

from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate
from app.services import audit


def create_workspace(db: Session, user_id: str, payload: WorkspaceCreate) -> Workspace:
    """Create a workspace, add the creator as owner member, and audit it."""
    workspace = Workspace(**payload.model_dump(), created_by=user_id)
    db.add(workspace)
    db.flush()
    db.add(WorkspaceMember(workspace_id=workspace.id, user_id=user_id, role="owner"))
    db.flush()
    db.refresh(workspace)
    audit.log(
        db,
        action="created",
        user_id=user_id,
        workspace_id=workspace.id,
        entity_type="workspace",
        entity_id=workspace.id,
        after_state={"name": workspace.name, "vertical": workspace.vertical},
    )
    return workspace


def list_workspaces(db: Session, user_id: str) -> list[Workspace]:
    """List workspaces the user is a member of."""
    member_ids = [
        m.workspace_id
        for m in db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user_id).all()
    ]
    return db.query(Workspace).filter(Workspace.id.in_(member_ids)).all()


def apply_update(
    db: Session, workspace: Workspace, user_id: str, payload: WorkspaceUpdate
) -> Workspace:
    """Apply a partial update to an already-authorized workspace and audit it."""
    before = {"name": workspace.name, "status": workspace.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    db.flush()
    db.refresh(workspace)
    audit.log(
        db,
        action="updated",
        user_id=user_id,
        workspace_id=workspace.id,
        entity_type="workspace",
        entity_id=workspace.id,
        before_state=before,
        after_state={"name": workspace.name, "status": workspace.status},
    )
    return workspace
