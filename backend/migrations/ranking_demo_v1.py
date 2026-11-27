"""Label legacy schedules that match the original demo generator."""
from datetime import timedelta

from sqlalchemy import inspect, select

from app.models import AuditLog, Schedule, User
from app.seed import ACCOUNTANT_DEMO_TRIPS, EMPLOYEE_DEMO_EMAILS, EMPLOYEE_DEMO_TRIPS


def upgrade(connection):
    if not inspect(connection).has_table('audit_logs'):
        return 'audit log unavailable'
    schedule = Schedule.__table__
    user = User.__table__
    creator = user.alias('creator')
    audit = AuditLog.__table__
    known_audit = select(audit.c.id).where(
        audit.c.entity_type == 'schedule', audit.c.entity_id == schedule.c.id,
        audit.c.action.in_(('schedule.created', 'schedule.demo_seeded')),
    ).exists()
    candidates = connection.execute(select(
        schedule.c.id, schedule.c.title, schedule.c.destination, schedule.c.status,
        schedule.c.starts_at, schedule.c.ends_at, schedule.c.completed_at,
        schedule.c.created_at, schedule.c.created_by, user.c.email, creator.c.email.label('creator_email'),
    ).select_from(schedule.join(user, schedule.c.assigned_to == user.c.id)
                  .join(creator, schedule.c.created_by == creator.c.id))
        .where(user.c.email.in_((*EMPLOYEE_DEMO_EMAILS, 'accountant@fintech.local')), ~known_audit))
    markers = []
    for row in candidates:
        if row.email == 'accountant@fintech.local':
            matches = row.creator_email == 'admin@fintech.local' and any(
                (row.title, row.destination, row.status) == (title, destination, status)
                and row.starts_at.replace(tzinfo=None) == start.replace(tzinfo=None)
                and row.ends_at.replace(tzinfo=None) == end.replace(tzinfo=None)
                and row.completed_at is None
                for title, destination, start, end, status in ACCOUNTANT_DEMO_TRIPS
            )
        else:
            employee = EMPLOYEE_DEMO_EMAILS.index(row.email)
            matches = False
            for index, trip in enumerate(EMPLOYEE_DEMO_TRIPS):
                base = row.starts_at - timedelta(days=index * 6)
                completed = index <= employee
                if ((row.title, row.destination) == trip and row.creator_email == 'accountant@fintech.local'
                        and row.created_at is not None and timedelta() <= row.created_at - base < timedelta(seconds=1)
                        and row.ends_at == row.starts_at + timedelta(hours=4)
                        and row.status == ('completed' if completed else 'planned')
                        and row.completed_at == (base if completed else None)):
                    matches = True
                    break
        if matches:
            markers.append(dict(actor_id=row.created_by, entity_type='schedule', entity_id=row.id,
                                action='schedule.demo_seeded'))
    if markers:
        connection.execute(audit.insert(), markers)
    return 'ready'
