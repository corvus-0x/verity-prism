from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entity import Entity, Relationship
from app.schemas.entity import EntityCreate, EntityUpdate, RelationshipCreate
from app.services import audit


def create_entity(db: Session, workspace_id: str, user_id: str, payload: EntityCreate) -> Entity:
    """Create an entity and write an audit entry."""
    entity = Entity(**payload.model_dump(), workspace_id=workspace_id, created_by=user_id)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    audit.log(
        db,
        action="created",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="entity",
        entity_id=entity.id,
        after_state={"name": entity.name, "type": entity.type},
    )
    return entity


def list_entities(db: Session, workspace_id: str) -> list[Entity]:
    """List active (non-deleted) entities in a workspace."""
    return (
        db.query(Entity)
        .filter(
            Entity.workspace_id == workspace_id,
            Entity.is_deleted == False,  # noqa: E712
        )
        .all()
    )


def update_entity(
    db: Session, workspace_id: str, entity_id: str, user_id: str, payload: EntityUpdate
) -> Entity | None:
    """Apply a partial update to an entity; return None if not found."""
    entity = (
        db.query(Entity)
        .filter(
            Entity.id == entity_id,
            Entity.workspace_id == workspace_id,
            Entity.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not entity:
        return None
    before = {"name": entity.name, "status": entity.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    audit.log(
        db,
        action="updated",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="entity",
        entity_id=entity.id,
        before_state=before,
    )
    return entity


def delete_entity(db: Session, workspace_id: str, entity_id: str, user_id: str) -> bool:
    """Soft-delete an entity; return False if not found."""
    entity = (
        db.query(Entity)
        .filter(
            Entity.id == entity_id,
            Entity.workspace_id == workspace_id,
            Entity.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not entity:
        return False
    entity.is_deleted = True
    entity.deleted_at = datetime.now(UTC)
    db.commit()
    audit.log(
        db,
        action="deleted",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="entity",
        entity_id=entity.id,
    )
    return True


def create_relationship(
    db: Session, workspace_id: str, user_id: str, payload: RelationshipCreate
) -> Relationship:
    """Create a relationship between entities and write an audit entry."""
    rel = Relationship(**payload.model_dump(), workspace_id=workspace_id, created_by=user_id)
    db.add(rel)
    db.commit()
    db.refresh(rel)
    audit.log(
        db,
        action="created",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="relationship",
        entity_id=rel.id,
    )
    return rel


def list_relationships(db: Session, workspace_id: str) -> list[Relationship]:
    """List active (non-deleted) relationships in a workspace."""
    return (
        db.query(Relationship)
        .filter(
            Relationship.workspace_id == workspace_id,
            Relationship.is_deleted == False,  # noqa: E712
        )
        .all()
    )
