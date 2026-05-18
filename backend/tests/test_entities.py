import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_create_entity(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/entities", json={
        "type": "organization",
        "name": "Do Good In His Name Inc",
        "data": {"ein": "82-4458479", "sos_id": "4128601"}
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Do Good In His Name Inc"
    assert data["data"]["ein"] == "82-4458479"

def test_list_entities_excludes_deleted(client, auth_headers, workspace_id):
    entity = client.post(f"/workspaces/{workspace_id}/entities",
                         json={"type": "person", "name": "Karen Homan"},
                         headers=auth_headers).json()
    client.delete(f"/workspaces/{workspace_id}/entities/{entity['id']}", headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/entities", headers=auth_headers)
    assert len(response.json()) == 0

def test_create_relationship(client, auth_headers, workspace_id):
    e1 = client.post(f"/workspaces/{workspace_id}/entities",
                     json={"type": "person", "name": "Karen Homan"}, headers=auth_headers).json()
    e2 = client.post(f"/workspaces/{workspace_id}/entities",
                     json={"type": "organization", "name": "Do Good Inc"}, headers=auth_headers).json()
    response = client.post(f"/workspaces/{workspace_id}/relationships", json={
        "entity_a_id": e1["id"],
        "entity_b_id": e2["id"],
        "type": "officer_of",
        "description": "President/Treasurer, $0 salary"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["type"] == "officer_of"
