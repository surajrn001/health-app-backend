from fastapi import status


def test_register_user_as_admin(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "newadmin@example.com",
            "password": "Password123",
            "role": "admin",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "newadmin@example.com"
    assert data["role"] == "admin"
    assert data["is_active"] is True
    assert "id" in data


def test_register_user_as_doctor_creates_doctor_profile(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "newdoc@example.com",
            "password": "Password123",
            "role": "doctor",
            "name": "Dr. Meredith Grey",
            "specialization": "General Surgery",
        },
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["email"] == "newdoc@example.com"
    assert data["role"] == "doctor"
    assert data["doctor_id"] is not None


def test_register_duplicate_email(client):
    payload = {
        "email": "duplicate@example.com",
        "password": "Password123",
        "role": "doctor",
    }
    res1 = client.post("/auth/register", json=payload)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = client.post("/auth/register", json=payload)
    assert res2.status_code == status.HTTP_400_BAD_REQUEST


def test_login_successful(client):
    client.post(
        "/auth/register",
        json={
            "email": "login_user@example.com",
            "password": "SecretPassword123",
            "role": "admin",
        },
    )
    response = client.post(
        "/auth/login",
        json={
            "email": "login_user@example.com",
            "password": "SecretPassword123",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "login_user@example.com"


def test_login_wrong_password(client):
    client.post(
        "/auth/register",
        json={
            "email": "wrong_pw@example.com",
            "password": "CorrectPassword",
            "role": "doctor",
        },
    )
    response = client.post(
        "/auth/login",
        json={
            "email": "wrong_pw@example.com",
            "password": "IncorrectPassword",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_login_non_existent_email(client):
    response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "SomePassword",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_me_authenticated(client, doctor1_fixture):
    headers = doctor1_fixture["headers"]
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "doctor1@example.com"
    assert data["role"] == "doctor"
    assert data["doctor_id"] == doctor1_fixture["doctor"].id


def test_unauthenticated_request_rejected(client):
    response = client.get("/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
