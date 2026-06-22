from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.entity import (
    EntityCreate,
    EntityOut,
    EntityUpdate,
    RelationshipCreate,
    RelationshipOut,
)
from app.services import entity_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["entities"])


@router.post("/entities", response_model=EntityOut, status_code=201)
def create_entity(
    workspace_id: str,
    payload: EntityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return entity_service.create_entity(db, workspace_id, user.id, payload)


@router.get("/entities", response_model=list[EntityOut])
def list_entities(
    workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)
    return entity_service.list_entities(db, workspace_id)


@router.patch("/entities/{entity_id}", response_model=EntityOut)
def update_entity(
    workspace_id: str,
    entity_id: str,
    payload: EntityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    entity = entity_service.update_entity(db, workspace_id, entity_id, user.id, payload)
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity


@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(
    workspace_id: str,
    entity_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    if not entity_service.delete_entity(db, workspace_id, entity_id, user.id):
        raise HTTPException(status_code=404, detail="Entity not found")


@router.post("/relationships", response_model=RelationshipOut, status_code=201)
def create_relationship(
    workspace_id: str,
    payload: RelationshipCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    rel = entity_service.create_relationship(db, workspace_id, user.id, payload)
    if rel is None:
        raise HTTPException(status_code=404, detail="Related entity not found in this workspace")
    return rel


@router.get("/relationships", response_model=list[RelationshipOut])
def list_relationships(
    workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)
    return entity_service.list_relationships(db, workspace_id)
