import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_create_entity(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/entities", json={
        "type": "organization",
        "name": "Acme Nonprofit Inc",
        "data": {"ein": "12-3456789", "sos_id": "1234567"}
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Acme Nonprofit Inc"
    assert data["data"]["ein"] == "12-3456789"

def test_list_entities_excludes_deleted(client, auth_headers, workspace_id):
    entity = client.post(f"/workspaces/{workspace_id}/entities",
                         json={"type": "person", "name": "Jane Smith"},
                         headers=auth_headers).json()
    client.delete(f"/workspaces/{workspace_id}/entities/{entity['id']}", headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/entities", headers=auth_headers)
    assert len(response.json()) == 0

def test_create_relationship(client, auth_headers, workspace_id):
    e1 = client.post(f"/workspaces/{workspace_id}/entities",
                     json={"type": "person", "name": "Jane Smith"}, headers=auth_headers).json()
    e2 = client.post(f"/workspaces/{workspace_id}/entities",
                     json={"type": "organization", "name": "Acme Corp"}, headers=auth_headers).json()
    response = client.post(f"/workspaces/{workspace_id}/relationships", json={
        "entity_a_id": e1["id"],
        "entity_b_id": e2["id"],
        "type": "officer_of",
        "description": "President, $0 salary"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["type"] == "officer_of"
