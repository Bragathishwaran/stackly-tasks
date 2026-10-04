"""Manual end-to-end verification of the running API (not part of the test suite).

Usage:  python verify_workflow.py [base_url]
"""
from __future__ import annotations

import sys

import httpx

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE, timeout=15.0)
failures: list[str] = []


def step(label: str, method: str, path: str, expected: int | tuple[int, ...], **kw) -> dict:
    response = client.request(method, path, **kw)
    ok = expected in response.status_code if isinstance(expected, tuple) else response.status_code == expected
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label:<52} {method} {path} -> {response.status_code}")
    if not ok:
        failures.append(f"{label}: expected {expected}, got {response.status_code}: {response.text}")
    if "json" not in response.headers.get("content-type", ""):
        return {}
    return response.json()


print(f"--- verifying {BASE} ---\n")

step("service metadata", "GET", "/", 200)
step("health check", "GET", "/health", 200)
step("openapi schema", "GET", "/openapi.json", 200)
step("swagger ui", "GET", "/docs", 200)
step("redoc ui", "GET", "/redoc", 200)

# 1. Register admin
step("register admin", "POST", "/auth/register", 201,
     json={"name": "Admin User", "email": "admin@gmail.com", "password": "admin123", "role": "admin"})
step("register duplicate admin -> 409", "POST", "/auth/register", 409,
     json={"name": "Admin User", "email": "admin@gmail.com", "password": "admin123", "role": "admin"})

# 2. Login admin
admin_token = step("login admin", "POST", "/auth/login", 200,
                   json={"email": "admin@gmail.com", "password": "admin123"})["access_token"]
admin = {"Authorization": f"Bearer {admin_token}"}
step("login admin wrong password -> 401", "POST", "/auth/login", 401,
     json={"email": "admin@gmail.com", "password": "nope"})
step("GET /doctors without token -> 401", "GET", "/doctors", 401)
step("GET /doctors bad token -> 401", "GET", "/doctors", 401, headers={"Authorization": "Bearer garbage"})
step("current user is admin", "GET", "/auth/me", 200, headers=admin)

# 3. Create doctors
step("create doctor 1", "POST", "/doctors", 201,
     json={"name": "Dr. Arun Kumar", "specialization": "Cardiology", "email": "arun@gmail.com"}, headers=admin)
meera = step("create doctor 2", "POST", "/doctors", 201,
             json={"name": "Dr. Meera Singh", "specialization": "Neurology", "email": "meera@gmail.com"}, headers=admin)
step("duplicate doctor email -> 409", "POST", "/doctors", 409,
     json={"name": "Dr. Copy", "specialization": "Cardiology", "email": "arun@gmail.com"}, headers=admin)

# 4. Create patients
step("create patient 1", "POST", "/patients", 201,
     json={"name": "Rahul", "age": 28, "phone": "9876543210"}, headers=admin)
patient2 = step("create patient 2", "POST", "/patients", 201,
                json={"name": "Priya", "age": 34, "phone": "9123456780"}, headers=admin)
step("invalid age -> 422", "POST", "/patients", 422,
     json={"name": "Bad", "age": 0, "phone": "9876543210"}, headers=admin)
step("invalid phone -> 422", "POST", "/patients", 422,
     json={"name": "Bad", "age": 20, "phone": "12345"}, headers=admin)

# 5. Register doctor accounts linked to the doctor records
step("register doctor account (arun)", "POST", "/auth/register", 201,
     json={"name": "Dr. Arun Kumar", "email": "arun@gmail.com", "password": "doctor123", "role": "doctor"})
step("register doctor account (meera)", "POST", "/auth/register", 201,
     json={"name": "Dr. Meera Singh", "email": "meera@gmail.com", "password": "doctor123", "role": "doctor"})
step("register invalid role -> 422", "POST", "/auth/register", 422,
     json={"name": "N", "email": "n@gmail.com", "password": "doctor123", "role": "nurse"})

arun_token = step("login doctor arun", "POST", "/auth/login", 200,
                  json={"email": "arun@gmail.com", "password": "doctor123"})["access_token"]
arun = {"Authorization": f"Bearer {arun_token}"}
meera_h = {"Authorization": f"Bearer {step('login doctor meera', 'POST', '/auth/login', 200, json={'email': 'meera@gmail.com', 'password': 'doctor123'})['access_token']}"}

