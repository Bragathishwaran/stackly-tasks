# Doctor and Patient Management API

A simple, beginner-friendly **REST API** for managing doctors and patients, built with
FastAPI. Doctors and patients are stored in memory (plain Python dictionaries), so no
database is needed and all data disappears when the server stops.

---

## Technologies used

| Tool          | Purpose                                             |
| ------------- | --------------------------------------------------- |
| Python 3.9+   | Programming language                                 |
| FastAPI       | Web framework, automatic validation and docs        |
| Pydantic      | Data validation for request and response bodies     |
| Uvicorn       | ASGI server used to run the app                     |
| email-validator | Validates the `email` field                       |

---

## Project structure

```
doctor_patient_api/
│
├── main.py           # FastAPI app + all endpoints (in-memory storage)
├── models.py         # Pydantic request models (validation of incoming data)
├── schemas.py        # Pydantic response models (shape of the data returned)
├── requirements.txt  # Dependencies
└── README.md         # This file
```

`models.py` = **input** schemas (what clients send) &nbsp;•&nbsp; `schemas.py` = **output**
schemas (what the API returns).

---

## Installation

```bash
cd doctor_patient_api

# (optional but recommended) create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
```

---

## How to run the server

```bash
uvicorn main:app --reload
```

Then open:

* Swagger UI: <http://127.0.0.1:8000/docs>
* ReDoc: <http://127.0.0.1:8000/redoc>

You can also run `python main.py`, which starts Uvicorn on `127.0.0.1:8000` for you.

---

## API endpoints

| Method | Path               | Description              | Success code |
| ------ | ------------------ | ------------------------ | ------------ |
| POST   | `/doctors`         | Create a new doctor      | 201 Created  |
| GET    | `/doctors`         | List all doctors         | 200 OK       |
| GET    | `/doctors/{id}`    | Get one doctor by id     | 200 OK       |
| POST   | `/patients`        | Create a new patient     | 201 Created  |
| GET    | `/patients`        | List all patients        | 200 OK       |

Error codes:

* `404 Not Found` — the requested `doctor_id` does not exist
  (`{"detail": "Doctor not found"}`)
* `422 Unprocessable Entity` — the request body failed validation (automatic)

---

## Example requests

### Create a doctor — `POST /doctors`

```json
{
  "name": "Dr. Ada Lovelace",
  "specialization": "Cardiology",
  "email": "ada.lovelace@example.com",
  "is_active": true
}
```

`is_active` is optional and defaults to `true`.

**Response (201):**

```json
{
  "doctor_id": 1,
  "name": "Dr. Ada Lovelace",
  "specialization": "Cardiology",
  "email": "ada.lovelace@example.com",
  "is_active": true
}
```

### Create a patient — `POST /patients`

```json
{
  "name": "Grace Hopper",
  "age": 36,
  "phone": "+1-555-0100"
}
```

**Response (201):**

```json
{
  "patient_id": 1,
  "name": "Grace Hopper",
  "age": 36,
  "phone": "+1-555-0100"
}
```

### curl examples

```bash
curl -X POST http://127.0.0.1:8000/doctors \
  -H "Content-Type: application/json" \
  -d '{"name": "Dr. Ada Lovelace", "specialization": "Cardiology", "email": "ada.lovelace@example.com"}'

curl http://127.0.0.1:8000/doctors
curl http://127.0.0.1:8000/doctors/1
```

---

## Validation rules

**Doctor**

| Field            | Rule                                       |
| ---------------- | ------------------------------------------ |
| `name`           | Required, non-empty string                 |
| `specialization` | Required, non-empty string                 |
| `email`          | Required, valid email address              |
| `is_active`      | Optional boolean, defaults to `true`       |

**Patient**

| Field   | Rule                                    |
| ------- | --------------------------------------- |
| `name`  | Required, non-empty string              |
| `age`   | Required integer, greater than `0`      |
| `phone` | Required, non-empty string              |

---

## Error handling summary

| Situation                        | Status | Body                                                |
| -------------------------------- | ------ | --------------------------------------------------- |
| Doctor id does not exist         | 404    | `{"detail": "Doctor not found"}`                    |
| Invalid email                    | 422    | Pydantic validation details                         |
| Patient `age` is `0` or negative | 422    | Pydantic validation details                         |
| Empty `name` / `specialization`   | 422    | Pydantic validation details                         |

All validation errors are reported automatically by FastAPI in this shape:

```json
{
  "detail": [
    {
      "loc": ["body", "age"],
      "msg": "Input should be greater than 0",
      "type": "greater_than"
    }
  ]
}
```

---

## Possible next steps

* Add `PUT` / `DELETE` endpoints
* Persist data with SQLAlchemy and SQLite
* Add authentication (OAuth2 / JWT)
* Link patients to doctors via appointments