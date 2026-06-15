from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.brief import Brief
from app.models.user import User
from app.services import audit
from app.services.auth import get_current_user
from app.services.synthesis_service import store_brief, synthesize_brief

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["briefs"])


def _serialize(row: Brief) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "version": row.version,
        "summary": row.summary,
        "claims": row.claims,
        "model": row.model,
        "latency_ms": row.latency_ms,
        "input_tokens": row.input_tokens,
        "output_tokens": row.output_tokens,
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
    }


@router.post("/brief")
def generate_brief(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    brief = synthesize_brief(workspace_id, db)
    row = store_brief(workspace_id, brief, db)
    audit.log(
        db,
        action="brief_generated",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="brief",
        entity_id=row.id,
        after_state={
            "version": row.version,
            "claim_count": len(row.claims),
            "claims_dropped": brief.get("claims_dropped", 0),
        },
    )
    return _serialize(row)


@router.get("/brief")
def latest_brief(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    row = (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No brief generated yet")
    return _serialize(row)


@router.get("/briefs")
def brief_history(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    rows = (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .all()
    )
    return {"briefs": [_serialize(r) for r in rows], "count": len(rows)}
