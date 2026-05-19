import pytest


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]


def test_create_transaction(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/transactions", json={
        "transaction_type": "purchase",
        "amount_paid": 300000,
        "appraised_value": 37490,
        "consideration": "above_market",
        "transaction_date": "2022-09-15",
        "instrument_number": "202300004871",
        "notes": "47 Patterson St — Seller: Winner Kyle J"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert float(data["amount_paid"]) == 300000.0
    assert data["consideration"] == "above_market"


def test_list_transactions(client, auth_headers, workspace_id):
    client.post(f"/workspaces/{workspace_id}/transactions",
                json={"transaction_type": "transfer", "amount_paid": 0,
                      "consideration": "zero"}, headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/transactions", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
