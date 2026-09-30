from datetime import datetime, timezone, timedelta
from fastapi import status
import pytest

from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.appointment import Appointment, AppointmentStatus
from app.models.billing import Billing, PaymentStatus, PaymentMode


@pytest.fixture
def billing_setup(client, admin_headers, doctor1_fixture, doctor2_fixture):
    """Sets up doctors, patients, and appointments for billing tests."""
    doc1 = doctor1_fixture["doctor"]
    doc1_headers = doctor1_fixture["headers"]

    doc2 = doctor2_fixture["doctor"]
    doc2_headers = doctor2_fixture["headers"]

    # Create Patient 1 assigned to Doctor 1
    p1_res = client.post(
        "/patients",
        json={"name": "Patient One", "age": 30, "phone": "1111111111", "doctor_id": doc1.id},
        headers=admin_headers,
    )
    assert p1_res.status_code == status.HTTP_201_CREATED
    p1 = p1_res.json()

    # Create Patient 2 assigned to Doctor 2
    p2_res = client.post(
        "/patients",
        json={"name": "Patient Two", "age": 45, "phone": "2222222222", "doctor_id": doc2.id},
        headers=admin_headers,
    )
    assert p2_res.status_code == status.HTTP_201_CREATED
    p2 = p2_res.json()

    # Create Scheduled Appointment for Doctor 1 & Patient 1
    appt1_res = client.post(
        "/appointments",
        json={
            "doctor_id": doc1.id,
            "patient_id": p1["id"],
            "appointment_date": "2026-11-20T10:00:00Z",
            "status": "scheduled",
        },
        headers=admin_headers,
    )
    assert appt1_res.status_code == status.HTTP_201_CREATED
    appt1 = appt1_res.json()

    # Create Cancelled Appointment for Doctor 1 & Patient 1
    appt_cancel_res = client.post(
        "/appointments",
        json={
            "doctor_id": doc1.id,
            "patient_id": p1["id"],
            "appointment_date": "2026-11-21T10:00:00Z",
            "status": "cancelled",
        },
        headers=admin_headers,
    )
    assert appt_cancel_res.status_code == status.HTTP_201_CREATED
    appt_cancel = appt_cancel_res.json()

    return {
        "doc1": doc1,
        "doc1_headers": doc1_headers,
        "doc2": doc2,
        "doc2_headers": doc2_headers,
        "patient1": p1,
        "patient2": p2,
        "appt1": appt1,
        "appt_cancel": appt_cancel,
    }


# ============================================================================
# LEVEL 27: Billing Model, Business Rules, Validation, RBAC
# ============================================================================

def test_admin_can_create_billing_with_auto_calculation(client, admin_headers, billing_setup):
    setup = billing_setup
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "appointment_id": setup["appt1"]["id"],
            "consultation_fee": 150.0,
            "additional_charges": 25.50,
            "payment_status": "paid",
            "payment_mode": "card",
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["patient_id"] == setup["patient1"]["id"]
    assert data["doctor_id"] == setup["doc1"].id
    assert data["appointment_id"] == setup["appt1"]["id"]
    assert data["consultation_fee"] == 150.0
    assert data["additional_charges"] == 25.50
    # Auto-calculated total amount: 150.0 + 25.50 = 175.50
    assert data["total_amount"] == 175.50
    assert data["payment_status"] == "paid"
    assert data["payment_mode"] == "card"
    assert data["is_active"] is True
    assert data["created_by"] == "test_admin@example.com"


def test_doctor_can_create_billing_for_self(client, billing_setup):
    setup = billing_setup
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "consultation_fee": 200.0,
            "additional_charges": 50.0,
            "payment_status": "pending",
            "payment_mode": "cash",
        },
        headers=setup["doc1_headers"],
    )
    assert res.status_code == status.HTTP_201_CREATED
    data = res.json()
    assert data["doctor_id"] == setup["doc1"].id
    assert data["total_amount"] == 250.0
    assert data["created_by"] == "doctor1@example.com"


