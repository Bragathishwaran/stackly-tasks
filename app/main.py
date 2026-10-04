"""FastAPI application entry point."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import Base, engine
from app.routers import auth as auth_router
from app.routers import doctors as doctors_router
from app.routers import patients as patients_router
from app.schemas import MessageResponse

logger = logging.getLogger("doctor_patient_api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables on startup."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready: %s", settings.DATABASE_URL)
    yield


tags_metadata = [
    {"name": "Authentication", "description": "Register, login and inspect the current user."},
    {"name": "Doctors", "description": "Doctor CRUD (admin) plus doctor-patient assignments."},
    {"name": "Patients", "description": "Patient CRUD (admin) and role-scoped patient reads."},
    {"name": "Health", "description": "Service liveness probe."},
]

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-style FastAPI backend for managing doctors and patients.\n\n"
        "* JWT authentication with `admin` and `doctor` roles\n"
        "* Admin-only doctor, patient and assignment management\n"
        "* Doctors only see the patients assigned to them\n"
        "* Swagger UI at `/docs`, ReDoc at `/redoc`\n\n"
        "Use the **Authorize** button to attach a bearer token."
    ),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------ error handling ---
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return a stable 422 payload without leaking internals."""
    errors = [
        {"loc": list(err.get("loc", [])), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors})


@app.exception_handler(IntegrityError)
async def integrity_exception_handler(request: Request, exc: IntegrityError) -> JSONResponse:
    """Translate database uniqueness violations into 409 responses."""
    logger.warning("Integrity error on %s: %s", request.url.path, exc.orig)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Resource conflict with existing data"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler: log the error, never return the traceback."""
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ----------------------------------------------------------------- routers ---
app.include_router(auth_router.router, prefix=settings.API_PREFIX)
app.include_router(doctors_router.router, prefix=settings.API_PREFIX)
app.include_router(patients_router.router, prefix=settings.API_PREFIX)


@app.get(
    "/",
    tags=["Health"],
    summary="Service metadata",
    description="Returns the API name, version and documentation links.",
)
def root() -> dict[str, str]:
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get(
    "/health",
    tags=["Health"],
    response_model=MessageResponse,
    summary="Health check",
)
def health_check() -> MessageResponse:
    """Simple liveness probe."""
    return MessageResponse(message="healthy")