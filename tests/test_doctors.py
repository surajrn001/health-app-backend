from fastapi import status


def test_admin_can_create_doctor(client, admin_headers):
    payload = {
        "name": "Dr. Gregory House",
        "specialization": "Diagnostic Medicine",
        "email": "dr.house@princeton.edu",
    }
    response = client.post("/doctors", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == payload["name"]
    assert data["specialization"] == payload["specialization"]
    assert data["email"] == payload["email"]
    assert data["is_active"] is True
    assert "id" in data


def test_doctor_cannot_create_doctor(client, doctor1_fixture):
    payload = {
        "name": "Dr. Unauthorized",
        "specialization": "Pediatrics",
        "email": "unauth_doc@example.com",
    }
    response = client.post("/doctors", json=payload, headers=doctor1_fixture["headers"])
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_create_doctor_duplicate_email(client, admin_headers):
    payload = {
        "name": "Dr. First",
        "specialization": "Cardiology",
        "email": "unique_doc@example.com",
    }
    res1 = client.post("/doctors", json=payload, headers=admin_headers)
    assert res1.status_code == status.HTTP_201_CREATED

    res2 = client.post("/doctors", json=payload, headers=admin_headers)
    assert res2.status_code == status.HTTP_400_BAD_REQUEST


def test_list_doctors_with_pagination_and_search(client, admin_headers):
    client.post(
        "/doctors",
        json={"name": "Dr. Alice Smith", "specialization": "Cardiology", "email": "alice@hospital.com"},
        headers=admin_headers,
    )
    client.post(
        "/doctors",
        json={"name": "Dr. Bob Jones", "specialization": "Neurology", "email": "bob@hospital.com"},
        headers=admin_headers,
    )

    res = client.get("/doctors", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["meta"]["total_items"] >= 2
    assert len(data["items"]) >= 2
    assert "total_records" in data
    assert "data" in data

    search_res = client.get("/doctors?search=Alice", headers=admin_headers)
    search_data = search_res.json()
    assert search_data["meta"]["total_items"] == 1
    assert search_data["items"][0]["name"] == "Dr. Alice Smith"


def test_doctor_filtering_specialization_and_active(client, admin_headers):
    client.post(
        "/doctors",
        json={"name": "Dr. Heart Expert", "specialization": "Cardiology", "email": "cardio@clinic.com"},
        headers=admin_headers,
    )
    client.post(
        "/doctors",
        json={"name": "Dr. Brain Expert", "specialization": "Neurology", "email": "neuro@clinic.com"},
        headers=admin_headers,
    )

    # Filter specialization
    res_spec = client.get("/doctors?specialization=cardiology", headers=admin_headers)
    assert res_spec.status_code == status.HTTP_200_OK
    data_spec = res_spec.json()
    for d in data_spec["data"]:
        assert "cardio" in d["specialization"].lower()

    # Filter is_active
    res_active = client.get("/doctors?is_active=true", headers=admin_headers)
    assert res_active.status_code == status.HTTP_200_OK
    data_active = res_active.json()
    for d in data_active["data"]:
        assert d["is_active"] is True


def test_get_doctor_details(client, doctor1_fixture):
    doc_id = doctor1_fixture["doctor"].id
    res = client.get(f"/doctors/{doc_id}", headers=doctor1_fixture["headers"])
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["id"] == doc_id
    assert data["name"] == doctor1_fixture["doctor"].name
    assert "patients" in data


def test_update_doctor_self(client, doctor1_fixture):
    doc_id = doctor1_fixture["doctor"].id
    update_payload = {"name": "Dr. Stephen Strange, MD, PhD"}
    res = client.put(f"/doctors/{doc_id}", json=update_payload, headers=doctor1_fixture["headers"])
    assert res.status_code == status.HTTP_200_OK
    assert res.json()["name"] == "Dr. Stephen Strange, MD, PhD"


def test_patch_doctor(client, admin_headers):
    create_res = client.post(
        "/doctors",
        json={"name": "Dr. Patch Test", "specialization": "Orthopedics", "email": "patch@test.com"},
        headers=admin_headers,
    )
    doc_id = create_res.json()["id"]

    patch_res = client.patch(
        f"/doctors/{doc_id}",
        json={"specialization": "Sports Medicine"},
        headers=admin_headers,
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["name"] == "Dr. Patch Test"
    assert patch_res.json()["specialization"] == "Sports Medicine"


def test_doctor_cannot_update_other_doctor(client, doctor1_fixture, doctor2_fixture):
    target_id = doctor2_fixture["doctor"].id
    res = client.put(
        f"/doctors/{target_id}",
        json={"name": "Hacked Name"},
        headers=doctor1_fixture["headers"],
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_soft_delete_doctor(client, admin_headers):
    create_res = client.post(
        "/doctors",
        json={"name": "Dr. To Delete", "specialization": "General", "email": "delete_me@doc.com"},
        headers=admin_headers,
    )
    doc_id = create_res.json()["id"]

    del_res = client.delete(f"/doctors/{doc_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["is_active"] is False

    del_res_again = client.delete(f"/doctors/{doc_id}", headers=admin_headers)
    assert del_res_again.status_code == status.HTTP_400_BAD_REQUEST


def test_get_doctor_patients_validation(client, admin_headers, doctor1_fixture):
    # Non-existent doctor returns 404
    res_404 = client.get("/doctors/99999/patients", headers=admin_headers)
    assert res_404.status_code == status.HTTP_404_NOT_FOUND

    # Inactive doctor returns 400
    doc_id = doctor1_fixture["doctor"].id
    client.delete(f"/doctors/{doc_id}", headers=admin_headers)
    res_inactive = client.get(f"/doctors/{doc_id}/patients", headers=admin_headers)
    assert res_inactive.status_code == status.HTTP_400_BAD_REQUEST


def test_api_v1_versioning(client, admin_headers):
    # Test /api/v1/doctors works identically
    res = client.get("/api/v1/doctors", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    assert "data" in res.json()
