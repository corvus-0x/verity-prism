import pytest


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]


def test_create_lead(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/leads", json={
        "question": "Does Karen Homan have related businesses registered in Ohio?",
        "source": "Ohio Secretary of State"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_complete_lead_with_summary(client, auth_headers, workspace_id):
    lead = client.post(f"/workspaces/{workspace_id}/leads",
                       json={"question": "Test question"}, headers=auth_headers).json()
    response = client.patch(f"/workspaces/{workspace_id}/leads/{lead['id']}", json={
        "status": "complete",
        "result_summary": "Found Do Good Real Estate LLC (SOS #4371988)"
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert response.json()["result_summary"] is not None
