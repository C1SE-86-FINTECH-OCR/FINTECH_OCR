# Phase 2 PostgreSQL schema expansion

## Existing Profile, Report, and Schedule databases

Run the additive migrations from `backend/` against the intended database URL
already configured for the process. Run them before starting the application
with an existing database so mapped columns exist before login and API queries.
Run them in this order:

1. `profile_v1.py` adds Profile fields and account columns used by login and
   user serialization, including `last_login_at`.
2. `report_history_v1.py` adds metadata and the stored workbook artifact to the
   existing `reports` table.
3. `schedule_notes_v1.py` adds the optional Schedule notes column.
4. `schedule_compat_v1.py` adds the date projections and timestamps required
   by the Schedule API, deriving dates in `Asia/Ho_Chi_Minh` while preserving
   the original `starts_at`/`ends_at` values.

```powershell
.\.venv\Scripts\python.exe .\migrations\profile_v1.py
.\.venv\Scripts\python.exe -m migrations.report_history_v1
.\.venv\Scripts\python.exe -m migrations.schedule_notes_v1
.\.venv\Scripts\python.exe -m migrations.schedule_compat_v1
```

These migrations are additive, preserve existing rows, and can be rerun. Check
that the process `DATABASE_URL` targets the intended database before running
them. No database reset is required. The versioned `phase2` migrations below
retain their explicit test-database guard and are not part of this sequence.

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

## Report export history

`report_history_v1.py` additively adds nullable export metadata and the stored
`.xlsx` artifact to the existing `reports` table. It does not delete or rewrite
existing report rows and is safe to run repeatedly. Set the intended
`DATABASE_URL`/`APP_ENV` in the backend environment, then run from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m migrations.report_history_v1
```

The app's SQLite development startup creates these columns for a new database,
but existing PostgreSQL/SQLite databases require this explicit migration.

## Schedule notes

`schedule_notes_v1.py` adds an optional `notes` field to existing schedules.
The additive change preserves all existing trips and can be run repeatedly:

```powershell
.\.venv\Scripts\python.exe -m migrations.schedule_notes_v1
```
