# Phase 2 PostgreSQL schema expansion

`apply_phase2_test_migration.py` is an explicitly invoked, versioned expansion
migration. It refuses to run unless `APP_ENV=testing` and the active database is
exactly `fintech_ocr_rbac_test`. It is additive: legacy columns remain in place,
and no table or user data is deleted. The migration is transactional and records
its version in `phase2_schema_migrations`.

From `backend/`, set process-local environment values in PowerShell; do not edit
`.env`:

```powershell
$env:APP_ENV = 'testing'
$line = Get-Content .env | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -Last 1
$env:DATABASE_URL = $line.Substring('DATABASE_URL='.Length) -replace '(?<=/)fintech_ocr(?=([?#]|$))', 'fintech_ocr_rbac_test'
.\.venv\Scripts\python.exe .\apply_phase2_test_migration.py
```

The expansion adds invoice `submitted_at/source_type`, original-file
`storage_url`, invoice-item timestamps and financial/line constraints, tax
lookup JSON snapshots and `notes`, notification `type/read_at`, status checks,
and indexes. Existing lookup snapshots are reconstructed from the invoice state
at lookup time by reversing later recorded corrections. Historical notification
read timestamps were never stored, so `read_at` remains NULL for those rows.

Schedule date migration `20261107_phase2_schedule_dates_v1` is applied only to
`fintech_ocr_rbac_test`. It preserves `starts_at/ends_at`, adds required
`start_date/end_date DATE` projections and `created_at/updated_at`, backfills
existing rows, validates `end_date >= start_date`, and adds the Database Design
indexes. Date projections use PostgreSQL's timestamp-to-date cast in the session
timezone; the verified test DB session timezone was `Etc/UTC`. The versioned
runner detects repeat application and changes no schedule data on rerun. Never
run this test-only migration against `fintech_ocr`.
