"""Shared pytest fixtures: isolated in-memory database and TestClient."""
from __future__ import annotations

import os
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-only-0123456789")

from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

ADMIN_CREDENTIALS = {"name": "Admin User", "email": "admin@test.com", "password": "admin123", "role": "admin"}
DOCTOR_CREDENTIALS = {"name": "Dr. Arun Kumar", "email": "arun@test.com", "password": "doctor123", "role": "doctor"}


@pytest.fixture(scope="session")
def engine():
    """In-memory SQLite engine shared by every session-scoped connection."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="session")
def TestingSessionLocal(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def db_session(TestingSessionLocal) -> Iterator[Session]:
    """Yield a session that is rolled back after every test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(TestingSessionLocal) -> Iterator[TestClient]:
    """TestClient wired to the test session, tables created/dropped per test."""

    def override_get_db() -> Iterator[Session]:
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def truncate_tables(engine) -> Iterator[None]:
    """Keep the in-memory database clean before every test."""
    from sqlalchemy import text

    with engine.connect() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f"DELETE FROM {table.name}"))
        conn.commit()
    yield


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    """Register + login an admin and return its Authorization header."""
    res = client.post("/auth/register", json=ADMIN_CREDENTIALS)
    assert res.status_code == 201, res.text
    token = client.post(
        "/auth/login", json={"email": ADMIN_CREDENTIALS["email"], "password": ADMIN_CREDENTIALS["password"]}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def doctor_headers(client: TestClient, admin_headers) -> dict[str, str]:
    """Create a doctor account through the admin, then log that doctor in."""
    create_user = client.post(
        "/auth/register", json={"name": "Dr. Arun Kumar", "email": "arun@test.com", "password": "doctor123", "role": "doctor"}
    )
    assert create_user.status_code == 201, create_user.text
    login = client.post("/auth/login", json={"email": "arun@test.com", "password": "doctor123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture()
def second_doctor_headers(client: TestClient, doctor_headers) -> dict[str, str]:
    """A second doctor account, used to prove cross-doctor isolation."""
    res = client.post(
        "/auth/register",
        json={"name": "Dr. Meera Singh", "email": "meera@test.com", "password": "doctor123", "role": "doctor"},
    )
    assert res.status_code == 201, res.text
    login = client.post("/auth/login", json={"email": "meera@test.com", "password": "doctor123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture()
def doctor_id(client: TestClient, admin_headers, doctor_headers) -> int:
    """Id of the doctor record created for `arun@test.com`."""
    doctors = client.get("/doctors", headers=admin_headers).json()["items"]
    assert doctors, "doctor record should exist after registering a doctor account"
    return doctors[0]["id"]


@pytest.fixture()
def second_doctor_id(client: TestClient, admin_headers, second_doctor_headers) -> int:
    doctors = client.get("/doctors", headers=admin_headers).json()["items"]
    meera = [d for d in doctors if d["email"] == "meera@test.com"]
    assert meera, "second doctor record should exist"
    return meera[0]["id"]


@pytest.fixture()
def patient(client: TestClient, admin_headers) -> dict:
    res = client.post(
        "/patients",
        json={"name": "Rahul", "age": 28, "phone": "9876543210"},
        headers=admin_headers,
    )
    assert res.status_code == 201, res.text
    return res.json()