from fastapi import status


def test_assign_patient_by_admin(client, admin_headers, doctor1_fixture):
    p_res = client.post(
        "/patients",
        json={"name": "Assigned Patient", "age": 45, "phone": "9876543210"},
        headers=admin_headers,
    )
    patient_id = p_res.json()["id"]
    doctor_id = doctor1_fixture["doctor"].id

    assign_res = client.post(
        f"/doctors/{doctor_id}/patients/{patient_id}",
        headers=admin_headers,
    )
    assert assign_res.status_code == status.HTTP_200_OK
    data = assign_res.json()
    assert data["doctor_id"] == doctor_id
    assert data["patient_id"] == patient_id
    assert "assigned_at" in data


def test_doctor_can_assign_patient_to_self(client, doctor1_fixture):
    p_res = client.post(
        "/patients",
        json={"name": "Self Assigned", "age": 33, "phone": "1234567890"},
        headers=doctor1_fixture["headers"],
    )
    patient_id = p_res.json()["id"]
    doctor_id = doctor1_fixture["doctor"].id

    fetch_res = client.get(
        f"/doctors/{doctor_id}/patients",
        headers=doctor1_fixture["headers"],
    )
    assert fetch_res.status_code == status.HTTP_200_OK
    assert fetch_res.json()["meta"]["total_items"] >= 1


def test_doctor_cannot_assign_patient_to_other_doctor(client, doctor1_fixture, doctor2_fixture, admin_headers):
    patient = client.post(
        "/patients",
        json={"name": "Cross Patient", "age": 60, "phone": "9998887776"},
        headers=admin_headers,
    ).json()

    target_doctor_id = doctor2_fixture["doctor"].id

    res = client.post(
        f"/doctors/{target_doctor_id}/patients/{patient['id']}",
        headers=doctor1_fixture["headers"],
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_duplicate_assignment_rejected(client, admin_headers, doctor1_fixture):
    patient = client.post(
        "/patients",
        json={"name": "Duplicate Test", "age": 55, "phone": "8887776665"},
        headers=admin_headers,
    ).json()

    doc_id = doctor1_fixture["doctor"].id

    res1 = client.post(f"/doctors/{doc_id}/patients/{patient['id']}", headers=admin_headers)
    assert res1.status_code == status.HTTP_200_OK

    res2 = client.post(f"/doctors/{doc_id}/patients/{patient['id']}", headers=admin_headers)
    assert res2.status_code == status.HTTP_400_BAD_REQUEST


def test_assign_to_nonexistent_doctor_or_patient(client, admin_headers):
    res_doc = client.post("/doctors/9999/patients/1", headers=admin_headers)
    assert res_doc.status_code == status.HTTP_404_NOT_FOUND

    doc = client.post(
        "/doctors",
        json={"name": "Dr. Exist", "specialization": "General", "email": "exist@med.com"},
        headers=admin_headers,
    ).json()
    res_pat = client.post(f"/doctors/{doc['id']}/patients/9999", headers=admin_headers)
    assert res_pat.status_code == status.HTTP_404_NOT_FOUND


def test_doctor_cannot_view_other_doctors_patient_list(client, doctor1_fixture, doctor2_fixture):
    doc2_id = doctor2_fixture["doctor"].id

    res = client.get(f"/doctors/{doc2_id}/patients", headers=doctor1_fixture["headers"])
    assert res.status_code == status.HTTP_403_FORBIDDEN