def test_doctor_cannot_create_billing_for_other_doctor(client, billing_setup):
    setup = billing_setup
    res = client.post(
        "/billings",
        json={
            "doctor_id": setup["doc2"].id,
            "patient_id": setup["patient1"]["id"],
            "consultation_fee": 100.0,
        },
        headers=setup["doc1_headers"],
    )
    assert res.status_code == status.HTTP_403_FORBIDDEN


def test_admin_must_provide_doctor_id(client, admin_headers, billing_setup):
    setup = billing_setup
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "consultation_fee": 100.0,
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "doctor_id is required" in res.json()["detail"]


def test_create_billing_nonexistent_patient_or_doctor(client, admin_headers, billing_setup):
    setup = billing_setup
    # Non-existent patient
    res = client.post(
        "/billings",
        json={
            "patient_id": 999999,
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 100.0,
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND

    # Non-existent doctor
    res2 = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": 999999,
            "consultation_fee": 100.0,
        },
        headers=admin_headers,
    )
    assert res2.status_code == status.HTTP_404_NOT_FOUND


def test_create_billing_inactive_doctor_or_patient(client, admin_headers, billing_setup):
    setup = billing_setup
    # Deactivate doctor
    client.patch(
        f"/doctors/{setup['doc2'].id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc2"].id,
            "consultation_fee": 100.0,
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "inactive" in res.json()["detail"].lower()


def test_prevent_mismatched_appointment_doctor_and_patient(client, admin_headers, billing_setup):
    setup = billing_setup
    # Appointment belongs to Doc 1 & Patient 1, but we pass Patient 2
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient2"]["id"],
            "doctor_id": setup["doc1"].id,
            "appointment_id": setup["appt1"]["id"],
            "consultation_fee": 100.0,
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not belong" in res.json()["detail"].lower()


def test_prevent_billing_for_cancelled_appointment(client, admin_headers, billing_setup):
    setup = billing_setup
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "appointment_id": setup["appt_cancel"]["id"],
            "consultation_fee": 100.0,
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_400_BAD_REQUEST
    assert "cancelled" in res.json()["detail"].lower()


def test_prevent_duplicate_billing_for_same_appointment(client, admin_headers, billing_setup):
    setup = billing_setup
    # First billing
    res1 = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "appointment_id": setup["appt1"]["id"],
            "consultation_fee": 120.0,
        },
        headers=admin_headers,
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # Duplicate billing for same appointment
    res2 = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "appointment_id": setup["appt1"]["id"],
            "consultation_fee": 120.0,
        },
        headers=admin_headers,
    )
    assert res2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in res2.json()["detail"].lower()


