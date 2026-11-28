# Phase 2 PostgreSQL schema expansion

## One-command upgrade for existing databases

Stop the API and back up the intended database first. From `backend/`, using the configured database URL and active virtual environment:

```powershell
python -m migrations.upgrade_existing
python -m migrations.upgrade_existing --apply
```

The first command only displays the target (password masked); run the second only after checking it. The runner reuses the existing additive Profile, Report and Schedule migrations in order, then creates missing invoice/direct message tables and applies the chat history and travel advance schema changes. It does not run test-only Phase 2 migrations or reset data. A pre-existing base schema is required. For a new SQLite development database, start the API as usual.

## Lịch sử AI và tạm ứng công tác phí

Chạy `python -m migrations.upgrade_existing --apply` một lần trước khi khởi động phiên bản API mới.
Migration bổ sung `conversations.updated_at` từ tin nhắn mới nhất, giữ nguyên hội thoại
và ảnh cũ, tạo chỉ mục tra cứu và bảng `chat_turns` để phát hiện gửi lại cùng yêu cầu.
The single active Travel implementation is /travel (app.travel).
Migrations create travel_cases, travel_expenses, travel_transactions, travel_evidence,
travel_history, travel_sla_cycles and the Finance/SLA tables.
Legacy tables are never dropped. Nonempty legacy Travel stops before any changes
with LEGACY_TRAVEL_RECONCILIATION_REQUIRED: receipt confirmation and history cannot
be inferred. An approved lossless reconciliation is required before deployment.
Empty legacy travel_expenses is preserved in the travel_legacy_main PostgreSQL
schema before creating the target table. Back up and test on a restored database first.
No automatic migration is applied by application startup.

### Nonempty legacy main Travel: deployment remains blocked

`LEGACY_TRAVEL_RECONCILIATION_REQUIRED` is an intentional safety stop, not a
successful conversion. The transaction must roll back; continue running the
existing application until reconciliation is approved. Do not point the new API
at the legacy schema or manually mark the migration complete.

1. Back up and restore the intended database into an isolated PostgreSQL target.
2. Inventory every advance, expense, payment, evidence and event; retain IDs,
   actor references, timestamps, amounts (including historical fractional VND),
   invoice links and original status. No rounding or account changes are allowed.
3. An authorized operator must reconcile missing receipt confirmation, ambiguous
   rejected/cancelled states, refund evidence and conflicting invoice links.
   No status or financial movement may be inferred from the old `disbursed` flag.
4. Approve explicit old-to-new ID/state mappings and verify row coverage and
   ledger totals on the restored copy before authorizing a conversion script.
   Until that mapping exists, this release deliberately performs no conversion.
5. Preserve legacy history in an archive schema; never DROP it. Only the new
   `app.travel` workflow and its target `travel_expenses` may run after a verified
   cutover. Restoring the backup is an operator decision, never an automatic reset.

Fresh databases, existing databases already on the target schema, and empty
legacy Travel are supported by the idempotent migration. Run the isolated checker
`tools/verify_integration_postgres.py --connection-env <local-config>`, which
creates only `fintech_integration_*` databases and tests the nonempty safety stop.

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
them. No database reset is required. The retired test-only migration launcher is no longer distributed. Production upgrades use only the explicit additive migration sequence above.

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
