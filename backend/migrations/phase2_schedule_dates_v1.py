"""Add date projections alongside existing schedule timestamps."""
from sqlalchemy import text

VERSION = "20261107_phase2_schedule_dates_v1"
REQUIRED_DATABASE = "fintech_ocr_rbac_test"


def upgrade(connection) -> int:
    database = connection.execute(text("SELECT current_database()")).scalar_one()
    if database != REQUIRED_DATABASE:
        raise RuntimeError(f"Migration blocked: expected {REQUIRED_DATABASE}, got {database}")
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS phase2_schema_migrations (
            version varchar(80) PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now(),
            description text NOT NULL
        )
    """))
    connection.execute(text("SELECT pg_advisory_xact_lock(hashtext('fintech_ocr_phase2_migrations'))"))
    if connection.execute(text(
        "SELECT 1 FROM phase2_schema_migrations WHERE version=:version"),
        {"version": VERSION},
    ).scalar_one_or_none():
        return 0

    connection.exec_driver_sql("ALTER TABLE schedules ADD COLUMN IF NOT EXISTS start_date date")
    connection.exec_driver_sql("ALTER TABLE schedules ADD COLUMN IF NOT EXISTS end_date date")
    connection.exec_driver_sql("ALTER TABLE schedules ADD COLUMN IF NOT EXISTS created_at timestamptz")
    connection.exec_driver_sql("ALTER TABLE schedules ADD COLUMN IF NOT EXISTS updated_at timestamptz")
    connection.exec_driver_sql("""
        UPDATE schedules
        SET start_date = COALESCE(start_date, starts_at::date),
            end_date = COALESCE(end_date, ends_at::date),
            created_at = COALESCE(created_at, now()),
            updated_at = COALESCE(updated_at, created_at, now())
    """)
    invalid = connection.execute(text(
        "SELECT count(*) FROM schedules WHERE end_date < start_date"
    )).scalar_one()
    if invalid:
        raise RuntimeError(f"Schedule date projection precondition failed: {invalid} invalid ranges")
    connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN start_date SET NOT NULL")
    connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN end_date SET NOT NULL")
    connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN created_at SET DEFAULT now()")
    connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN created_at SET NOT NULL")
    connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN updated_at SET DEFAULT now()")
    connection.exec_driver_sql("ALTER TABLE schedules ALTER COLUMN updated_at SET NOT NULL")
    connection.exec_driver_sql("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_schedules_date_range') THEN
            ALTER TABLE schedules ADD CONSTRAINT ck_schedules_date_range CHECK (end_date >= start_date);
          END IF;
        END $$
    """)
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_schedules_assigned_to_start_date ON schedules(assigned_to,start_date)")
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_schedules_status_completed_assigned ON schedules(status,completed_at,assigned_to)")
    connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_schedules_created_by ON schedules(created_by)")
    connection.execute(text(
        "INSERT INTO phase2_schema_migrations(version,description) VALUES (:version,:description)"
    ), {"version": VERSION, "description": "Add Database Design schedule dates while preserving timestamp fields"})
    return connection.execute(text("SELECT count(*) FROM schedules")).scalar_one()
