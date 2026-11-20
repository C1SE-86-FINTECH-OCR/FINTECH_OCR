"""Add optional schedule notes without altering existing trip records."""
from sqlalchemy import inspect, text


def upgrade(connection):
    if "schedules" not in inspect(connection).get_table_names():
        raise RuntimeError("The schedules table must exist before applying this migration")
    columns = {item["name"] for item in inspect(connection).get_columns("schedules")}
    if "notes" in columns:
        return False
    connection.execute(text("ALTER TABLE schedules ADD COLUMN notes TEXT"))
    return True


if __name__ == "__main__":
    try:
        from app.core import engine
    except ImportError:
        from backend.app.core import engine

    with engine.begin() as connection:
        added = upgrade(connection)
    print("Schedule notes column: " + ("added" if added else "already present"))
