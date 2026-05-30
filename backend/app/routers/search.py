from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.deps import get_workspace_or_404
from app.services import audit
from app.services.auth import get_current_user
from app.services.search_service import get_known_field_names, run_search, translate_query

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str


@router.post("/")
def search(
    workspace_id: str,
    payload: SearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Plain-English search across all extracted document fields in a workspace.
    Claude translates the query into FTS + field filters, then runs against
    document_extractions. Returns matching documents with their extracted fields.
    """
    get_workspace_or_404(workspace_id, user, db)

    field_names = get_known_field_names(workspace_id, db)
    query_plan = translate_query(payload.query, field_names)
    results = run_search(workspace_id, query_plan, db)

    audit.log(
        db,
        action="searched",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="search",
        after_state={"query": payload.query, "result_count": len(results)},
    )

    return {
        "query": payload.query,
        "query_plan": query_plan,
        "result_count": len(results),
        "results": results,
    }
