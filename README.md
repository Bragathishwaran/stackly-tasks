# Doctor & Patient Management API

Production-style FastAPI backend for managing doctors, patients and
doctor-patient assignments with JWT authentication and role-based
authorization.

## 1. Project overview

A layered REST API where **admins** manage doctors, patients and assignments,
while **doctors** only ever see the patients assigned to them. Passwords are
hashed with bcrypt, tokens are signed JWTs validated on every request, and all
database access lives in a service layer that routers cannot bypass.

- Base URL: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- OpenAPI JSON: `http://127.0.0.1:8000/openapi.json`

## 2. Features

- JWT auth with `admin` / `doctor` roles, token expiry and signature checks
- Role-based dependencies: `get_current_user`, `require_admin`, `require_doctor`,
  `require_admin_or_doctor`, `get_current_doctor`
- Doctor CRUD (admin) with soft delete (`is_active = false`)
- Patient CRUD with age (`> 0`) and phone (10-15 digits) validation
- Doctor-patient assignment with duplicate protection (409)
- Doctors can only list/read their own assigned patients
- Pagination (`page`, `page_size`) plus specialization / search filters
- Environment-driven configuration via `.env` + `pydantic-settings`
- Global exception handlers returning clean JSON (no stack traces)
- Swagger + ReDoc with a bearer-token Authorize button
- 54 pytest tests using an isolated in-memory SQLite database

## 3. Technology stack

| Concern | Library |
| --- | --- |
| Web framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x |
| Database | SQLite |
| Validation | Pydantic v2 / `EmailStr` |
| Settings | pydantic-settings (+ python-dotenv) |
| JWT | python-jose |
| Password hashing | pwdlib with bcrypt |
| Tests | pytest + httpx (FastAPI TestClient) |

## 4. Project structure

```text
doctor_patient_api/
├── app/
│   ├── __init__.py
│   ├── main.py                 # app factory, lifespan, exception handlers
│   ├── config.py               # pydantic-settings Settings
│   ├── database.py             # engine, SessionLocal, get_db, Base
│   ├── models.py               # User, Doctor, Patient, DoctorPatient
│   ├── schemas.py              # all request/response schemas
│   ├── dependencies.py         # auth + role dependencies
│   ├── auth/
│   │   ├── __init__.py
│   │   └── auth.py             # hashing, create/verify token, get_current_user
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py             # /auth/*
│   │   ├── doctors.py          # /doctors/* + assignments
│   │   └── patients.py         # /patients/*
│   └── services/
│       ├── __init__.py
│       ├── user_service.py     # register / authenticate
│       ├── doctor_service.py   # doctor CRUD + assignment logic
│       └── patient_service.py  # patient CRUD + access scoping
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_doctors.py
│   └── test_patients.py
├── .env / .env.example
├── .gitignore / .dockerignore
├── pytest.ini
├── requirements.txt
├── postman_collection.json
├── verify_workflow.py          # live end-to-end smoke script
├── Dockerfile
└── README.md
```

Routers only handle request parsing, dependencies and response codes; all
queries and business rules live in `app/services/`.

## 5. Installation

Requires Python 3.9+ (developed and tested on 3.11+).

```bash
cd doctor_patient_api
python -m venv venv
```

### Windows

```powershell
venv\Scripts\Activate.ps1
```

### macOS / Linux

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## 6. `.env` configuration

`.env` ships with development defaults (create it from the example if missing):

```env
DATABASE_URL=sqlite:///./doctor_patient.db
SECRET_KEY=change-this-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

`SECRET_KEY` is read only from the environment - never hardcoded in the source.
For anything beyond local development, set a long random value, e.g.
`python -c "import secrets; print(secrets.token_urlsafe(48))"`.

Optional keys: `SQL_ECHO=true` for SQL logging, `CORS_ORIGINS` as a comma
separated list, plus `PROJECT_NAME`, `VERSION` and `API_PREFIX`.

## 7. Database setup

Tables are created automatically on startup (`Base.metadata.create_all`).
For a clean slate, delete the database file and restart:

```bash
del doctor_patient.db        # Windows
rm doctor_patient.db         # macOS / Linux
```

Schema:

- **users** - id, name, email (unique), hashed_password, role, is_active, created_at
- **doctors** - id, name, specialization, email (unique), is_active, user_id (FK, optional)
- **patients** - id, name, age, phone, created_at
- **doctor_patients** - id, doctor_id (FK), patient_id (FK),
  unique(doctor_id, patient_id)

## 8. Running the application

```bash
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/docs>, click **Authorize**, paste a token and
explore the endpoints.

## 9. Authentication flow

1. `POST /auth/register` with `role: "admin"` to create the first admin.
2. `POST /auth/login` -> `{"access_token": "...", "token_type": "bearer"}`.
3. Send `Authorization: Bearer <token>` on protected routes.
4. A doctor login is linked to the `doctors` row sharing the same email, which
   is how "my patients" is resolved.

Token failures: missing/invalid/expired token -> **401**; inactive account or
insufficient role -> **403**.

## 10. API endpoints

