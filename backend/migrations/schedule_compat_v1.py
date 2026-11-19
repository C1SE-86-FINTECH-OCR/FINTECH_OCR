"""Add legacy Schedule projection fields without replacing stored timestamps."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, text

VIETNAM_ZONE = ZoneInfo("Asia/Ho_Chi_Minh")


def _datetime_value(value):
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VIETNAM_ZONE)
    return parsed


def upgrade(connection):
    dialect = connection.dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    if "schedules" not in inspect(connection).get_table_names():
        raise RuntimeError("The schedules table must exist before applying the Schedule compatibility migration")

    existing = {column["name"] for column in inspect(connection).get_columns("schedules")}
    if not {"id", "starts_at", "ends_at"} <= existing:
        raise RuntimeError("Legacy schedules must contain id, starts_at, and ends_at")
    timestamp_type = "TIMESTAMPTZ" if dialect == "postgresql" else "DATETIME"
    additions = {
        "start_date": "DATE",
        "end_date": "DATE",
        "created_at": timestamp_type,
        "updated_at": timestamp_type,
    }
    added = []
    for name, sql_type in additions.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE schedules ADD COLUMN {name} {sql_type} NULL"))
            added.append(name)

    rows = connection.execute(text(
        "SELECT id, starts_at, ends_at, start_date, end_date, created_at, updated_at FROM schedules"
    )).mappings().all()
    for row in rows:
        starts = _datetime_value(row["starts_at"])
        ends = _datetime_value(row["ends_at"])
        if ends <= starts:
            raise RuntimeError(f"Schedule {row['id']} has an end timestamp before its start timestamp")
        created = row["created_at"] or datetime.now(timezone.utc)
        updated = row["updated_at"] or created
        connection.execute(text("""
            UPDATE schedules
            SET start_date = COALESCE(start_date, :start_date),
                end_date = COALESCE(end_date, :end_date),
                created_at = COALESCE(created_at, :created_at),
                updated_at = COALESCE(updated_at, :updated_at)
            WHERE id = :id
        """), {
            "id": row["id"],
            "start_date": starts.astimezone(VIETNAM_ZONE).date().isoformat(),
            "end_date": ends.astimezone(VIETNAM_ZONE).date().isoformat(),
            "created_at": created.isoformat() if isinstance(created, datetime) else created,
            "updated_at": updated.isoformat() if isinstance(updated, datetime) else updated,
        })
    return added


if __name__ == "__main__":
    try:
        from app.core import engine
    except ImportError:
        from backend.app.core import engine

    with engine.begin() as connection:
        added = upgrade(connection)
    print("Schedule compatibility columns added: " + (", ".join(added) if added else "none (already current)"))
