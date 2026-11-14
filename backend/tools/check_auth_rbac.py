#!/usr/bin/env python3
"""FINTECH OCR - safe authentication/RBAC smoke check over HTTP.

This script calls login and GET endpoints only (plus one deliberately invalid
login). It does not create, update, delete, upload, approve, or export to disk.
Login may update users.last_login_at as normal application behavior.

Python 3.10+ / standard library only.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass
class Response:
    status: int
    data: object | None = None
    error: str = ""


def call(base: str, method: str, path: str, token: str | None = None,
         body: object | None = None, timeout: float = 10.0) -> Response:
    headers = {"Accept": "application/json"}
    payload = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(base + path, data=payload, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as reply:
            status = reply.status
            content = reply.read(4 * 1024 * 1024)
    except HTTPError as ex:
        status = ex.code
        content = ex.read(65536)
    except (URLError, TimeoutError, OSError) as ex:
        return Response(status=0, error=str(getattr(ex, "reason", ex)))
    try:
        result = json.loads(content)
    except (ValueError, UnicodeDecodeError):
        result = None
    return Response(status=status, data=result)


class Results:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def check(self, title: str, condition: bool, detail: str = ""):
        if condition:
            self.passed += 1
            print(f"[PASS] {title}")
        else:
            self.failed += 1
            print(f"[FAIL] {title}" + (f" | {detail}" if detail else ""))

    def status(self, title: str, got: Response, expected: int):
        self.check(title, got.status == expected,
                   f"HTTP {got.status}; expected {expected}" +
                   (f"; {got.error}" if got.error else ""))

    def skip(self, title: str, reason: str):
        self.skipped += 1
        print(f"[SKIP] {title} | {reason}")


def main() -> int:
    parser = argparse.ArgumentParser(description="FINTECH OCR authentication and RBAC check (safe GETs + login)")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend URL, not the Vite web URL")
    parser.add_argument("--admin-email", default="admin@fintech.local")
    parser.add_argument("--accountant-email", default="accountant@fintech.local")
    parser.add_argument("--employee-email", default="employee@fintech.local")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    print("FINTECH OCR | AUTHENTICATION + RBAC | SAFE SMOKE CHECK")
    print("Backend:", base)
    print("No invoice/profile/schedule modifications will be submitted.")
    print("Login updates last_login_at as normal. Tokens/password will NOT be printed.\n")

    password = os.environ.get("FINTECH_TEST_PASSWORD")
    if not password:
        try:
            password = getpass.getpass("Shared demo-account password (hidden): ")
        except (EOFError, KeyboardInterrupt):
            print("[STOP] Password was not supplied.")
            return 2
    if not password:
        print("[STOP] Empty password.")
        return 2

    results = Results()
    health = call(base, "GET", "/health", timeout=args.timeout)
    results.status("Health endpoint", health, 200)
    if health.status != 200:
        print("[STOP] Start FastAPI on port 8000 first; do not change the database.")
        return 2

    for endpoint in ("/api/v1/auth/me", "/api/v1/users", "/api/v1/invoices"):
        results.status("Anonymous access blocked: " + endpoint,
                       call(base, "GET", endpoint, timeout=args.timeout), 401)

    roles = {
        "admin": args.admin_email,
        "accountant": args.accountant_email,
        "employee": args.employee_email,
    }
    tokens: dict[str, str] = {}
    identities: dict[str, dict] = {}
    for role, email in roles.items():
        response = call(base, "POST", "/api/v1/auth/login",
                        body={"email": email, "password": password}, timeout=args.timeout)
        token = response.data.get("access_token") if isinstance(response.data, dict) else None
        results.check(role + " demo login", response.status == 200 and bool(token),
                      f"HTTP {response.status}; check the demo account/password")
        if token:
            tokens[role] = str(token)
            me = call(base, "GET", "/api/v1/auth/me", token=token, timeout=args.timeout)
            info = me.data if isinstance(me.data, dict) else {}
            results.check(role + " /auth/me matches DB role",
                          me.status == 200 and info.get("role") == role and
                          str(info.get("email", "")).lower() == email.lower(),
                          f"HTTP {me.status}; returned role={info.get('role')!r}")
            identities[role] = info
        else:
            results.skip(role + " /auth/me", "login unsuccessful")
    if len(tokens) != 3:
        print("\n[STOP] Test accounts could not all sign in. No other endpoints tested.")
        return 1

    bad = call(base, "GET", "/api/v1/auth/me", token="not-a-real-jwt", timeout=args.timeout)
    results.status("Invalid JWT rejected", bad, 401)

    checks = [
        ("Admin-only users", "/api/v1/users", {"admin": 200, "accountant": 403, "employee": 403}),
        ("Employee directory", "/api/v1/directory/employees", {"admin": 200, "accountant": 200, "employee": 403}),
        ("Admin-only audit logs", "/api/v1/audit-logs", {"admin": 200, "accountant": 403, "employee": 403}),
        ("Excel export permission", "/api/v1/reports/export", {"admin": 200, "accountant": 200, "employee": 403}),
        ("Invoice list", "/api/v1/invoices", {"admin": 200, "accountant": 200, "employee": 200}),
        ("Own profile", "/api/v1/profile", {"admin": 200, "accountant": 200, "employee": 200}),
        ("Notifications", "/api/v1/notifications", {"admin": 200, "accountant": 200, "employee": 200}),
        ("Schedule list", "/api/v1/schedules", {"admin": 200, "accountant": 200, "employee": 200}),
        ("Dashboard summary", "/api/v1/dashboard/summary", {"admin": 200, "accountant": 200, "employee": 200}),
        ("Completed-trip ranking", "/api/v1/ranking", {"admin": 200, "accountant": 200, "employee": 200}),
    ]
    invoice_lists: dict[str, list] = {}
    for label, path, expected_by_role in checks:
        for role in ("admin", "accountant", "employee"):
            response = call(base, "GET", path, token=tokens[role], timeout=args.timeout)
            results.status(role + " | " + label, response, expected_by_role[role])
            if path == "/api/v1/invoices" and response.status == 200 and isinstance(response.data, list):
                invoice_lists[role] = response.data

    employee_id = identities.get("employee", {}).get("id")
    own = invoice_lists.get("employee")
    all_invoices = invoice_lists.get("admin")
    accountant_invoices = invoice_lists.get("accountant")
    if own is not None and employee_id is not None:
        results.check("Employee invoice list is owner-filtered",
                      all(isinstance(item, dict) and item.get("uploaded_by") == employee_id for item in own),
                      f"employee_id={employee_id}; visible invoices={len(own)}")
    else:
        results.skip("Employee invoice list is owner-filtered", "response missing")
    if all_invoices is not None and accountant_invoices is not None:
        results.check("Admin and Accountant can see same invoice IDs",
                      {x.get("id") for x in all_invoices} ==
                      {x.get("id") for x in accountant_invoices})
    else:
        results.skip("Admin and Accountant can see same invoice IDs", "response missing")

    foreign = next((item for item in all_invoices or []
                    if isinstance(item, dict) and item.get("uploaded_by") != employee_id), None)
    if foreign and isinstance(foreign.get("id"), int):
        foreign_id = foreign["id"]
        for path in (f"/api/v1/invoices/{foreign_id}",
                     f"/api/v1/invoices/{foreign_id}/file",
                     f"/api/v1/invoices/{foreign_id}/risk-assessment"):
            response = call(base, "GET", path, token=tokens["employee"], timeout=args.timeout)
            results.status("Employee cannot access another owner's invoice: " + path,
                           response, 404)
        results.status("Admin can access other employee's invoice",
                       call(base, "GET", f"/api/v1/invoices/{foreign_id}",
                            token=tokens["admin"], timeout=args.timeout), 200)
    else:
        results.skip("Cross-user invoice isolation", "No foreign-owned invoice found in admin list")

    print("\nSUMMARY: " + str(results.passed) + " PASS / " + str(results.failed) +
          " FAIL / " + str(results.skipped) + " SKIP")
    if results.failed:
        print("RBAC CHECK: ATTENTION REQUIRED. Do not claim RBAC complete yet.")
        return 1
    print("RBAC CHECK: READ-ENDPOINT SMOKE TEST PASSED.")
    print("Write/approval/lookup authorization is NOT tested by this script.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