def test_billing_read_update_delete_and_role_permissions(client, admin_headers, billing_setup):
    setup = billing_setup
    # Create billing under Doctor 1
    create_res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 100.0,
            "additional_charges": 20.0,
            "payment_status": "pending",
            "payment_mode": "cash",
        },
        headers=admin_headers,
    )
    billing_id = create_res.json()["id"]

    # Admin can view
    get_res = client.get(f"/billings/{billing_id}", headers=admin_headers)
    assert get_res.status_code == status.HTTP_200_OK

    # Doctor 1 can view
    doc1_get = client.get(f"/billings/{billing_id}", headers=setup["doc1_headers"])
    assert doc1_get.status_code == status.HTTP_200_OK

    # Doctor 2 cannot view Doc 1's billing (403 Forbidden)
    doc2_get = client.get(f"/billings/{billing_id}", headers=setup["doc2_headers"])
    assert doc2_get.status_code == status.HTTP_403_FORBIDDEN

    # Doctor 1 can update (PUT)
    put_res = client.put(
        f"/billings/{billing_id}",
        json={
            "consultation_fee": 150.0,
            "additional_charges": 30.0,
            "payment_status": "paid",
            "payment_mode": "upi",
        },
        headers=setup["doc1_headers"],
    )
    assert put_res.status_code == status.HTTP_200_OK
    assert put_res.json()["total_amount"] == 180.0
    assert put_res.json()["payment_status"] == "paid"
    assert put_res.json()["payment_mode"] == "upi"

    # Doctor 2 cannot update Doctor 1's billing (403)
    doc2_put = client.put(
        f"/billings/{billing_id}",
        json={"consultation_fee": 200.0},
        headers=setup["doc2_headers"],
    )
    assert doc2_put.status_code == status.HTTP_403_FORBIDDEN

    # PATCH test
    patch_res = client.patch(
        f"/billings/{billing_id}",
        json={"additional_charges": 50.0},
        headers=setup["doc1_headers"],
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["total_amount"] == 200.0  # 150.0 + 50.0

    # Doctor CANNOT delete billing record (403 Forbidden)
    doc_del = client.delete(f"/billings/{billing_id}", headers=setup["doc1_headers"])
    assert doc_del.status_code == status.HTTP_403_FORBIDDEN

    # Admin CAN delete billing record (soft delete)
    admin_del = client.delete(f"/billings/{billing_id}", headers=admin_headers)
    assert admin_del.status_code == status.HTTP_200_OK

    # Check soft deleted record
    check_res = client.get(f"/billings/{billing_id}", headers=admin_headers)
    assert check_res.status_code == status.HTTP_200_OK
    assert check_res.json()["is_active"] is False


def test_doctor_and_patient_billing_subroutes(client, admin_headers, billing_setup):
    setup = billing_setup
    # Create billing for patient 1 with doctor 1
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 100.0,
            "payment_status": "paid",
        },
        headers=admin_headers,
    )

    # GET /patients/{patient_id}/billings as admin
    p_res = client.get(f"/patients/{setup['patient1']['id']}/billings", headers=admin_headers)
    assert p_res.status_code == status.HTTP_200_OK
    assert len(p_res.json()["items"]) >= 1

    # GET /patients/{patient_id}/billings as Doctor 1 (assigned)
    p_doc1_res = client.get(f"/patients/{setup['patient1']['id']}/billings", headers=setup["doc1_headers"])
    assert p_doc1_res.status_code == status.HTTP_200_OK

    # GET /patients/{patient_id}/billings as Doctor 2 (unassigned -> 403)
    p_doc2_res = client.get(f"/patients/{setup['patient1']['id']}/billings", headers=setup["doc2_headers"])
    assert p_doc2_res.status_code == status.HTTP_403_FORBIDDEN

    # GET /doctors/{doctor_id}/billings as admin
    d_res = client.get(f"/doctors/{setup['doc1'].id}/billings", headers=admin_headers)
    assert d_res.status_code == status.HTTP_200_OK
    assert len(d_res.json()["items"]) >= 1

    # GET /doctors/{doctor_id}/billings as Doctor 1 for self
    d_doc1_res = client.get(f"/doctors/{setup['doc1'].id}/billings", headers=setup["doc1_headers"])
    assert d_doc1_res.status_code == status.HTTP_200_OK

    # GET /doctors/{doctor_id}/billings as Doctor 1 for Doctor 2 (403)
    d_doc2_res = client.get(f"/doctors/{setup['doc2'].id}/billings", headers=setup["doc1_headers"])
    assert d_doc2_res.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# LEVEL 28: Billing Reports & Filtering
# ============================================================================

