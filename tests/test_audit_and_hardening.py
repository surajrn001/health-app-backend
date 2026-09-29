from fastapi import status
from datetime import datetime, timezone


def test_response_time_header_present(client, admin_headers):
    """Level 14: Performance & Query Optimization - Response time headers measured."""
    response = client.get("/doctors", headers=admin_headers)
    assert response.status_code == status.HTTP_200_OK
    assert "x-process-time" in response.headers or "X-Process-Time" in response.headers
    assert "x-response-time" in response.headers or "X-Response-Time" in response.headers


def test_audit_fields_tracking(client, admin_headers, doctor1_fixture):
    """Level 15: Auditing & Tracking - created_by, updated_by, created_at, updated_at."""
    # 1. Create patient as admin
    create_res = client.post(
        "/patients",
        json={"name": "Audit Test Patient", "age": 27, "phone": "1230984567"},
        headers=admin_headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    data = create_res.json()
    assert data["created_by"] == "test_admin@example.com"
    assert data["updated_by"] == "test_admin@example.com"
    assert data["created_at"] is not None
    assert data["updated_at"] is not None

    pid = data["id"]

    # 2. Update patient as admin
    update_res = client.patch(
        f"/patients/{pid}",
        json={"name": "Audit Test Patient Renamed"},
        headers=admin_headers,
    )
    assert update_res.status_code == status.HTTP_200_OK
    up_data = update_res.json()
    assert up_data["name"] == "Audit Test Patient Renamed"
    assert up_data["updated_by"] == "test_admin@example.com"


def test_uniform_error_response_format(client, admin_headers):
    """Level 16: Global exception handling and standardized error response format."""
    # 404 error
    res_404 = client.get("/doctors/99999", headers=admin_headers)
    assert res_404.status_code == status.HTTP_404_NOT_FOUND
    json_404 = res_404.json()
    assert json_404["status"] == "error"
    assert json_404["code"] == 404
    assert "detail" in json_404
    assert "message" in json_404

    # 422 validation error
    res_422 = client.post(
        "/patients",
        json={"name": "Bad Age", "age": -5, "phone": "123"},
        headers=admin_headers,
    )
    assert res_422.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    json_422 = res_422.json()
    assert json_422["status"] == "error"
    assert json_422["code"] == 422
    assert "errors" in json_422
    assert len(json_422["errors"]) > 0


def test_database_integrity_unique_email_error(client, admin_headers):
    """Level 13: Handle database constraints and return clean error messages."""
    doc_data = {
        "name": "Dr. Unique One",
        "specialization": "Cardiology",
        "email": "unique.doctor@healthapp.com",
    }
    res1 = client.post("/doctors", json=doc_data, headers=admin_headers)
    assert res1.status_code == status.HTTP_201_CREATED

    # Duplicate doctor creation
    res2 = client.post("/doctors", json=doc_data, headers=admin_headers)
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in res2.json()["detail"].lower()


def test_auth_token_security_and_deactivated_user(client, db_session):
    """Test invalid token, expired token, and deactivated account handling."""
    from app.auth.jwt import create_access_token, hash_password
    from app.models.user import User, UserRole
    from datetime import timedelta

    # 1. Invalid token format
    res_inv = client.get("/doctors", headers={"Authorization": "Bearer invalid.jwt.token"})
    assert res_inv.status_code == status.HTTP_401_UNAUTHORIZED

    # 2. Expired token
    expired_token = create_access_token(
        {"sub": "expired@example.com", "user_id": 1, "role": "admin"},
        expires_delta=timedelta(seconds=-10),
    )
    res_exp = client.get("/doctors", headers={"Authorization": f"Bearer {expired_token}"})
    assert res_exp.status_code == status.HTTP_401_UNAUTHORIZED
    assert "expired" in res_exp.json()["detail"].lower()

    # 3. Deactivated user token
    deactivated = User(
        email="deactivated@healthapp.com",
        hashed_password=hash_password("Pass123"),
        role=UserRole.DOCTOR,
        is_active=False,
    )
    db_session.add(deactivated)
    db_session.commit()
    db_session.refresh(deactivated)

    deact_token = create_access_token({"sub": deactivated.email, "user_id": deactivated.id, "role": deactivated.role.value})
    res_deact = client.get("/doctors", headers={"Authorization": f"Bearer {deact_token}"})
    assert res_deact.status_code == status.HTTP_403_FORBIDDEN
    assert "deactivated" in res_deact.json()["detail"].lower()


def test_openapi_documentation_and_system_endpoints(client):
    """Level 18: Swagger documentation and schema endpoints validation."""
    # Root endpoint
    root_res = client.get("/")
    assert root_res.status_code == status.HTTP_200_OK
    assert root_res.json()["status"] == "online"

    # Health endpoint
    health_res = client.get("/health")
    assert health_res.status_code == status.HTTP_200_OK
    assert health_res.json()["status"] == "healthy"

    # Swagger UI
    docs_res = client.get("/docs")
    assert docs_res.status_code == status.HTTP_200_OK

    # ReDoc
    redoc_res = client.get("/redoc")
    assert redoc_res.status_code == status.HTTP_200_OK

    # OpenAPI JSON schema validation
    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == status.HTTP_200_OK
    schema = openapi_res.json()
    assert "paths" in schema
    assert "/api/v1/appointments" in schema["paths"]
    assert "/api/v1/doctors/{doctor_id}/appointments" in schema["paths"]
    assert "/api/v1/patients/{patient_id}/appointments" in schema["paths"]

