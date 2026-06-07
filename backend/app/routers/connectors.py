from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.connector_run import ConnectorRun
from app.models.user import User
from app.schemas.connector import (
    CandidateOut,
    ConnectorOut,
    FetchableItemOut,
    FetchRequest,
    ListItemsRequest,
    RunOut,
    SearchRequest,
)
from app.services import connector_registry, connector_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["connectors"])


@router.get("/connectors", response_model=list[ConnectorOut])
def list_connectors(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List connectors available to this workspace's vertical."""
    ws = get_workspace_or_404(workspace_id, user, db)
    connectors = connector_registry.get_connectors_for_vertical(ws.vertical)
    return [
        ConnectorOut(
            id=c.id,
            name=c.name,
            description=c.description,
            verticals=c.verticals,
            search_schema=c.search_schema,
        )
        for c in connectors
    ]


@router.post("/connectors/{connector_id}/search", response_model=list[CandidateOut])
def search_connector(
    workspace_id: str,
    connector_id: str,
    body: SearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Phase 1 — run a connector search and return candidate matches."""
    ws = get_workspace_or_404(workspace_id, user, db)
    connector = connector_registry.get_connector(connector_id)
    allowed_ids = {c.id for c in connector_registry.get_connectors_for_vertical(ws.vertical)}
    if connector is None or connector_id not in allowed_ids:
        raise HTTPException(status_code=404, detail="Connector not found")
    candidates = connector.search(body.params)
    return [
        CandidateOut(
            ref=c.ref,
            display_name=c.display_name,
            identifier=c.identifier,
            location=c.location,
        )
        for c in candidates
    ]


@router.post("/connectors/{connector_id}/list", response_model=list[FetchableItemOut])
def list_connector_items(
    workspace_id: str,
    connector_id: str,
    body: ListItemsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Phase 2 — list fetchable items for a chosen candidate."""
    ws = get_workspace_or_404(workspace_id, user, db)
    connector = connector_registry.get_connector(connector_id)
    allowed_ids = {c.id for c in connector_registry.get_connectors_for_vertical(ws.vertical)}
    if connector is None or connector_id not in allowed_ids:
        raise HTTPException(status_code=404, detail="Connector not found")
    items = connector.list_items(body.candidate_ref)
    return [
        FetchableItemOut(
            item_ref=i.item_ref,
            label=i.label,
            year=i.year,
            item_type=i.item_type,
            filed_date=i.filed_date,
        )
        for i in items
    ]


@router.post("/connectors/{connector_id}/fetch")
def fetch_connector_items(
    workspace_id: str,
    connector_id: str,
    body: FetchRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Phase 3 — create a ConnectorRun and kick off the fetch in the background."""
    ws = get_workspace_or_404(workspace_id, user, db)
    connector = connector_registry.get_connector(connector_id)
    allowed_ids = {c.id for c in connector_registry.get_connectors_for_vertical(ws.vertical)}
    if connector is None or connector_id not in allowed_ids:
        raise HTTPException(status_code=404, detail="Connector not found")
    run = ConnectorRun(
        id=str(uuid4()),
        workspace_id=workspace_id,
        connector_id=connector_id,
        search_query=body.search_query,
        candidate_label=body.candidate_label,
        params={"candidate_ref": body.candidate_ref, "item_refs": body.item_refs},
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    background.add_task(
        connector_service.run_fetch,
        run.id,
        connector_id,
        body.item_refs,
        workspace_id,
        user.id,
    )
    return {"run_id": run.id, "status": "running"}


@router.get("/connector-runs", response_model=list[RunOut])
def list_connector_runs(
    workspace_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List this workspace's connector runs, newest first."""
    get_workspace_or_404(workspace_id, user, db)
    return (
        db.query(ConnectorRun)
        .filter(
            ConnectorRun.workspace_id == workspace_id,
            ConnectorRun.is_deleted == False,  # noqa: E712
        )
        .order_by(ConnectorRun.started_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )


@router.get("/connector-runs/{run_id}", response_model=RunOut)
def get_connector_run(
    workspace_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Fetch a single connector run by id."""
    get_workspace_or_404(workspace_id, user, db)
    run = (
        db.query(ConnectorRun)
        .filter(
            ConnectorRun.id == run_id,
            ConnectorRun.workspace_id == workspace_id,
            ConnectorRun.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Connector run not found")
    return run
