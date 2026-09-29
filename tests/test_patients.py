from fastapi import status


def test_create_patient_valid(client, admin_headers):
    payload = {
        "name": "Jane Patient",
        "age": 28,
        "phone": "9876543210",
    }
    response = client.post("/patients", json=payload, headers=admin_headers)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["name"] == "Jane Patient"
    assert data["age"] == 28
    assert data["phone"] == "9876543210"
    assert "id" in data


def test_patient_age_validation(client, admin_headers):
    res_zero = client.post(
        "/patients",
        json={"name": "Baby", "age": 0, "phone": "9876543210"},
        headers=admin_headers,
    )
    assert res_zero.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    res_neg = client.post(
        "/patients",
        json={"name": "Time Traveler", "age": -5, "phone": "9876543210"},
        headers=admin_headers,
    )
    assert res_neg.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_patient_phone_validation(client, admin_headers):
    # Too short (< 10 digits)
    res_short = client.post(
        "/patients",
        json={"name": "Short Phone", "age": 30, "phone": "12345"},
        headers=admin_headers,
    )
    assert res_short.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Too long (> 10 digits)
    res_long = client.post(
        "/patients",
        json={"name": "Long Phone", "age": 30, "phone": "123456789012345"},
        headers=admin_headers,
    )
    assert res_long.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Alphabetic characters
    res_invalid = client.post(
        "/patients",
        json={"name": "Letters Phone", "age": 30, "phone": "abcdef1234"},
        headers=admin_headers,
    )
    assert res_invalid.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Symbols / plus sign (must be numeric only)
    res_plus = client.post(
        "/patients",
        json={"name": "Plus Phone", "age": 30, "phone": "+1234567890"},
        headers=admin_headers,
    )
    assert res_plus.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Exactly 10 numeric digits
    res_10 = client.post(
        "/patients",
        json={"name": "Valid 10", "age": 30, "phone": "9876543210"},
        headers=admin_headers,
    )
    assert res_10.status_code == status.HTTP_201_CREATED


def test_doctor_sees_only_assigned_patients(client, admin_headers, doctor1_fixture, doctor2_fixture):
    p1 = client.post(
        "/patients",
        json={"name": "Patient For Doc1", "age": 40, "phone": "1111111111"},
        headers=admin_headers,
    ).json()

    p2 = client.post(
        "/patients",
        json={"name": "Patient For Doc2", "age": 50, "phone": "2222222222"},
        headers=admin_headers,
    ).json()

    doc1_id = doctor1_fixture["doctor"].id
    doc2_id = doctor2_fixture["doctor"].id

    client.post(f"/doctors/{doc1_id}/patients/{p1['id']}", headers=admin_headers)
    client.post(f"/doctors/{doc2_id}/patients/{p2['id']}", headers=admin_headers)

    doc1_list = client.get("/patients", headers=doctor1_fixture["headers"]).json()
    assert doc1_list["meta"]["total_items"] == 1
    assert doc1_list["items"][0]["id"] == p1["id"]

    doc1_p2_res = client.get(f"/patients/{p2['id']}", headers=doctor1_fixture["headers"])
    assert doc1_p2_res.status_code == status.HTTP_403_FORBIDDEN

    doc1_p1_res = client.get(f"/patients/{p1['id']}", headers=doctor1_fixture["headers"])
    assert doc1_p1_res.status_code == status.HTTP_200_OK
    assert doc1_p1_res.json()["name"] == "Patient For Doc1"


def test_patient_patch_and_soft_delete(client, admin_headers):
    # Create patient
    p = client.post(
        "/patients",
        json={"name": "Initial Name", "age": 25, "phone": "1234567890"},
        headers=admin_headers,
    ).json()

    # PATCH partial update
    patch_res = client.patch(
        f"/patients/{p['id']}",
        json={"name": "Updated Name"},
        headers=admin_headers,
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["name"] == "Updated Name"
    assert patch_res.json()["age"] == 25

    # DELETE soft delete
    del_res = client.delete(f"/patients/{p['id']}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_200_OK
    assert del_res.json()["is_active"] is False

    # Already deactivated error
    del_again = client.delete(f"/patients/{p['id']}", headers=admin_headers)
    assert del_again.status_code == status.HTTP_400_BAD_REQUEST


def test_patient_age_gt_filter(client, admin_headers):
    client.post(
        "/patients",
        json={"name": "Young Person", "age": 22, "phone": "1111111111"},
        headers=admin_headers,
    )
    client.post(
        "/patients",
        json={"name": "Older Person", "age": 45, "phone": "2222222222"},
        headers=admin_headers,
    )

    res = client.get("/patients?age_gt=30", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    for item in data["data"]:
        assert item["age"] > 30


def test_patient_doctor_assignment_validation(client, admin_headers, doctor1_fixture):
    # Non-existing doctor returns 404
    res_not_found = client.post(
        "/patients",
        json={"name": "Orphan Patient", "age": 30, "phone": "3333333333", "doctor_id": 99999},
        headers=admin_headers,
    )
    assert res_not_found.status_code == status.HTTP_404_NOT_FOUND

    # Inactive doctor returns 400
    doc_id = doctor1_fixture["doctor"].id
    # Deactivate doctor
    client.delete(f"/doctors/{doc_id}", headers=admin_headers)

    res_inactive = client.post(
        "/patients",
        json={"name": "Unlucky Patient", "age": 30, "phone": "4444444444", "doctor_id": doc_id},
        headers=admin_headers,
    )
    assert res_inactive.status_code == status.HTTP_400_BAD_REQUEST
