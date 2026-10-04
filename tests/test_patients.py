"""Patient management tests: validation, role scoping and assignments."""
from __future__ import annotations

from fastapi.testclient import TestClient


# --------------------------------------------------------------- creation ---
def test_admin_creates_patient(client: TestClient, admin_headers) -> None:
    res = client.post(
        "/patients", json={"name": "Rahul", "age": 28, "phone": "9876543210"}, headers=admin_headers
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Rahul"
    assert body["age"] == 28
    assert body["phone"] == "9876543210"
    assert body["doctor_ids"] == []


def test_doctor_cannot_create_patient(client: TestClient, doctor_headers) -> None:
    res = client.post(
        "/patients", json={"name": "Rahul", "age": 28, "phone": "9876543210"}, headers=doctor_headers
    )
    assert res.status_code == 403


def test_invalid_age_rejected(client: TestClient, admin_headers) -> None:
    for age in (0, -5):
        res = client.post(
            "/patients", json={"name": "Rahul", "age": age, "phone": "9876543210"}, headers=admin_headers
        )
        assert res.status_code == 422


def test_invalid_phone_rejected(client: TestClient, admin_headers) -> None:
    for phone in ("12345", "1234567890123456", "98765abcde", ""):
        res = client.post(
            "/patients", json={"name": "Rahul", "age": 28, "phone": phone}, headers=admin_headers
        )
        assert res.status_code == 422, phone


def test_missing_name_rejected(client: TestClient, admin_headers) -> None:
    res = client.post("/patients", json={"age": 28, "phone": "9876543210"}, headers=admin_headers)
    assert res.status_code == 422


# ----------------------------------------------------------------- listing ---
def test_admin_gets_all_patients(client: TestClient, admin_headers, patient) -> None:
    res = client.get("/patients", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1


def test_get_patients_pagination(client: TestClient, admin_headers, patient) -> None:
    for i in range(2, 5):
        client.post(
            "/patients",
            json={"name": f"P{i}", "age": 30 + i, "phone": "9000000000"},
            headers=admin_headers,
        )
    page1 = client.get("/patients?page=1&page_size=2", headers=admin_headers).json()
    page2 = client.get("/patients?page=2&page_size=2", headers=admin_headers).json()
    assert page1["meta"]["total"] == 4
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2


def test_get_patient_by_id(client: TestClient, admin_headers, patient) -> None:
    res = client.get(f"/patients/{patient['id']}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Rahul"


def test_get_patient_not_found(client: TestClient, admin_headers) -> None:
    assert client.get("/patients/9999", headers=admin_headers).status_code == 404


def test_get_patients_unauthenticated(client: TestClient) -> None:
    assert client.get("/patients").status_code == 401


def test_doctor_sees_only_assigned_patients(
    client: TestClient, doctor_headers, admin_headers, second_doctor_headers, doctor_id, second_doctor_id, patient
) -> None:
    client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)

    res = client.get("/patients", headers=doctor_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1
    assert res.json()["items"][0]["name"] == "Rahul"

    # The second doctor has no assignments at all.
    other = client.get("/patients", headers=second_doctor_headers)
    assert other.status_code == 200
    assert other.json()["meta"]["total"] == 0


def test_doctor_cannot_read_unassigned_patient(
    client: TestClient, doctor_headers, second_doctor_headers, patient
) -> None:
    res = client.get(f"/patients/{patient['id']}", headers=second_doctor_headers)
    assert res.status_code == 403


# ------------------------------------------------------------ assignments ---
def test_assign_patient_to_doctor(client: TestClient, admin_headers, doctor_id, patient) -> None:
    res = client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    assert res.status_code == 201, res.text
    assert res.json()["doctor_id"] == doctor_id
    assert res.json()["patient_id"] == patient["id"]


def test_duplicate_assignment_conflict(client: TestClient, admin_headers, doctor_id, patient) -> None:
    assert client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers).status_code == 201
    res = client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    assert res.status_code == 409


def test_assign_unknown_patient(client: TestClient, admin_headers, doctor_id) -> None:
    assert client.post(f"/doctors/{doctor_id}/patients/9999", headers=admin_headers).status_code == 404


def test_assign_unknown_doctor(client: TestClient, admin_headers, patient) -> None:
    assert client.post(f"/doctors/9999/patients/{patient['id']}", headers=admin_headers).status_code == 404


def test_assign_to_inactive_doctor(client: TestClient, admin_headers, doctor_id, patient) -> None:
    client.delete(f"/doctors/{doctor_id}", headers=admin_headers)
    res = client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    assert res.status_code == 400


def test_assign_requires_admin(client: TestClient, doctor_headers, doctor_id, patient) -> None:
    res = client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=doctor_headers)
    assert res.status_code == 403


def test_doctor_lists_own_patients(
    client: TestClient, admin_headers, doctor_headers, doctor_id, patient
) -> None:
    client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    res = client.get(f"/doctors/{doctor_id}/patients", headers=doctor_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1
    assert res.json()["items"][0]["id"] == patient["id"]


def test_doctor_cannot_list_other_doctor_patients(
    client: TestClient, admin_headers, doctor_headers, doctor_id, second_doctor_id, patient
) -> None:
    client.post(f"/doctors/{second_doctor_id}/patients/{patient['id']}", headers=admin_headers)
    res = client.get(f"/doctors/{second_doctor_id}/patients", headers=doctor_headers)
    assert res.status_code == 403


def test_admin_lists_any_doctor_patients(
    client: TestClient, admin_headers, doctor_headers, doctor_id, second_doctor_id, patient
) -> None:
    client.post(f"/doctors/{second_doctor_id}/patients/{patient['id']}", headers=admin_headers)
    res = client.get(f"/doctors/{second_doctor_id}/patients", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["meta"]["total"] == 1


def test_assigned_patient_shows_doctor_ids(
    client: TestClient, admin_headers, doctor_id, patient
) -> None:
    client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    res = client.get(f"/patients/{patient['id']}", headers=admin_headers)
    assert res.json()["doctor_ids"] == [doctor_id]


def test_unassign_patient(client: TestClient, admin_headers, doctor_id, patient) -> None:
    client.post(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    res = client.delete(f"/doctors/{doctor_id}/patients/{patient['id']}", headers=admin_headers)
    assert res.status_code == 200
    assert client.get(f"/patients/{patient['id']}", headers=admin_headers).json()["doctor_ids"] == []