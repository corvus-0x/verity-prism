import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_signal_types_are_preloaded(client, auth_headers):
    response = client.get("/signal-types", headers=auth_headers)
    assert response.status_code == 200
    codes = [s["code"] for s in response.json()]
    assert "SR-003" in codes
    assert "SR-025" in codes
    assert "SR-005" in codes

def test_create_finding(client, auth_headers, workspace_id):
    signal = client.get("/signal-types", headers=auth_headers).json()[0]
    response = client.post(f"/workspaces/{workspace_id}/findings", json={
        "title": "Property overpayment anomaly",
        "description": "Paid above-market price for significantly below-appraisal property.",
        "severity": "critical",
        "signal_type_id": signal["id"]
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "open"

def test_confirm_finding(client, auth_headers, workspace_id):
    signal = client.get("/signal-types", headers=auth_headers).json()[0]
    finding = client.post(f"/workspaces/{workspace_id}/findings",
                          json={"title": "Test", "severity": "high",
                                "signal_type_id": signal["id"]},
                          headers=auth_headers).json()
    response = client.patch(f"/workspaces/{workspace_id}/findings/{finding['id']}",
                            json={"status": "confirmed"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
