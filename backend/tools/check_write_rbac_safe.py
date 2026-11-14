#!/usr/bin/env python3
r"""FINTECH OCR - Phase 2 / write-RBAC negative smoke checks.

Safety scope:
- Reads the local PostgreSQL invoices table to verify the probe ID is absent.
- Logs in using existing demo users (which may update last_login_at).
- Sends write-method requests ONLY to a nonexistent invoice ID.
- Never submits a real file or uses a real invoice ID.
- It is NOT a complete authorization test of legitimate write operations.

Run from backend directory:
    .\.venv\Scripts\python.exe .\tools\check_write_rbac_safe.py
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

import requests
from sqlalchemy import text

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

BASE_URL = "http://127.0.0.1:8000"
PROBE_ID = 2147483647
LOGIN_PATH = "/api/v1/auth/login"
EMAILS = {
    "admin": "admin@fintech.local",
    "accountant": "accountant@fintech.local",
    "employee": "employee@fintech.local",
}
TIMEOUT = 12


def stop(reason: str) -> None:
    print(f"[STOP] {reason}")
    raise SystemExit(1)


def check_db() -> None:
    try:
        from app.core import SessionLocal
        with SessionLocal() as session:
            dialect = session.bind.dialect.name
            if dialect != "postgresql":
                stop(f"Current backend DB dialect is '{dialect}', expected 'postgresql'.")
            n = session.execute(
                text("SELECT count(*) FROM invoices WHERE id = :id"),
                {"id": PROBE_ID},
            ).scalar_one()
            if n:
                stop(f"Probe invoice ID {PROBE_ID} already exists. No tests were sent.")
            count = session.execute(text("SELECT count(*) FROM invoices")).scalar_one()
            print(f"[OK] PostgreSQL connected. Existing invoices: {count}. Probe ID {PROBE_ID} does not exist.")
    except SystemExit:
        raise
    except Exception as exc:
        stop(f"Cannot confirm safe test ID in PostgreSQL: {type(exc).__name__}: {exc}")


def login(role: str, password: str) -> str:
    try:
        r = requests.post(
            BASE_URL + LOGIN_PATH,
            json={"email": EMAILS[role], "password": password},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        stop(f"Login request failed: {type(exc).__name__}: {exc}")
    if r.status_code != 200:
        stop(f"{role} login returned HTTP {r.status_code}. Check demo password / Backend.")
    try:
        data = r.json()
        token = data.get("access_token") or data.get("token")
        if not token and isinstance(data.get("data"), dict):
            token = data["data"].get("access_token")
    except ValueError:
        token = None
    if not isinstance(token, str) or not token:
        stop(f"{role} login succeeded but response has no access token.")
    print(f"[OK] {role} login: HTTP 200 (token hidden)")
    return token


CASES = [
    # Anonymous calls; upload intentionally omits the required file. HTTP 422 is inconclusive.
    ("anonymous", "PUT", f"/api/v1/invoices/{PROBE_ID}", {"seller_name": "RBAC_TEST"}),
    ("anonymous", "POST", "/api/v1/invoices/upload", None),
    ("anonymous", "POST", f"/api/v1/invoices/{PROBE_ID}/submit", None),
    ("anonymous", "POST", f"/api/v1/invoices/{PROBE_ID}/approval", {"action": "approve", "reason": "RBAC test"}),
    ("anonymous", "POST", f"/api/v1/invoices/{PROBE_ID}/lookup", {"result": "valid", "note": "RBAC test"}),
    # These roles should NOT be permitted to perform these operations.
    ("employee", "POST", f"/api/v1/invoices/{PROBE_ID}/approval", {"action": "approve", "reason": "RBAC test"}),
    ("employee", "POST", f"/api/v1/invoices/{PROBE_ID}/lookup", {"result": "valid", "note": "RBAC test"}),
    ("accountant", "PUT", f"/api/v1/invoices/{PROBE_ID}", {"seller_name": "RBAC_TEST"}),
    ("admin", "PUT", f"/api/v1/invoices/{PROBE_ID}", {"seller_name": "RBAC_TEST"}),
    ("accountant", "POST", f"/api/v1/invoices/{PROBE_ID}/submit", None),
    ("admin", "POST", f"/api/v1/invoices/{PROBE_ID}/submit", None),
]


def main() -> None:
    print("FINTECH OCR | WRITE RBAC | NONEXISTENT-ID SAFETY SMOKE TEST")
    print("No real invoice will be targeted; no file will be uploaded.")
    print("Login may update last_login_at. 404/422 means INCONCLUSIVE, not a permission PASS.\n")
    check_db()
    try:
        health = requests.get(BASE_URL + "/health", timeout=TIMEOUT)
    except requests.RequestException as exc:
        stop(f"Backend is unavailable: {exc}")
    if health.status_code != 200:
        stop(f"Backend /health returned HTTP {health.status_code}")
    print("[OK] Backend health endpoint: HTTP 200")
    password = getpass.getpass("Shared demo-account password (hidden): ")
    if not password:
        stop("Password was blank")
    tokens = {role: login(role, password) for role in EMAILS}
    password = ""  # Do not print or save password.
    print("\n--- Unauthorized write checks against NONEXISTENT invoice ID ---")
    passed = 0
    inconclusive = 0
    failed = 0
    for role, method, path, payload in CASES:
        headers = {"Authorization": f"Bearer {tokens[role]}"} if role != "anonymous" else {}
        try:
            response = requests.request(
                method,
                BASE_URL + path,
                headers=headers,
                json=payload,
                timeout=TIMEOUT,
            )
            code = response.status_code
        except requests.RequestException as exc:
            print(f"[ERROR] {role:10s} {method:4s} {path} | {type(exc).__name__}")
            failed += 1
            continue
        if code in (401, 403):
            verdict = "PASS"
            passed += 1
        elif code in (404, 422):
            verdict = "INCONCLUSIVE"
            inconclusive += 1
        else:
            verdict = "CHECK"
            failed += 1
        print(f"[{verdict}] {role:10s} {method:4s} {path} | HTTP {code}")
    print(f"\nSUMMARY: {passed} PASS / {failed} CHECK / {inconclusive} INCONCLUSIVE")
    print("Scope: denied access only; valid permitted-role writes and upload need isolated test data.")
    check_db()
    if failed:
        print("[ATTENTION] Some outcomes need review before continuing.")
    else:
        print("[DONE] Safe negative checks finished; do not label write RBAC fully passed yet.")


if __name__ == "__main__":
    main()
