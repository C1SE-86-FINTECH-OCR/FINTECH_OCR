# Profile fields migration

Run from `backend/` with the existing `.env` database configuration:

```powershell
.\.venv\Scripts\python.exe .\migrations\profile_v1.py
```

The migration adds nullable phone, team, employee code, and avatar fields to
`users`. It is additive and idempotent; it does not alter existing values or
require a database reset. Avatar bytes are stored in the database so the existing
`UPLOAD_DIR` configuration remains unchanged. PostgreSQL and SQLite are supported.