| Method | Path | Access | Description |
| --- | --- | --- | --- |
| GET | `/` | public | Service metadata |
| GET | `/health` | public | Health check |
| POST | `/auth/register` | public | Register (`admin` or `doctor`) |
| POST | `/auth/login` | public | Obtain JWT |
| GET | `/auth/me` | any | Current user profile |
| POST | `/auth/logout` | any | Informational logout |
| POST | `/doctors` | admin | Create doctor |
| GET | `/doctors` | any | List doctors (paged, filterable) |
| GET | `/doctors/{id}` | any | Doctor details |
| PUT | `/doctors/{id}` | admin | Partial update |
| DELETE | `/doctors/{id}` | admin | Soft delete |
| POST | `/doctors/{did}/patients/{pid}` | admin | Assign patient |
| GET | `/doctors/{did}/patients` | admin / owner | Doctor's patients |
| DELETE | `/doctors/{did}/patients/{pid}` | admin | Unassign |
| POST | `/patients` | admin | Create patient |
| GET | `/patients` | any | Admin: all; doctor: assigned only |
| GET | `/patients/{id}` | any | Authorized access only |
| PUT | `/patients/{id}` | admin | Partial update |
| DELETE | `/patients/{id}` | admin | Hard delete |

Status codes used: 200, 201, 400, 401, 403, 404, 409, 422.

## 11. Example requests

```bash
BASE=http://127.0.0.1:8000

# Register admin
curl -X POST $BASE/auth/register -H "Content-Type: application/json" \
  -d '{"name":"Admin User","email":"admin@gmail.com","password":"admin123","role":"admin"}'

# Login
curl -X POST $BASE/auth/login -H "Content-Type: application/json" \
  -d '{"email":"admin@gmail.com","password":"admin123"}'
# -> {"access_token":"eyJ...","token_type":"bearer"}

TOKEN=<paste token>
curl $BASE/auth/me -H "Authorization: Bearer $TOKEN"

# Create doctor
curl -X POST $BASE/doctors -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Dr. Arun Kumar","specialization":"Cardiology","email":"arun@gmail.com"}'

# Create patient
curl -X POST $BASE/patients -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Rahul","age":28,"phone":"9876543210"}'

# Assign patient 1 to doctor 1
curl -X POST $BASE/doctors/1/patients/1 -H "Authorization: Bearer $TOKEN"

# Doctor login and own patients
curl -X POST $BASE/auth/login -H "Content-Type: application/json" \
  -d '{"email":"arun@gmail.com","password":"doctor123"}'
curl $BASE/patients -H "Authorization: Bearer $DOCTOR_TOKEN"
curl $BASE/doctors/2/patients -H "Authorization: Bearer $DOCTOR_TOKEN"   # 403
```

## 12. Postman testing

Import `postman_collection.json`, then run requests in this order:

1. `Health > Health Check`
2. `Auth > Register Admin` (test script logs in and sets `admin_token`)
3. `Auth > Register Doctor`, `Auth > Register Second Doctor`
4. `Doctors > Create Doctor` (sets `doctor_id`),
   `Doctors > Create Second Doctor` (sets `second_doctor_id`)
5. `Patients > Create Patient` (sets `patient_id`)
6. `Assignments > Assign Patient To Doctor`
7. `Auth > Login Admin` and `Auth > Login Doctor` (set the tokens)
8. `Patients > Get Patients (doctor sees only assigned)`
9. `Assignments > Get Doctor Patients (other doctor -> 403)` - expect 403
10. `Doctors > Update Doctor`, then `Doctors > Soft Delete Doctor` last

Collection variables: `base_url`, `admin_token`, `doctor_token`, `doctor_id`,
`second_doctor_id`, `patient_id`.

## 13. Running the tests

```bash
pytest                 # 54 tests
pytest -v              # verbose
pytest tests/test_auth.py
```

Tests use an isolated in-memory SQLite database (tables truncated between
tests) and the FastAPI `TestClient`, so they never touch `doctor_patient.db`.

An additional live smoke test runs against a started server:

```bash
uvicorn app.main:app --reload      # terminal 1
python verify_workflow.py          # terminal 2
```

It walks the full business flow and prints PASS/FAIL per check.

## 14. Docker

```bash
docker build -t doctor-patient-api .
docker run -p 8000:8000 doctor-patient-api
```

The image starts Uvicorn on `0.0.0.0:8000`; tables are created on startup and
the SQLite file is written inside the container. Mount a volume for
persistence: `docker run -p 8000:8000 -v "$(pwd)/data:/code/data" doctor-patient-api`
with `DATABASE_URL=sqlite:////code/data/doctor_patient.db`.

## 15. Security notes

- bcrypt hashing, plain-text passwords never stored or returned
- `SECRET_KEY` only from the environment; signature and expiry validated
- inactive accounts rejected (403) at login and on every request
- role checks enforced by dependencies, not by route handlers alone
- doctors are confined to their own assigned patients (403 otherwise)
- unique constraints on user email, doctor email and (doctor, patient) pairs
- SQLAlchemy Core/ORM parameter binding everywhere (no string-built SQL)
- exception handlers return JSON messages; stack traces stay in the logs