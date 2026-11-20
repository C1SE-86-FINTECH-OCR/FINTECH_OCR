"""Add Profile and account compatibility fields without rewriting user rows."""
from sqlalchemy import inspect, text


def upgrade(connection):
    dialect = connection.dialect.name
    if dialect not in ("postgresql", "sqlite"):
        raise RuntimeError(f"Unsupported database dialect: {dialect}")
    if "users" not in inspect(connection).get_table_names():
        raise RuntimeError("The users table must exist before applying the Profile migration")

    timestamp_type = "TIMESTAMPTZ" if dialect == "postgresql" else "DATETIME"
    binary_type = "BYTEA" if dialect == "postgresql" else "BLOB"
    additions = {
        "phone": "VARCHAR(30)",
        "team": "VARCHAR(120)",
        "employee_code": "VARCHAR(40)",
        "avatar_data": binary_type,
        "avatar_mime": "VARCHAR(30)",
        # Auth login reads and writes this field; add it for pre-Profile schemas.
        "last_login_at": timestamp_type,
        # User serialization selects every mapped column, so legacy schemas
        # also need these nullable account-management fields before login works.
        "created_by": "INTEGER",
        "created_at": timestamp_type,
        "updated_at": timestamp_type,
    }
    existing = {column["name"] for column in inspect(connection).get_columns("users")}
    added = []
    for name, sql_type in additions.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sql_type} NULL"))
            added.append(name)

    if "status" not in existing:
        connection.execute(text("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"))
        added.append("status")
    return added


if __name__ == "__main__":
    try:
        from app.core import engine
    except ImportError:
        from backend.app.core import engine

    with engine.begin() as connection:
        added = upgrade(connection)
    print("Profile/account fields added: " + (", ".join(added) if added else "none (already current)"))
