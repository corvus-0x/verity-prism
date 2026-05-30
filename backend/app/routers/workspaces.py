from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.post("/", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    workspace = Workspace(**payload.model_dump(), created_by=user.id)
    db.add(workspace)
    db.flush()
    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    db.refresh(workspace)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace.id,
              entity_type="workspace", entity_id=workspace.id,
              after_state={"name": workspace.name, "vertical": workspace.vertical})
    return workspace

@router.get("/", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    member_ids = [m.workspace_id for m in
                  db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()]
    return db.query(Workspace).filter(Workspace.id.in_(member_ids)).all()

@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_workspace_or_404(workspace_id, user, db)

@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    workspace = get_workspace_or_404(workspace_id, user, db)
    before = {"name": workspace.name, "status": workspace.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace.id,
              entity_type="workspace", entity_id=workspace.id,
              before_state=before, after_state={"name": workspace.name, "status": workspace.status})
    return workspace
