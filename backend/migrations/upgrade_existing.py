"""Explicit additive migrations for existing application databases.

Run from backend with the intended DATABASE_URL. Never runs test-only Phase 2.
"""
import argparse

from sqlalchemy import inspect

from migrations.profile_v1 import upgrade as upgrade_profile
from migrations.report_history_v1 import upgrade as upgrade_report_history
from migrations.schedule_notes_v1 import upgrade as upgrade_schedule_notes
from migrations.schedule_compat_v1 import upgrade as upgrade_schedule_compat


def upgrade(connection):
    missing = {"users", "reports", "schedules"} - set(inspect(connection).get_table_names())
    if missing:
        raise RuntimeError("Existing base schema required; missing tables: " + ", ".join(sorted(missing)))

    from app.models import DirectMessage, InvoiceMessage

    results = {
        "profile": upgrade_profile(connection),
        "report_history": upgrade_report_history(connection),
        "schedule_notes": upgrade_schedule_notes(connection),
        "schedule_compat": upgrade_schedule_compat(connection),
    }
    for model in (InvoiceMessage, DirectMessage):
        table = model.__table__
        existed = inspect(connection).has_table(table.name)
        table.create(connection, checkfirst=True)
        results[table.name] = "already current" if existed else "created"
    return results


def main():
    from app.core import engine

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Explicitly apply to the displayed configured database")
    args = parser.parse_args()
    print("Target database:", engine.url.render_as_string(hide_password=True))
    if not args.apply:
        print("No changes made. Verify the target, back it up, then rerun with --apply.")
        return
    with engine.begin() as connection:
        results = upgrade(connection)
    for name, result in results.items():
        print(f"{name}: {result or 'already current'}")


if __name__ == "__main__":
    main()
