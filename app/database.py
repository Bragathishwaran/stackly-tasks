"""Database engine, session factory and declarative base."""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite needs check_same_thread disabled for FastAPI's threadpool usage.
# An in-memory database additionally requires StaticPool so all sessions share
# the same connection (used by the test-suite).
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
    engine_kwargs: dict = {"connect_args": connect_args, "echo": settings.SQL_ECHO}
    if DATABASE_URL in ("sqlite://", "sqlite:///:memory:"):
        engine_kwargs["poolclass"] = StaticPool
else:  # pragma: no cover - other backends are not used in this project
    engine_kwargs = {"echo": settings.SQL_ECHO}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for every ORM model."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()