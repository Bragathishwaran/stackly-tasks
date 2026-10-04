"""Authentication tests: registration, login and token handling."""
from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.auth.auth import create_access_token


def test_register_success(client: TestClient) -> None:
    res = client.post(
        "/auth/register",
        json={"name": "Admin User", "email": "admin@gmail.com", "password": "admin123", "role": "admin"},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["email"] == "admin@gmail.com"
    assert body["role"] == "admin"
    assert body["is_active"] is True
    assert "password" not in body
    assert "hashed_password" not in body


def test_register_duplicate_email(client: TestClient) -> None:
    payload = {"name": "Admin", "email": "dup@gmail.com", "password": "admin123", "role": "admin"}
    assert client.post("/auth/register", json=payload).status_code == 201
    res = client.post("/auth/register", json=payload)
    assert res.status_code == 409
    assert "already registered" in res.json()["detail"]


def test_register_invalid_email(client: TestClient) -> None:
    res = client.post(
        "/auth/register",
        json={"name": "X", "email": "not-an-email", "password": "admin123", "role": "admin"},
    )
    assert res.status_code == 422


def test_register_invalid_role(client: TestClient) -> None:
    res = client.post(
        "/auth/register",
        json={"name": "X", "email": "x@gmail.com", "password": "admin123", "role": "nurse"},
    )
    assert res.status_code == 422


def test_register_missing_password(client: TestClient) -> None:
    res = client.post("/auth/register", json={"name": "X", "email": "x@gmail.com", "role": "admin"})
    assert res.status_code == 422


def test_password_is_hashed(client: TestClient, db_session) -> None:
    from app.services import user_service

    client.post(
        "/auth/register",
        json={"name": "Admin", "email": "hash@gmail.com", "password": "secret123", "role": "admin"},
    )
    user = user_service.get_user_by_email(db_session, "hash@gmail.com")
    assert user is not None
    assert user.hashed_password != "secret123"
    assert user.hashed_password.startswith("$2")


def test_login_success(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Admin", "email": "admin@gmail.com", "password": "admin123", "role": "admin"},
    )
    res = client.post("/auth/login", json={"email": "admin@gmail.com", "password": "admin123"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_invalid_password(client: TestClient) -> None:
    client.post(
        "/auth/register",
        json={"name": "Admin", "email": "admin@gmail.com", "password": "admin123", "role": "admin"},
    )
    res = client.post("/auth/login", json={"email": "admin@gmail.com", "password": "wrong"})
    assert res.status_code == 401
    assert "detail" in res.json()


def test_login_unknown_user(client: TestClient) -> None:
    res = client.post("/auth/login", json={"email": "ghost@gmail.com", "password": "whatever"})
    assert res.status_code == 401


def test_invalid_token(client: TestClient) -> None:
    res = client.get("/doctors", headers={"Authorization": "Bearer not-a-real-token"})
    assert res.status_code == 401


def test_missing_token(client: TestClient) -> None:
    assert client.get("/doctors").status_code == 401


def test_tampered_token_rejected(client: TestClient, doctor_headers) -> None:
    token = doctor_headers["Authorization"].split()[1]
    tampered = token[:-3] + ("aaa" if not token.endswith("aaa") else "bbb")
    res = client.get("/doctors", headers={"Authorization": f"Bearer {tampered}"})
    assert res.status_code == 401


def test_expired_token_rejected(client: TestClient, doctor_headers) -> None:
    expired = create_access_token(subject=1, expires_delta=timedelta(minutes=-5))
    res = client.get("/doctors", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401


def test_me_endpoint(client: TestClient, admin_headers) -> None:
    res = client.get("/auth/me", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["email"] == "admin@test.com"