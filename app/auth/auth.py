"""Password hashing, JWT creation/verification and the OAuth2 scheme."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User

# bcrypt via pwdlib (passlib is unmaintained and breaks with bcrypt>=4.1).
password_hash = PasswordHash((BcryptHasher(),))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


# --------------------------------------------------------------- passwords ---
def hash_password(plain_password: str) -> str:
    """Return a bcrypt hash for the given plain-text password."""
    return password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Constant-time verification of a plain-text password against a hash."""
    try:
        return password_hash.verify(plain_password, hashed_password)
    except Exception:  # malformed hash in the database
        return False


# --------------------------------------------------------------------- JWT ---
def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Create a signed JWT for the given user subject."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire, "iat": datetime.now(timezone.utc)}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT, raising 401 when it is invalid or expired."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise CREDENTIALS_ERROR
    if not payload.get("sub"):
        raise CREDENTIALS_ERROR
    return payload


# ------------------------------------------------------------ dependencies ---
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the Bearer token."""
    payload = verify_token(token)
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        raise CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if user is None:
        raise CREDENTIALS_ERROR
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive"
        )
    return user