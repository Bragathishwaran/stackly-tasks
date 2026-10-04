"""Registration and login endpoints."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.auth import create_access_token, get_current_user
from app.database import get_db
from app.models import User
from app.schemas import MessageResponse, Token, UserLogin, UserRegister, UserResponse
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description=(
        "Creates an account with the `admin` or `doctor` role. The password is "
        "hashed with bcrypt and never returned. Registering a doctor account "
        "also links it to a doctor record so the account can read its patients."
    ),
    responses={
        409: {"description": "Email already registered"},
        422: {"description": "Invalid payload"},
    },
)
def register(payload: UserRegister, db: Session = Depends(get_db)) -> User:
    """Register a user account."""
    return user_service.create_user(db, payload)


@router.post(
    "/login",
    response_model=Token,
    summary="Login and obtain a JWT",
    description="Validates the credentials and returns a signed bearer token.",
    responses={
        401: {"description": "Incorrect email or password"},
        403: {"description": "Account inactive"},
    },
)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    """Authenticate a user and issue an access token."""
    user = user_service.authenticate_user(db, payload.email, payload.password)
    token = create_access_token(subject=user.id, extra_claims={"role": user.role.value})
    return Token(access_token=token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Current authenticated user",
    description="Returns the profile behind the supplied bearer token.",
    responses={401: {"description": "Missing or invalid token"}},
)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the currently authenticated user."""
    return current_user


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Logout (client side)",
    description=(
        "Stateless JWT logout is performed by discarding the token on the client. "
        "This endpoint exists so the Postman collection and clients have an "
        "explicit call to make."
    ),
)
def logout() -> MessageResponse:
    return MessageResponse(message="Logged out successfully")