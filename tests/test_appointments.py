from datetime import datetime, timezone, timedelta
from fastapi import status
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.doctor_patient import DoctorPatient
from app.models.appointment import Appointment, AppointmentStatus


def test_admin_can_create_appointment(client, admin_headers, doctor1_fixture):
    doc = doctor1_fixture["doctor"]
    patient_res = client.post(
        "/patients",
        json={"name": "Alice Wonderland", "age": 28, "phone": "1234567890", "doctor_id": doc.id},
        headers=admin_headers,
    )
    patient_id = patient_res.json()["id"]

    appt_time = "2026-11-10T10:00:00Z"
    res = client.post(
        "/appointments",
        json={
            "doctor_id": doc.id,
            "patient_id": patient_id,
            "appointment_date": appt_time,
            "status": "scheduled",
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["doctor_id"] == doc.id
    assert data["patient_id"] == patient_id
    assert data["status"] == "scheduled"
    assert data["created_by"] == "test_admin@example.com"
    assert data["created_at"] is not None


def test_doctor_can_create_appointment_for_self(client, doctor1_fixture, admin_headers):
    doc = doctor1_fixture["doctor"]
    doc_headers = doctor1_fixture["headers"]

    patient_res = client.post(
        "/patients",
        json={"name": "Bob Builder", "age": 40, "phone": "2234567890", "doctor_id": doc.id},
        headers=admin_headers,
    )
    patient_id = patient_res.json()["id"]

    res = client.post(
        "/appointments",
        json={
            "patient_id": patient_id,
            "appointment_date": "2026-11-12T14:00:00Z",
        },
        headers=doc_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    assert res.json()["doctor_id"] == doc.id
    assert res.json()["created_by"] == "doctor1@example.com"


def test_doctor_cannot_create_appointment_for_other_doctor(client, doctor1_fixture, doctor2_fixture, admin_headers):
    doc2 = doctor2_fixture["doctor"]
    doc1_headers = doctor1_fixture["headers"]

    patient_res = client.post(
        "/patients",
        json={"name": "Charlie Brown", "age": 30, "phone": "3234567890"},
        headers=admin_headers,
    )
    patient_id = patient_res.json()["id"]

    res = client.post(
        "/appointments",
        json={
            "doctor_id": doc2.id,
            "patient_id": patient_id,
            "appointment_date": "2026-11-15T09:00:00Z",
        },
        headers=doc1_headers,
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_admin_must_provide_doctor_id(client, admin_headers):
    res = client.post(
        "/appointments",
        json={
            "patient_id": 1,
            "appointment_date": "2026-11-15T09:00:00Z",
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST


def test_create_appointment_nonexistent_doctor_or_patient(client, admin_headers, doctor1_fixture):
    doc = doctor1_fixture["doctor"]

    # Nonexistent patient
    res_no_pat = client.post(
        "/appointments",
        json={
            "doctor_id": doc.id,
            "patient_id": 99999,
            "appointment_date": "2026-11-20T10:00:00Z",
        },
        headers=admin_headers,
    )
    assert res_no_pat.status_code == status.HTTP_404_NOT_FOUND

    # Nonexistent doctor
    patient_res = client.post(
        "/patients",
        json={"name": "David Miller", "age": 45, "phone": "4234567890"},
        headers=admin_headers,
    )
    patient_id = patient_res.json()["id"]

    res_no_doc = client.post(
        "/appointments",
        json={
            "doctor_id": 99999,
            "patient_id": patient_id,
            "appointment_date": "2026-11-20T10:00:00Z",
        },
        headers=admin_headers,
    )
    assert res_no_doc.status_code == status.HTTP_404_NOT_FOUND


def test_create_appointment_inactive_doctor_or_patient(client, admin_headers, db_session):
    # Inactive doctor
    inactive_doc = Doctor(
        name="Dr. Sleepy",
        specialization="Anesthesiology",
        email="sleepy@healthapp.com",
        is_active=False,
    )
    db_session.add(inactive_doc)

    # Inactive patient
    inactive_pat = Patient(
        name="Inactive Person",
        age=50,
        phone="5234567890",
        is_active=False,
    )
    db_session.add(inactive_pat)
    db_session.commit()

    # Active patient
    active_pat = Patient(
        name="Active Person",
        age=30,
        phone="6234567890",
        is_active=True,
    )
    db_session.add(active_pat)
    db_session.commit()

    # Try booking inactive doctor
    res_doc = client.post(
        "/appointments",
        json={
            "doctor_id": inactive_doc.id,
            "patient_id": active_pat.id,
            "appointment_date": "2026-11-22T10:00:00Z",
        },
        headers=admin_headers,
    )
    assert res_doc.status_code == status.HTTP_400_BAD_REQUEST

    # Try booking inactive patient
    active_doc = Doctor(
        name="Dr. Active",
        specialization="Pediatrics",
        email="active.doc@healthapp.com",
        is_active=True,
    )
    db_session.add(active_doc)
    db_session.commit()

    res_pat = client.post(
        "/appointments",
        json={
            "doctor_id": active_doc.id,
            "patient_id": inactive_pat.id,
            "appointment_date": "2026-11-22T10:00:00Z",
        },
        headers=admin_headers,
    )
    assert res_pat.status_code == status.HTTP_400_BAD_REQUEST


def test_prevent_overlapping_appointments_for_same_doctor(client, admin_headers, doctor1_fixture, doctor2_fixture):
    doc1 = doctor1_fixture["doctor"]
    doc2 = doctor2_fixture["doctor"]

    p_res = client.post(
        "/patients",
        json={"name": "Overlapping Test Patient", "age": 25, "phone": "7234567890"},
        headers=admin_headers,
    )
    patient_id = p_res.json()["id"]

    slot_time = "2026-12-01T10:00:00Z"

    # First appointment schedules cleanly
    res1 = client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": patient_id, "appointment_date": slot_time},
        headers=admin_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED
    appt1_id = res1.json()["id"]

    # Same time for same doctor fails
    res_same = client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": patient_id, "appointment_date": slot_time},
        headers=admin_headers,
    )
    assert res_same.status_code == status.HTTP_400_BAD_REQUEST
    assert "overlapping" in res_same.json()["detail"].lower()

    # Time within 15 minutes fails (overlap)
    res_near = client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": patient_id, "appointment_date": "2026-12-01T10:15:00Z"},
        headers=admin_headers,
    )
    assert res_near.status_code == status.HTTP_400_BAD_REQUEST

    # Same time for DIFFERENT doctor succeeds
    res_diff_doc = client.post(
        "/appointments",
        json={"doctor_id": doc2.id, "patient_id": patient_id, "appointment_date": slot_time},
        headers=admin_headers,
    )
    assert res_diff_doc.status_code == status.HTTP_201_CREATED

    # Cancel first appointment, now slot becomes available
    client.patch(
        f"/appointments/{appt1_id}",
        json={"status": "cancelled"},
        headers=admin_headers,
    )

    res_retry = client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": patient_id, "appointment_date": slot_time},
        headers=admin_headers,
    )
    assert res_retry.status_code == status.HTTP_201_CREATED


def test_list_appointments_and_role_restrictions(client, admin_headers, doctor1_fixture, doctor2_fixture):
    doc1 = doctor1_fixture["doctor"]
    doc2 = doctor2_fixture["doctor"]

    p_res = client.post(
        "/patients",
        json={"name": "List Filter Patient", "age": 33, "phone": "8234567890"},
        headers=admin_headers,
    )
    pid = p_res.json()["id"]

    # Create 1 appointment for doc1, 1 for doc2
    client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": pid, "appointment_date": "2026-12-05T09:00:00Z"},
        headers=admin_headers,
    )
    client.post(
        "/appointments",
        json={"doctor_id": doc2.id, "patient_id": pid, "appointment_date": "2026-12-05T11:00:00Z"},
        headers=admin_headers,
    )

    # Admin sees both
    admin_list = client.get("/appointments", headers=admin_headers)
    assert admin_list.status_code == status.HTTP_200_OK
    assert admin_list.json()["total_records"] >= 2

    # Doctor1 sees only their own
    doc1_list = client.get("/appointments", headers=doctor1_fixture["headers"])
    assert doc1_list.status_code == status.HTTP_200_OK
    for item in doc1_list.json()["items"]:
        assert item["doctor_id"] == doc1.id

    # Doctor1 trying to query doctor2's appointments gets 403
    doc1_try_doc2 = client.get(f"/appointments?doctor_id={doc2.id}", headers=doctor1_fixture["headers"])
    assert doc1_try_doc2.status_code == status.HTTP_403_FORBIDDEN


def test_appointment_crud_and_status_updates(client, admin_headers, doctor1_fixture):
    doc = doctor1_fixture["doctor"]
    p_res = client.post(
        "/patients",
        json={"name": "Lifecycle Patient", "age": 30, "phone": "9988776655"},
        headers=admin_headers,
    )
    pid = p_res.json()["id"]

    create_res = client.post(
        "/appointments",
        json={"doctor_id": doc.id, "patient_id": pid, "appointment_date": "2026-12-10T14:00:00Z"},
        headers=admin_headers,
    )
    appt_id = create_res.json()["id"]

    # Get single appointment
    get_res = client.get(f"/appointments/{appt_id}", headers=admin_headers)
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["id"] == appt_id

    # PUT update
    put_res = client.put(
        f"/appointments/{appt_id}",
        json={
            "doctor_id": doc.id,
            "patient_id": pid,
            "appointment_date": "2026-12-10T15:00:00Z",
            "status": "completed",
        },
        headers=admin_headers,
    )
    assert put_res.status_code == status.HTTP_200_OK
    assert put_res.json()["status"] == "completed"
    assert put_res.json()["updated_by"] == "test_admin@example.com"

    # DELETE appointment
    del_res = client.delete(f"/appointments/{appt_id}", headers=admin_headers)
    assert del_res.status_code == status.HTTP_200_OK

    # 404 after deletion
    after_del = client.get(f"/appointments/{appt_id}", headers=admin_headers)
    assert after_del.status_code == status.HTTP_404_NOT_FOUND


def test_doctor_and_patient_appointment_subroutes(client, admin_headers, doctor1_fixture, doctor2_fixture):
    doc1 = doctor1_fixture["doctor"]
    doc2 = doctor2_fixture["doctor"]

    p_res = client.post(
        "/patients",
        json={"name": "Subroute Patient", "age": 22, "phone": "1231231234", "doctor_id": doc1.id},
        headers=admin_headers,
    )
    pid = p_res.json()["id"]

    client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": pid, "appointment_date": "2026-12-12T10:00:00Z"},
        headers=admin_headers,
    )

    # GET /doctors/{id}/appointments
    # Doctor1 accessing own appointments -> 200
    res_doc1_own = client.get(f"/doctors/{doc1.id}/appointments", headers=doctor1_fixture["headers"])
    assert res_doc1_own.status_code == status.HTTP_200_OK
    assert len(res_doc1_own.json()["items"]) >= 1

    # Doctor1 accessing Doctor2 appointments -> 403
    res_doc1_doc2 = client.get(f"/doctors/{doc2.id}/appointments", headers=doctor1_fixture["headers"])
    assert res_doc1_doc2.status_code == status.HTTP_403_FORBIDDEN

    # Admin accessing Doctor2 appointments -> 200
    res_admin_doc2 = client.get(f"/doctors/{doc2.id}/appointments", headers=admin_headers)
    assert res_admin_doc2.status_code == status.HTTP_200_OK

    # GET /patients/{id}/appointments
    # Doctor1 assigned to patient -> 200
    res_p_doc1 = client.get(f"/patients/{pid}/appointments", headers=doctor1_fixture["headers"])
    assert res_p_doc1.status_code == status.HTTP_200_OK

    # Doctor2 NOT assigned to patient -> 403
    res_p_doc2 = client.get(f"/patients/{pid}/appointments", headers=doctor2_fixture["headers"])
    assert res_p_doc2.status_code == status.HTTP_403_FORBIDDEN


def test_doctor_appointment_lifecycle_permissions(client, admin_headers, doctor1_fixture, doctor2_fixture):
    doc1 = doctor1_fixture["doctor"]
    doc2 = doctor2_fixture["doctor"]

    p_res = client.post(
        "/patients",
        json={"name": "Perm Patient", "age": 28, "phone": "9998887776", "doctor_id": doc1.id},
        headers=admin_headers,
    )
    pid = p_res.json()["id"]

    # Create appt for doc1
    appt1_res = client.post(
        "/appointments",
        json={"doctor_id": doc1.id, "patient_id": pid, "appointment_date": "2026-12-20T10:00:00Z"},
        headers=admin_headers,
    )
    appt1_id = appt1_res.json()["id"]

    # Doc1 updates own appt via patch -> 200
    patch_res = client.patch(
        f"/appointments/{appt1_id}",
        json={"status": "completed"},
        headers=doctor1_fixture["headers"],
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["status"] == "completed"

    # Doc1 attempts to reassign to Doc2 -> 403
    reassign_res = client.patch(
        f"/appointments/{appt1_id}",
        json={"doctor_id": doc2.id},
        headers=doctor1_fixture["headers"],
    )
    assert reassign_res.status_code == status.HTTP_403_FORBIDDEN

    # Doc2 attempts to view Doc1 appt -> 403
    view_res = client.get(f"/appointments/{appt1_id}", headers=doctor2_fixture["headers"])
    assert view_res.status_code == status.HTTP_403_FORBIDDEN

    # Doc2 attempts to update Doc1 appt -> 403
    doc2_patch = client.patch(
        f"/appointments/{appt1_id}",
        json={"status": "cancelled"},
        headers=doctor2_fixture["headers"],
    )
    assert doc2_patch.status_code == status.HTTP_403_FORBIDDEN

    # Doc2 attempts to delete Doc1 appt -> 403
    doc2_del = client.delete(f"/appointments/{appt1_id}", headers=doctor2_fixture["headers"])
    assert doc2_del.status_code == status.HTTP_403_FORBIDDEN

    # Doc1 deletes own appt -> 200
    doc1_del = client.delete(f"/appointments/{appt1_id}", headers=doctor1_fixture["headers"])
    assert doc1_del.status_code == status.HTTP_200_OK