def test_billing_filtering_and_pagination(client, admin_headers, billing_setup):
    setup = billing_setup
    # Create multiple billings
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 100.0,
            "payment_status": "pending",
        },
        headers=admin_headers,
    )
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 200.0,
            "payment_status": "paid",
        },
        headers=admin_headers,
    )

    # Filter by payment_status=paid
    res_paid = client.get("/billings?payment_status=paid", headers=admin_headers)
    assert res_paid.status_code == status.HTTP_200_OK
    for b in res_paid.json()["items"]:
        assert b["payment_status"] == "paid"

    # Filter by doctor_id
    res_doc = client.get(f"/billings?doctor_id={setup['doc1'].id}", headers=admin_headers)
    assert res_doc.status_code == status.HTTP_200_OK
    assert res_doc.json()["total_records"] >= 2

    # Pagination
    res_paginated = client.get("/billings?page=1&limit=1", headers=admin_headers)
    assert res_paginated.status_code == status.HTTP_200_OK
    assert len(res_paginated.json()["items"]) == 1
    assert res_paginated.json()["meta"]["page"] == 1
    assert res_paginated.json()["meta"]["page_size"] == 1


def test_revenue_report_generation(client, admin_headers, billing_setup):
    setup = billing_setup
    # Doc 1: 150 + 250 = 400 paid
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 150.0,
            "payment_status": "paid",
        },
        headers=admin_headers,
    )
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 250.0,
            "payment_status": "paid",
        },
        headers=admin_headers,
    )

    # Doc 2: 500 paid
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient2"]["id"],
            "doctor_id": setup["doc2"].id,
            "consultation_fee": 500.0,
            "payment_status": "paid",
        },
        headers=admin_headers,
    )

    # One pending billing (should NOT be counted in revenue)
    client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "consultation_fee": 999.0,
            "payment_status": "pending",
        },
        headers=admin_headers,
    )

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Admin requests all revenue
    res = client.get(f"/reports/revenue?from={today_str}&to={today_str}", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK
    report = res.json()
    assert report["total_revenue"] >= 900.0
    assert report["total_paid_records"] >= 3
    assert len(report["revenue_by_doctor"]) >= 2
    assert len(report["revenue_by_day"]) >= 1

    # Filter by Doc 1
    res_doc1 = client.get(f"/reports/revenue?doctor_id={setup['doc1'].id}", headers=admin_headers)
    assert res_doc1.status_code == status.HTTP_200_OK
    doc1_report = res_doc1.json()
    assert doc1_report["total_revenue"] == 400.0

    # Doctor 1 requests self
    doc1_self = client.get("/reports/revenue", headers=setup["doc1_headers"])
    assert doc1_self.status_code == status.HTTP_200_OK
    assert doc1_self.json()["total_revenue"] == 400.0

    # Doctor 1 requests Doctor 2 (403 Forbidden)
    doc1_doc2 = client.get(f"/reports/revenue?doctor_id={setup['doc2'].id}", headers=setup["doc1_headers"])
    assert doc1_doc2.status_code == status.HTTP_403_FORBIDDEN


# ============================================================================
# LEVEL 29: Transactions & Consistency
# ============================================================================

def test_transaction_creates_billing_and_completes_appointment(client, admin_headers, billing_setup):
    setup = billing_setup
    # Initially appt1 is scheduled
    appt_before = client.get(f"/appointments/{setup['appt1']['id']}", headers=admin_headers).json()
    assert appt_before["status"] == "scheduled"

    # Create billing for appointment
    res = client.post(
        "/billings",
        json={
            "patient_id": setup["patient1"]["id"],
            "doctor_id": setup["doc1"].id,
            "appointment_id": setup["appt1"]["id"],
            "consultation_fee": 150.0,
            "payment_status": "paid",
        },
        headers=admin_headers,
    )
    assert res.status_code == status.HTTP_201_CREATED

    # Verify appointment status was atomically updated to completed
    appt_after = client.get(f"/appointments/{setup['appt1']['id']}", headers=admin_headers).json()
    assert appt_after["status"] == "completed"


def test_api_v1_versioning_for_billings(client, admin_headers, billing_setup):
    setup = billing_setup
    res = client.get("/api/v1/billings", headers=admin_headers)
    assert res.status_code == status.HTTP_200_OK

    res_report = client.get("/api/v1/reports/revenue", headers=admin_headers)
    assert res_report.status_code == status.HTTP_200_OK
