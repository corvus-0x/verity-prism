from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.entity import Entity, Relationship
from app.models.user import User
from app.deps import get_workspace_or_404
from app.schemas.entity import (
    EntityCreate,
    EntityOut,
    EntityUpdate,
    RelationshipCreate,
    RelationshipOut,
)
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["entities"])

@router.post("/entities", response_model=EntityOut, status_code=201)
def create_entity(workspace_id: str, payload: EntityCreate,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    entity = Entity(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="entity", entity_id=entity.id,
              after_state={"name": entity.name, "type": entity.type})
    return entity

@router.get("/entities", response_model=list[EntityOut])
def list_entities(workspace_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Entity).filter(
        Entity.workspace_id == workspace_id, Entity.is_deleted == False
    ).all()

@router.patch("/entities/{entity_id}", response_model=EntityOut)
def update_entity(workspace_id: str, entity_id: str, payload: EntityUpdate,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    entity = db.query(Entity).filter(
        Entity.id == entity_id, Entity.workspace_id == workspace_id
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    before = {"name": entity.name, "status": entity.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace_id,
              entity_type="entity", entity_id=entity.id, before_state=before)
    return entity

@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(workspace_id: str, entity_id: str,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    entity = db.query(Entity).filter(
        Entity.id == entity_id, Entity.workspace_id == workspace_id
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity.is_deleted = True
    entity.deleted_at = datetime.now(UTC)
    db.commit()
    audit.log(db, action="deleted", user_id=user.id, workspace_id=workspace_id,
              entity_type="entity", entity_id=entity.id)

@router.post("/relationships", response_model=RelationshipOut, status_code=201)
def create_relationship(workspace_id: str, payload: RelationshipCreate,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    rel = Relationship(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(rel)
    db.commit()
    db.refresh(rel)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="relationship", entity_id=rel.id)
    return rel

@router.get("/relationships", response_model=list[RelationshipOut])
def list_relationships(workspace_id: str, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Relationship).filter(Relationship.workspace_id == workspace_id).all()
