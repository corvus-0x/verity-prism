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

def test_protected_route_without_token_returns_401(client):
    response = client.get("/workspaces/")
    assert response.status_code == 401


def test_login_sets_httponly_cookie(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    assert response.status_code == 200
    cookie = response.cookies.get("access_token")
    assert cookie is not None


def test_login_response_includes_user(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == registered_user["email"]


def test_logout_clears_cookie(client, registered_user):
    client.post("/auth/login", json=registered_user)
    response = client.post("/auth/logout")
    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token" in set_cookie


def test_me_returns_user_with_valid_cookie(client, registered_user):
    client.post("/auth/login", json=registered_user)
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == registered_user["email"]


def test_me_returns_401_without_auth(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
