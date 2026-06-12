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
    # WALKTHROUGH: this is the access gate every workspace endpoint calls first.
    # The ORDER of the four checks is the whole lesson — each one assumes the
    # previous passed, and the 404-vs-403 choice is deliberate, not stylistic:
    #   404 = "I won't even confirm this exists to you."
    #   403 = "It exists and you can see it, but you can't do THIS."
    # We only ever escalate to 403 AFTER membership is proven. That's how the gate
    # avoids leaking information to people who shouldn't know the workspace exists.

    # CHECK 1 — membership, queried before the workspace itself is even loaded.
    membership = (
        db.query(WorkspaceMember)
        .filter(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
        .first()
    )
    # 404, NOT 403, on purpose. A 403 ("forbidden") would confirm the workspace
    # exists to a stranger probing IDs. 404 ("not found") reveals nothing — to a
    # non-member, a real-but-foreign workspace is indistinguishable from one that
    # was never created. Information hiding is the security control here.
    if not membership:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # CHECK 2 — role. Now that membership is proven, we CAN admit the resource
    # exists, so a role failure is an honest 403: you're in the workspace, but
    # this action needs a role you don't hold (e.g. admin-only operations).
    if required_roles and membership.role not in required_roles:
        raise HTTPException(status_code=403, detail="Insufficient workspace permissions")

    # CHECK 3 — load the workspace row. Reaching here means a membership row
    # exists; if the workspace itself is gone (soft-deleted, or a race), fall back
    # to 404 — there's genuinely nothing to return.
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # CHECK 4 — lifecycle gate, opt-in via require_active. A member may still be
    # blocked from acting on an archived/suspended workspace. 403 (not 404)
    # because we're telling a legitimate member WHY they're blocked — the status
    # is safe to reveal to someone already inside.
    if require_active and workspace.status != "active":
        raise HTTPException(status_code=403, detail=f"Workspace is {workspace.status}")

    return workspace
