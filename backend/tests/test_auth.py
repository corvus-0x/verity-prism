def test_register_creates_user(client):
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123!",
        "full_name": "Test User"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data

def test_register_duplicate_email_returns_400(client):
    payload = {"email": "dup@example.com", "password": "TestPass123!", "full_name": "User"}
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400

def test_login_returns_jwt_token(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_wrong_password_returns_401(client, registered_user):
    response = client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_protected_route_without_token_returns_403(client):
    response = client.get("/workspaces/")
    assert response.status_code == 403
