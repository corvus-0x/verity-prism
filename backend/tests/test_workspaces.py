def test_create_workspace(client, auth_headers):
    response = client.post("/workspaces/", json={
        "name": "Acme Foundation Investigation",
        "subject_name": "Acme Foundation",
        "jurisdiction": "Test County, OH",
        "vertical": "fraud"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Foundation Investigation"
    assert data["status"] == "active"
    assert data["vertical"] == "fraud"

def test_list_workspaces_only_shows_own(client, auth_headers):
    client.post("/workspaces/", json={"name": "My Workspace"}, headers=auth_headers)
    response = client.get("/workspaces/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_workspace_by_id(client, auth_headers):
    created = client.post("/workspaces/", json={"name": "Test"}, headers=auth_headers).json()
    response = client.get(f"/workspaces/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]

def test_update_workspace_name(client, auth_headers):
    created = client.post("/workspaces/", json={"name": "Old Name"}, headers=auth_headers).json()
    response = client.patch(f"/workspaces/{created['id']}", json={"name": "New Name"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

def test_cannot_access_workspace_without_token(client):
    response = client.get("/workspaces/")
    assert response.status_code == 401


def test_create_workspace_accepts_render_mode(client, auth_headers):
    r = client.post("/workspaces/", json={
        "name": "Render Mode WS", "vertical": "general",
        "document_render_mode": "faithful",
    }, headers=auth_headers)
    assert r.status_code in (200, 201)
    assert r.json()["document_render_mode"] == "faithful"


def test_create_workspace_defaults_render_mode_schema(client, auth_headers):
    r = client.post("/workspaces/", json={"name": "Default WS", "vertical": "general"},
                    headers=auth_headers)
    assert r.status_code in (200, 201)
    assert r.json()["document_render_mode"] == "schema"
