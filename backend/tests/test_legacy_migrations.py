from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from app.models import Base, User
from migrations.profile_v1 import upgrade as upgrade_profile
from migrations.report_history_v1 import upgrade as upgrade_report_history
from migrations.schedule_compat_v1 import upgrade as upgrade_schedule_compat
from migrations.schedule_notes_v1 import upgrade as upgrade_schedule_notes


def test_profile_migration_repairs_legacy_auth_columns_and_is_repeatable():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                full_name VARCHAR(150) NOT NULL,
                email VARCHAR(255) NOT NULL,
                password_hash TEXT NOT NULL,
                role VARCHAR(20) NOT NULL
            )
        """))
        connection.execute(text("INSERT INTO users VALUES (1, 'Kế toán', 'legacy@example.test', 'hash', 'accountant')"))
        added = upgrade_profile(connection)
        assert "last_login_at" in added
        assert "avatar_data" in added
        assert upgrade_profile(connection) == []
        columns = {column["name"] for column in inspect(connection).get_columns("users")}
        assert {column.name for column in User.__table__.columns} <= columns
        row = connection.execute(text("SELECT full_name, email, password_hash, status FROM users WHERE id=1")).one()
        assert row == ("Kế toán", "legacy@example.test", "hash", "active")
    with Session(engine) as session:
        legacy_user = session.get(User, 1)
        assert legacy_user.email == "legacy@example.test"
        assert legacy_user.last_login_at is None
    engine.dispose()


def test_profile_migration_is_noop_for_current_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        assert upgrade_profile(connection) == []
    engine.dispose()


def test_report_history_migration_preserves_rows_and_is_repeatable():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE reports (id INTEGER PRIMARY KEY, requested_by INTEGER NOT NULL, filters JSON NOT NULL, created_at DATETIME)"))
        connection.execute(text("INSERT INTO reports VALUES (1, 7, '{}', '2026-01-01')"))
        assert upgrade_report_history(connection)
        assert upgrade_report_history(connection) == []
        assert connection.execute(text("SELECT id, requested_by FROM reports")).one() == (1, 7)
    engine.dispose()


def test_schedule_notes_migration_preserves_rows_and_is_repeatable():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE schedules (id INTEGER PRIMARY KEY, title TEXT NOT NULL)"))
        connection.execute(text("INSERT INTO schedules VALUES (1, 'Lịch cũ')"))
        assert upgrade_schedule_notes(connection)
        assert not upgrade_schedule_notes(connection)
        assert connection.execute(text("SELECT id, title, notes FROM schedules")).one() == (1, "Lịch cũ", None)
    engine.dispose()


def test_schedule_compat_migration_preserves_timestamps_and_projects_vietnam_dates():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE schedules (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL
            )
        """))
        connection.execute(text("INSERT INTO schedules VALUES (1, 'Lịch cũ', '2026-10-31T18:00:00+00:00', '2026-10-31T20:00:00+00:00')"))
        assert set(upgrade_schedule_compat(connection)) == {"start_date", "end_date", "created_at", "updated_at"}
        assert upgrade_schedule_compat(connection) == []
        row = connection.execute(text("SELECT starts_at, ends_at, start_date, end_date, created_at, updated_at FROM schedules WHERE id=1")).one()
        assert row[:2] == ("2026-10-31T18:00:00+00:00", "2026-10-31T20:00:00+00:00")
        assert row[2:4] == ("2026-11-01", "2026-11-01")
        assert row[4] and row[5]
    engine.dispose()


def test_all_profile_report_and_schedule_migrations_are_noop_on_new_database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        assert upgrade_profile(connection) == []
        assert upgrade_report_history(connection) == []
        assert upgrade_schedule_notes(connection) is False
        assert upgrade_schedule_compat(connection) == []
    engine.dispose()


def test_existing_upgrade_is_repeatable_on_current_schema():
    from migrations.upgrade_existing import upgrade
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        first = upgrade(connection)
        second = upgrade(connection)
        assert first == second
        assert first["profile"] == []
        assert first["schedule_compat"] == []
    engine.dispose()


def test_existing_upgrade_rejects_missing_base_schema():
    import pytest
    from migrations.upgrade_existing import upgrade
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as connection:
        with pytest.raises(RuntimeError, match="missing tables"):
            upgrade(connection)
        assert inspect(connection).get_table_names() == []
    engine.dispose()
