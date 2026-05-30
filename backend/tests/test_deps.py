import uuid
import pytest
from fastapi import HTTPException

from app.deps import get_workspace_or_404
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"deps_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed",
        full_name="Deps Test User",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(id=str(uuid.uuid4()), name="Deps WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    return ws


def test_get_workspace_or_404_returns_workspace(db, user, workspace):
    result = get_workspace_or_404(workspace.id, user, db)
    assert result.id == workspace.id
    assert result.name == "Deps WS"


def test_get_workspace_or_404_raises_404_when_not_member(db, workspace):
    outsider = User(
        id=str(uuid.uuid4()),
        email="outsider@test.com",
        password_hash="hashed",
        full_name="Outsider",
    )
    db.add(outsider)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        get_workspace_or_404(workspace.id, outsider, db)
    assert exc.value.status_code == 404


def test_get_workspace_or_404_raises_404_for_nonexistent_workspace(db, user):
    with pytest.raises(HTTPException) as exc:
        get_workspace_or_404(str(uuid.uuid4()), user, db)
    assert exc.value.status_code == 404
