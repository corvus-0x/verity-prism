import pytest


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post(
        "/workspaces/", json={"name": "Test", "vertical": "fraud"}, headers=auth_headers
    ).json()["id"]


def test_create_lead(client, auth_headers, workspace_id):
    response = client.post(
        f"/workspaces/{workspace_id}/leads",
        json={
            "question": "Does the subject entity have related businesses registered in the state?",
            "source": "Secretary of State",
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["status"] == "pending"


def test_update_deleted_lead_returns_404(client, auth_headers, workspace_id, db):
    from app.models.lead import InvestigationLead

    lead = client.post(
        f"/workspaces/{workspace_id}/leads",
        json={"question": "Test question"},
        headers=auth_headers,
    ).json()
    row = db.query(InvestigationLead).filter(InvestigationLead.id == lead["id"]).first()
    row.is_deleted = True
    db.commit()
    response = client.patch(
        f"/workspaces/{workspace_id}/leads/{lead['id']}",
        json={"status": "complete"},
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_complete_lead_with_summary(client, auth_headers, workspace_id):
    lead = client.post(
        f"/workspaces/{workspace_id}/leads",
        json={"question": "Test question"},
        headers=auth_headers,
    ).json()
    response = client.patch(
        f"/workspaces/{workspace_id}/leads/{lead['id']}",
        json={
            "status": "complete",
            "result_summary": "Found affiliated LLC registered with state (SOS #1234567)",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert response.json()["result_summary"] is not None
