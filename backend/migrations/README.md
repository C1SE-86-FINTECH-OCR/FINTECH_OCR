# Phase 2 PostgreSQL schema expansion

## One-command upgrade for existing databases

Stop the API and back up the intended database first. From `backend/`, using the configured database URL and active virtual environment:

```powershell
python -m migrations.upgrade_existing
python -m migrations.upgrade_existing --apply
```

The first command only displays the target (password masked); run the second only after checking it. The runner reuses the existing additive Profile, Report and Schedule migrations in order, then creates missing invoice/direct message tables and applies the chat history and Finance/SLA schema changes. It does not run test-only Phase 2 migrations or reset data. A pre-existing base schema is required. For a new SQLite development database, start the API as usual.

## Lịch sử AI và tạm ứng công tác phí

Chạy `python -m migrations.upgrade_existing --apply` một lần trước khi khởi động phiên bản API mới.
Migration bổ sung `conversations.updated_at` từ tin nhắn mới nhất, giữ nguyên hội thoại
và ảnh cũ, tạo chỉ mục tra cứu và bảng `chat_turns` để phát hiện gửi lại cùng yêu cầu.
Task 1 creates Finance/SLA tables and preserves existing legacy Travel tables without importing or running either Travel workflow. Task 2 must be deployed separately with its explicit legacy-data preflight. No migration runs at application startup.

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

## Xếp hạng và dữ liệu mẫu

Trình nâng cấp ghi dấu các lịch mẫu cũ khớp mẫu seed gốc trong nhật ký.
Ranking bỏ qua các lịch có dấu này. Lịch và các hồ sơ tạm ứng liên kết vẫn được lưu.