doctors = step("list doctors", "GET", "/doctors?page=1&page_size=10", 200, headers=admin)
ids = {d["name"]: d["id"] for d in doctors["items"]}
arun_id, meera_id = ids["Dr. Arun Kumar"], ids["Dr. Meera Singh"]
print(f"       doctors -> arun={arun_id} meera={meera_id}")
patient_id = step("list patients", "GET", "/patients", 200, headers=admin)["items"][0]["id"]

# 6. Role restrictions
step("doctor cannot create doctor -> 403", "POST", "/doctors", 403,
     json={"name": "X", "specialization": "Y", "email": "x@gmail.com"}, headers=arun)
step("doctor cannot create patient -> 403", "POST", "/patients", 403,
     json={"name": "X", "age": 20, "phone": "9876543210"}, headers=arun)
step("doctor cannot update doctor -> 403", "PUT", f"/doctors/{arun_id}", 403,
     json={"name": "Hacked"}, headers=arun)
step("doctor cannot delete doctor -> 403", "DELETE", f"/doctors/{meera_id}", 403, headers=arun)

# 7. Assignments
step("assign patient 1 to arun", "POST", f"/doctors/{arun_id}/patients/{patient_id}", 201, headers=admin)
step("duplicate assignment -> 409", "POST", f"/doctors/{arun_id}/patients/{patient_id}", 409, headers=admin)
step("assign patient 2 to meera", "POST", f"/doctors/{meera_id}/patients/{patient2['id']}", 201, headers=admin)
step("assign to unknown patient -> 404", "POST", f"/doctors/{arun_id}/patients/9999", 404, headers=admin)
step("doctor cannot assign -> 403", "POST", f"/doctors/{arun_id}/patients/{patient_id}", 403, headers=arun)

# 8. Visibility
seen = step("doctor arun sees own patients", "GET", "/patients", 200, headers=arun)
print(f"       arun sees {seen['meta']['total']} patient(s): {[p['name'] for p in seen['items']]}")
if seen["meta"]["total"] != 1 or seen["items"][0]["name"] != "Rahul":
    failures.append("arun should only see his assigned patient Rahul")

seen_m = step("doctor meera sees own patients", "GET", "/patients", 200, headers=meera_h)
if seen_m["meta"]["total"] != 1 or seen_m["items"][0]["name"] != "Priya":
    failures.append("meera should only see her assigned patient Priya")

step("arun cannot read meera's patient -> 403", "GET", f"/patients/{patient2['id']}", 403, headers=arun)
step("arun cannot list meera's patients -> 403", "GET", f"/doctors/{meera_id}/patients", 403, headers=arun)
step("admin lists arun's patients", "GET", f"/doctors/{arun_id}/patients", 200, headers=admin)
step("arun lists own patients via path", "GET", f"/doctors/{arun_id}/patients", 200, headers=arun)
step("missing doctor -> 404", "GET", "/doctors/9999", 404, headers=admin)
step("missing patient -> 404", "GET", "/patients/9999", 404, headers=admin)
step("patients pagination", "GET", "/patients?page=1&page_size=1", 200, headers=admin)

# 9. Updates + soft delete
step("admin updates doctor", "PUT", f"/doctors/{arun_id}", 200,
     json={"specialization": "Cardiothoracic Surgery"}, headers=admin)
step("update to duplicate email -> 409", "PUT", f"/doctors/{arun_id}", 409,
     json={"email": "meera@gmail.com"}, headers=admin)
step("admin soft deletes doctor", "DELETE", f"/doctors/{meera_id}", 200, headers=admin)
hidden = step("deleted doctor hidden from list", "GET", "/doctors", 200, headers=admin)
if any(d["id"] == meera_id for d in hidden["items"]):
    failures.append("soft deleted doctor should not be listed")
step("deleted doctor visible with include_inactive", "GET", "/doctors?include_inactive=true", 200, headers=admin)
step("assign to inactive doctor -> 400", "POST", f"/doctors/{meera_id}/patients/{patient2['id']}", 400, headers=admin)
step("deactivated doctor cannot log in -> 403", "POST", "/auth/login", 403,
     json={"email": "meera@gmail.com", "password": "doctor123"})
step("unassign patient", "DELETE", f"/doctors/{arun_id}/patients/{patient_id}", 200, headers=admin)

print("\n--- summary ---")
if failures:
    print(f"{len(failures)} check(s) failed:")
    for item in failures:
        print(f"  - {item}")
    sys.exit(1)
print("All workflow checks passed.")