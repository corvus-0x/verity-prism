def test_create_workspace(client, auth_headers):
    response = client.post("/workspaces/", json={
        "name": "Do Good In His Name Inc",
        "subject_name": "Karen Homan",
        "jurisdiction": "Darke County, OH",
        "vertical": "fraud"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Do Good In His Name Inc"
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
    assert response.status_code == 403
