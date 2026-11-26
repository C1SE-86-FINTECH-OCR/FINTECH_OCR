# FINTECH OCR

**Internal Expense Invoice Digitization and Extraction System**

Capstone Project 1 (CMU-SE 450) · Team **C1SE.86** · International School, Duy Tan University

## Overview

FINTECH OCR is a web application for managing internal expense invoices. Employees upload PDF, JPG/PNG, or XML invoices; the system extracts draft fields, performs rule-based validation, and supports review, correction, approval, tax lookup, and reporting.

> **Implementation status:** The repository contains a working development baseline, not a verified production release. The chatbot endpoint currently implements role-scoped database queries, **not Gemini/RAG**. OCR extraction is a draft that requires human review. Features described as planned in the project documents should not be assumed complete.

## User Roles

- **Admin:** user administration, oversight, audit and authorized accounting functions.
- **Accountant:** invoice review, approval/rejection, tax lookup, reporting and business-trip management.
- **Employee:** upload, review/correction, submission and permitted invoice/trip views.

## Repository Structure

```text
backend/  FastAPI application, SQLAlchemy models, OCR extraction, migrations and tests
web/      React + Vite frontend, CSS and tests
docs/     Project and contribution notes
```

## Technology

| Area | Current repository |
| --- | --- |
| Frontend | React, Vite, JavaScript, CSS |
| Backend | Python, FastAPI, SQLAlchemy |
| Authentication | JWT and role-based access control |
| OCR | Tesseract via pytesseract; PDF/XML processing |
| Database | SQLite for local development; PostgreSQL is the target DBMS in project design |
| Export | Openpyxl |

The **project specification** additionally targets PostgreSQL + pgvector, Tailwind CSS, Gemini/RAG and cloud storage. These are design targets and must be checked against actual implementation before being described as delivered.

## Local Development

### Backend

1. Install Python and Tesseract OCR.
2. Open a terminal in `backend/`.
3. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env`, configure a **unique** `JWT_SECRET`, and select a suitable database.
5. For an **existing** database, stop the API, back up the database, and follow [the migration instructions](backend/migrations/README.md). Run `python -m migrations.upgrade_existing` to check the target and `python -m migrations.upgrade_existing --apply` to apply the additive upgrades. Skip this for a new SQLite development database.
6. Start the API:
   ```bash
   uvicorn app.main:app --reload
   ```
7. Check `http://localhost:8000/health`.

> The example configuration defaults to local SQLite. PostgreSQL setup requires a separately prepared schema/migration process. Do not apply the test-only migration to the main database.

### Frontend

1. Open another terminal in `web/`.
2. Install dependencies and run Vite:
   ```bash
   npm ci
   npm run dev
   ```
3. Open `http://localhost:5173`. Use `web/.env.example` to configure `VITE_API_URL` if needed.

## Tests

From `backend/`:
```bash
pytest
```

From `web/`:
```bash
node --test tests/*.test.js
npm run build
```

These are local test commands; passing results are **not** asserted here.

## Git Workflow

- `main`: stable/release branch.
- `develop`: integration branch and current default branch.
- `feature/<name-or-task>`: individual development branches created from `develop`.
- Open a Pull Request from the feature branch to `develop`; describe actual code changes and tests, request review, and merge only after review.
- Do not push secrets, local databases, uploaded invoice files, or generated build artifacts.

## Project Plan

Project period: **03 September – 15 December 2026**. The **Project Plan v1.2** defines **four development sprints**. Sprint dates should be taken from the approved Project Plan when other documents differ.

## Team

| Name | Role |
| --- | --- |
| Tran Phuoc Nhan | Scrum Master / Project Leader |
| Tran Phuoc Hiep | Team Member |
| Tran Quang Thien | Team Member |
| Tran Quoc Huy | Team Member |

**Mentor:** MSc. Dang Ngoc Trung

## Scope

The project focuses on Vietnamese expense invoices and evaluation with simulated data. Invoice extraction and validation support human review; legal authenticity certification and payment gateway integration are not claimed as delivered features.
