from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.brief import Brief
from app.models.user import User
from app.services import synthesis_service
from app.services.auth import get_current_user

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


class CitationBatchRequest(BaseModel):
    extraction_ids: list[str]


@router.post("/brief")
def generate_brief(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    try:
        row = synthesis_service.generate_brief(workspace_id, user.id, db)
    except synthesis_service.SynthesisError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
    return _serialize(row)


@router.get("/brief")
def latest_brief(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    row = synthesis_service.get_latest_brief(workspace_id, db)
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
    rows = synthesis_service.list_briefs(workspace_id, db)
    return {"briefs": [_serialize(r) for r in rows], "count": len(rows)}


@router.get("/brief/citations/{extraction_id}")
def get_citation(
    workspace_id: str,
    extraction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    resolved = synthesis_service.resolve_citation(workspace_id, extraction_id, db)
    if not resolved:
        raise HTTPException(status_code=404, detail="Citation not found in this workspace")
    return resolved


@router.post("/brief/citations")
def resolve_citations(
    workspace_id: str,
    payload: CitationBatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    resolved = {}
    for eid in payload.extraction_ids:
        r = synthesis_service.resolve_citation(workspace_id, eid, db)
        if r:
            resolved[eid] = r
    return {"resolved": resolved, "count": len(resolved)}
