"""Additive profile fields migration. Run from backend with its configured DATABASE_URL."""
from pathlib import Path
import sys
from sqlalchemy import inspect, text
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core import engine

COLUMNS = {
    "phone": "VARCHAR(30)",
    "team": "VARCHAR(120)",
    "employee_code": "VARCHAR(40)",
    "avatar_data": "BYTEA" if engine.dialect.name == "postgresql" else "BLOB",
    "avatar_mime": "VARCHAR(30)",
}

if engine.dialect.name not in ("postgresql", "sqlite"):
    raise SystemExit(f"Unsupported database dialect: {engine.dialect.name}")

with engine.begin() as connection:
    existing = {column["name"] for column in inspect(connection).get_columns("users")}
    for name, sql_type in COLUMNS.items():
        if name not in existing:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {name} {sql_type} NULL"))
            print(f"Added users.{name}")
        else:
            print(f"users.{name} already exists")
print("Profile migration complete. Existing user rows and data were preserved.")
