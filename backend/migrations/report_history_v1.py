"""Add durable report export artifacts and metadata without changing existing rows."""
from sqlalchemy import inspect, text

VERSION = "20261119_report_history_v1"


def upgrade(connection):
    inspector = inspect(connection)
    if "reports" not in inspector.get_table_names():
        raise RuntimeError("The reports table must exist before applying this migration")
    existing = {column["name"] for column in inspector.get_columns("reports")}
    additions = {
        "filename": "VARCHAR(255)",
        "row_count": "INTEGER",
        "total_amount": "NUMERIC(18, 2)",
        "status": "VARCHAR(20) NOT NULL DEFAULT 'completed'",
        "artifact_data": "BLOB" if connection.dialect.name == "sqlite" else "BYTEA",
    }
    for name, sql_type in additions.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE reports ADD COLUMN {name} {sql_type}"))
    return sorted(set(additions) - existing)


if __name__ == "__main__":
    try:
        from app.core import engine
    except ImportError:
        from backend.app.core import engine

    with engine.begin() as connection:
        added = upgrade(connection)
    print("Added report columns: " + (", ".join(added) if added else "none (already current)"))
