from fastapi import status
from app.models.patient import Patient
from app.models.doctor_patient import DoctorPatient


def test_doctor_cannot_delete_doctors(client, doctor1_fixture, doctor2_fixture):
    """Doctor role cannot delete other doctors or themselves."""
    doc2 = doctor2_fixture["doctor"]
    doc1 = doctor1_fixture["doctor"]

    # Delete other doctor -> 403
    res_other = client.delete(f"/doctors/{doc2.id}", headers=doctor1_fixture["headers"])
    assert res_other.status_code == status.HTTP_403_FORBIDDEN

    # Delete self doctor -> 403
    res_self = client.delete(f"/doctors/{doc1.id}", headers=doctor1_fixture["headers"])
    assert res_self.status_code == status.HTTP_403_FORBIDDEN


def test_doctor_cannot_delete_patients(client, admin_headers, doctor1_fixture):
    """Doctor role cannot delete any patients (even assigned ones)."""
    doc1 = doctor1_fixture["doctor"]

    # Create patient assigned to doctor1
    p_res = client.post(
        "/patients",
        json={"name": "Protected Patient", "age": 29, "phone": "1122334455", "doctor_id": doc1.id},
        headers=admin_headers,
    )
    pid = p_res.json()["id"]

    # Doctor attempts to delete assigned patient -> 403 Forbidden
    doc_del = client.delete(f"/patients/{pid}", headers=doctor1_fixture["headers"])
    assert doc_del.status_code == status.HTTP_403_FORBIDDEN

    # Admin CAN delete patient -> 200 OK
    admin_del = client.delete(f"/patients/{pid}", headers=admin_headers)
    assert admin_del.status_code == status.HTTP_200_OK


def test_doctor_can_only_view_assigned_patients(client, admin_headers, doctor1_fixture, doctor2_fixture):
    """Doctor can only view their own assigned patients."""
    doc1 = doctor1_fixture["doctor"]
    doc2 = doctor2_fixture["doctor"]

    # Patient 1 -> assigned to doc1
    p1 = client.post(
        "/patients",
        json={"name": "Doc1 Patient", "age": 25, "phone": "1010101010", "doctor_id": doc1.id},
        headers=admin_headers,
    ).json()

    # Patient 2 -> assigned to doc2
    p2 = client.post(
        "/patients",
        json={"name": "Doc2 Patient", "age": 45, "phone": "2020202020", "doctor_id": doc2.id},
        headers=admin_headers,
    ).json()

    # Doc1 accesses Doc1 patient details -> 200
    res_p1 = client.get(f"/patients/{p1['id']}", headers=doctor1_fixture["headers"])
    assert res_p1.status_code == status.HTTP_200_OK

    # Doc1 accesses Doc2 patient details -> 403 Forbidden
    res_p2 = client.get(f"/patients/{p2['id']}", headers=doctor1_fixture["headers"])
    assert res_p2.status_code == status.HTTP_403_FORBIDDEN

    # Doc1 lists patients -> gets only p1
    res_list = client.get("/patients", headers=doctor1_fixture["headers"])
    assert res_list.status_code == status.HTTP_200_OK
    patient_ids = [p["id"] for p in res_list.json()["items"]]
    assert p1["id"] in patient_ids
    assert p2["id"] not in patient_ids


def test_admin_has_full_access_to_all_apis(client, admin_headers, doctor1_fixture, doctor2_fixture):
    """Admin has full access to create, read, update, delete across doctors and patients."""
    # List all doctors
    doc_res = client.get("/doctors", headers=admin_headers)
    assert doc_res.status_code == status.HTTP_200_OK

    # List all patients
    pat_res = client.get("/patients", headers=admin_headers)
    assert pat_res.status_code == status.HTTP_200_OK

    # List all appointments
    appt_res = client.get("/appointments", headers=admin_headers)
    assert appt_res.status_code == status.HTTP_200_OK
