import pytest


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]


def test_create_note(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/notes", json={
        "entity_type": "workspace",
        "entity_id": workspace_id,
        "content": "Address digit sequence reversed — 6172 vs 6712 Olding Rd. Same road as nonprofit."
    }, headers=auth_headers)
    assert response.status_code == 201
    assert "reversed" in response.json()["content"]


def test_list_notes_filtered_by_entity(client, auth_headers, workspace_id):
    client.post(f"/workspaces/{workspace_id}/notes",
                json={"entity_type": "workspace", "entity_id": workspace_id, "content": "Note 1"},
                headers=auth_headers)
    response = client.get(
        f"/workspaces/{workspace_id}/notes?entity_type=workspace&entity_id={workspace_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
