"""Doctor management and role-restriction tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

DOCTOR_PAYLOAD = {"name": "Dr. Arun Kumar", "specialization": "Cardiology", "email": "arun@gmail.com"}


def test_admin_creates_doctor(client: TestClient, admin_headers) -> None:
    res = client.post("/doctors", json=DOCTOR_PAYLOAD, headers=admin_headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Dr. Arun Kumar"
    assert body["specialization"] == "Cardiology"
    assert body["email"] == "arun@gmail.com"
    assert body["is_active"] is True
    assert "password" not in body


def test_non_admin_cannot_create_doctor(client: TestClient, doctor_headers) -> None:
    res = client.post("/doctors", json=DOCTOR_PAYLOAD, headers=doctor_headers)
    assert res.status_code == 403


def test_unauthenticated_cannot_create_doctor(client: TestClient) -> None:
    assert client.post("/doctors", json=DOCTOR_PAYLOAD).status_code == 401


def test_duplicate_doctor_email(client: TestClient, admin_headers, doctor_id) -> None:
    existing = client.get(f"/doctors/{doctor_id}", headers=admin_headers).json()["email"]
    res = client.post("/doctors", json={**DOCTOR_PAYLOAD, "email": existing}, headers=admin_headers)
    assert res.status_code == 409


def test_get_doctors_list(client: TestClient, admin_headers, doctor_id) -> None:
    res = client.get("/doctors", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 1
    assert body["items"][0]["id"] == doctor_id


def test_get_doctors_filter_by_specialization(client: TestClient, admin_headers) -> None:
    client.post(
        "/doctors",
        json={"name": "Dr. Arun Kumar", "specialization": "Cardiology", "email": "arun@gmail.com"},
        headers=admin_headers,
    )
    client.post(
        "/doctors",
        json={"name": "Dr. Meera", "specialization": "Neurology", "email": "meera@gmail.com"},
        headers=admin_headers,
    )
    res = client.get("/doctors?specialization=Cardiology", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["meta"]["total"] == 1
    assert body["items"][0]["email"] == "arun@gmail.com"

    no_match = client.get("/doctors?specialization=Oncology", headers=admin_headers)
    assert no_match.json()["meta"]["total"] == 0


def test_get_doctors_pagination(client: TestClient, admin_headers, doctor_id) -> None:
    for i in range(2, 6):
        client.post(
            "/doctors",
            json={"name": f"Dr. Doc {i}", "specialization": "Orthopedics", "email": f"d{i}@gmail.com"},
            headers=admin_headers,
        )
    page1 = client.get("/doctors?page=1&page_size=2", headers=admin_headers).json()
    page2 = client.get("/doctors?page=2&page_size=2", headers=admin_headers).json()
    assert page1["meta"] == {"total": 5, "page": 1, "page_size": 2, "pages": 3}
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    assert page1["items"][0]["id"] != page2["items"][0]["id"]


def test_get_doctor_by_id(client: TestClient, admin_headers, doctor_id) -> None:
    res = client.get(f"/doctors/{doctor_id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "arun@test.com"


def test_get_doctor_not_found(client: TestClient, admin_headers) -> None:
    assert client.get("/doctors/9999", headers=admin_headers).status_code == 404


def test_get_doctors_unauthenticated(client: TestClient) -> None:
    assert client.get("/doctors").status_code == 401


def test_admin_updates_doctor(client: TestClient, admin_headers, doctor_id) -> None:
    res = client.put(
        f"/doctors/{doctor_id}",
        json={"specialization": "Cardiothoracic Surgery", "name": "Dr. Arun Kumar Sr."},
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["specialization"] == "Cardiothoracic Surgery"
    assert res.json()["name"] == "Dr. Arun Kumar Sr."


def test_update_doctor_duplicate_email(client: TestClient, admin_headers, doctor_id, second_doctor_id) -> None:
    other = client.get(f"/doctors/{second_doctor_id}", headers=admin_headers).json()["email"]
    res = client.put(f"/doctors/{doctor_id}", json={"email": other}, headers=admin_headers)
    assert res.status_code == 409


def test_doctor_cannot_update_doctor(client: TestClient, doctor_headers, doctor_id) -> None:
    assert client.put(f"/doctors/{doctor_id}", json={"name": "Hack"}, headers=doctor_headers).status_code == 403


def test_admin_soft_deletes_doctor(client: TestClient, admin_headers, doctor_id, db_session) -> None:
    from app.models import Doctor

    res = client.delete(f"/doctors/{doctor_id}", headers=admin_headers)
    assert res.status_code == 200
    assert "deactivated" in res.json()["message"]

    row = db_session.get(Doctor, doctor_id)
    assert row is not None, "row must still exist after a soft delete"
    assert row.is_active is False


def test_soft_deleted_doctor_hidden_by_default(client: TestClient, admin_headers, doctor_id) -> None:
    client.delete(f"/doctors/{doctor_id}", headers=admin_headers)
    assert client.get("/doctors", headers=admin_headers).json()["meta"]["total"] == 0
    with_inactive = client.get("/doctors?include_inactive=true", headers=admin_headers).json()
    assert with_inactive["meta"]["total"] == 1
    assert with_inactive["items"][0]["is_active"] is False


def test_delete_doctor_requires_admin(client: TestClient, doctor_headers, doctor_id) -> None:
    assert client.delete(f"/doctors/{doctor_id}", headers=doctor_headers).status_code == 403


def test_delete_missing_doctor_404(client: TestClient, admin_headers) -> None:
    assert client.delete("/doctors/4242", headers=admin_headers).status_code == 404