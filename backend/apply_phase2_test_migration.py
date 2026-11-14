"""Apply the additive Phase 2 expansion to the isolated PostgreSQL test DB only."""
from __future__ import annotations

from app.core import engine, settings
from migrations.phase2_expand_v1 import REQUIRED_DATABASE, VERSION, upgrade
from migrations.phase2_schedule_dates_v1 import upgrade as upgrade_schedule_dates
from sqlalchemy.engine import make_url


def main() -> None:
    url = make_url(settings.database_url)
    if url.get_backend_name() != "postgresql" or url.database != REQUIRED_DATABASE:
        raise SystemExit(f"Refusing migration: DATABASE_URL must target {REQUIRED_DATABASE}")
    if settings.app_env != "testing":
        raise SystemExit("Refusing migration: set APP_ENV=testing for the isolated database")
    with engine.begin() as connection:
        snapshots = upgrade(connection)
        schedule_dates = upgrade_schedule_dates(connection)
    print(f"Migration {VERSION} applied/verified on {REQUIRED_DATABASE}; lookup snapshots reconstructed: {snapshots}")
    print(f"Schedule date projection applied/verified; schedules backfilled: {schedule_dates}")


if __name__ == "__main__":
    main()
