"""Approval deadlines are internal service targets, never approval decisions."""
import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, select, text, func
from sqlalchemy.orm import Mapped, mapped_column
from .core import Base, SessionLocal, current_user, db_session, require_roles
from .models import Invoice, InvoiceFile, InvoiceApproval, Notification, User

TZ = ZoneInfo('Asia/Ho_Chi_Minh')
logger = logging.getLogger(__name__)
router = APIRouter(prefix='/api/v1/approval-sla', tags=['Approval SLA'])

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def working(day, holidays):
    return day.weekday() < 5 and day.isoformat() not in holidays

def deadline(start, days, holidays):
    local = utc(start).astimezone(TZ)
    left = days
    while left:
        local += timedelta(days=1)
        if working(local.date(), holidays): left -= 1
    return local.astimezone(timezone.utc)

def working_seconds(start, end, holidays):
    start, end = utc(start).astimezone(TZ), utc(end).astimezone(TZ)
    if end < start: return -working_seconds(end, start, holidays)
    total = 0
    cursor = start
    while cursor < end:
        boundary = min(datetime.combine(cursor.date()+timedelta(days=1), datetime.min.time(), TZ), end)
        if working(cursor.date(), holidays): total += (boundary-cursor).total_seconds()
        cursor = boundary
    return total

class SLAPolicy(Base):
    __tablename__ = 'approval_sla_policies'
    id: Mapped[int] = mapped_column(primary_key=True)
    days: Mapped[int] = mapped_column(Integer)
    holidays: Mapped[list] = mapped_column(JSON, default=list)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc))

class SLACycle(Base):
    __tablename__ = 'approval_sla_cycles'
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'), index=True)
    submission_id: Mapped[int] = mapped_column(ForeignKey('invoice_approvals.id'), unique=True)
    policy_id: Mapped[int | None] = mapped_column(ForeignKey('approval_sla_policies.id'))
    days: Mapped[int] = mapped_column(Integer)
    holidays: Mapped[list] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome: Mapped[str | None] = mapped_column(String(20))

class SLANotice(Base):
    __tablename__ = 'approval_sla_notices'
    __table_args__ = (UniqueConstraint('cycle_id', 'user_id', 'kind'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cycle_id: Mapped[int] = mapped_column(ForeignKey('approval_sla_cycles.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(20))
    notification_id: Mapped[int] = mapped_column(ForeignKey('notifications.id'))

def lock(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(820261128)'))

def current_policy(db):
    return db.scalar(select(SLAPolicy).order_by(SLAPolicy.id.desc()).limit(1))

def start_cycle(db, submission):
    lock(db)
    existing = db.scalar(select(SLACycle).where(SLACycle.submission_id==submission.id))
    if existing: return existing
    policy = current_policy(db)
    days, holidays = (policy.days, list(policy.holidays)) if policy else (3, [])
    cycle = SLACycle(invoice_id=submission.invoice_id, submission_id=submission.id,
                     policy_id=policy.id if policy else None, days=days, holidays=holidays,
                     submitted_at=submission.created_at, due_at=deadline(submission.created_at, days, holidays))
    db.add(cycle); db.flush()
    return cycle

def finish_cycle(db, invoice_id, outcome, at):
    lock(db)
    cycle = db.scalar(select(SLACycle).where(SLACycle.invoice_id==invoice_id).order_by(SLACycle.id.desc()).limit(1))
    if cycle and cycle.processed_at is None:
        cycle.processed_at, cycle.outcome = at, outcome

def serialize(cycle, now=None, invoice_status=None):
    now = utc(now or datetime.now(timezone.utc))
    stop = utc(cycle.processed_at) if cycle.processed_at else now
    due, start = utc(cycle.due_at), utc(cycle.submitted_at)
    remaining = working_seconds(stop, due, cycle.holidays)
    overdue = max(0, (stop-due).total_seconds())
    status = cycle.outcome or ('overdue' if stop>due else 'due_soon' if remaining<=86400 else 'in_time')
    duration = max(1, working_seconds(start, due, cycle.holidays))
    unknown = not cycle.processed_at and invoice_status is not None and invoice_status != 'pending'
    return {'id':cycle.id, 'invoice_id':cycle.invoice_id, 'status':'unknown' if unknown else status,
            'submitted_at':start.isoformat(), 'due_at':due.isoformat(),
            'processed_at':utc(cycle.processed_at).isoformat() if cycle.processed_at else None,
            'working_days':cycle.days, 'policy_id':cycle.policy_id, 'timezone':'Asia/Ho_Chi_Minh',
            'remaining_working_seconds':None if unknown else max(0, remaining), 'overdue_seconds':None if unknown else overdue,
            'processing_working_seconds':max(0, working_seconds(start,stop,cycle.holidays)),
            'progress':round(min(100,max(0,100*(1-remaining/duration))),1),
            'on_time':stop<=due if cycle.processed_at else None,
            'outcome':cycle.outcome}

def latest(db, invoice_id, invoice_status=None):
    cycle = db.scalar(select(SLACycle).where(SLACycle.invoice_id==invoice_id).order_by(SLACycle.submitted_at.desc(), SLACycle.id.desc()).limit(1))
    return serialize(cycle, invoice_status=invoice_status) if cycle else None

def synchronize(db, now=None):
    """Recover only from recorded submission events; never infer from upload time."""
    lock(db)
    known = set(db.scalars(select(SLACycle.submission_id)))
    events = db.scalars(select(InvoiceApproval).order_by(InvoiceApproval.invoice_id, InvoiceApproval.created_at, InvoiceApproval.id)).all()
    active = {}
    for event in events:
        if event.action == 'submitted':
            if event.id not in known:
                # Legacy cycles predate SLA configuration. Preserve the internal
                # default explicitly, rather than applying today's changed policy.
                cycle = SLACycle(invoice_id=event.invoice_id, submission_id=event.id, days=3, holidays=[],
                                 submitted_at=event.created_at, due_at=deadline(event.created_at,3,[]))
                db.add(cycle);db.flush();known.add(event.id)
            else: cycle = db.scalar(select(SLACycle).where(SLACycle.submission_id==event.id))
            active[event.invoice_id] = cycle
        elif event.action in ('approved','rejected') and event.invoice_id in active:
            cycle = active.pop(event.invoice_id)
            if not cycle.processed_at: cycle.processed_at, cycle.outcome = event.created_at, event.action
    pending = db.execute(select(SLACycle,Invoice).join(Invoice,Invoice.id==SLACycle.invoice_id).where(SLACycle.processed_at.is_(None),Invoice.approval_status=='pending')).all()
    recipients = db.scalars(select(User).where(User.status=='active',User.role.in_(['accountant','admin']))).all()
    for cycle,invoice in pending:
        # Do not notify obsolete cycles if imported history has repeated submits.
        if active.get(invoice.id) is not cycle: continue
        status = serialize(cycle, now)['status']
        if status not in ('due_soon','overdue'): continue
        for user in recipients:
            if user.role=='admin' and status!='overdue': continue
            exists = db.scalar(select(SLANotice.id).where(SLANotice.cycle_id==cycle.id,SLANotice.user_id==user.id,SLANotice.kind==status))
            if exists: continue
            note = Notification(user_id=user.id, invoice_id=invoice.id,
                title='Hóa đơn quá hạn phê duyệt' if status=='overdue' else 'Hóa đơn sắp đến hạn phê duyệt',
                message=f'Hóa đơn #{invoice.id} · Hạn {utc(cycle.due_at).astimezone(TZ).strftime("%d/%m/%Y %H:%M")} (giờ Việt Nam).')
            db.add(note); db.flush()
            db.add(SLANotice(cycle_id=cycle.id,user_id=user.id,kind=status,notification_id=note.id))

def sweep():
    with SessionLocal() as db:
        synchronize(db)
        db.commit()

async def worker():
    while True:
        try: await asyncio.to_thread(sweep)
        except Exception:
            logger.exception('Approval SLA scheduler failed')
        await asyncio.sleep(60)

class PolicyInput(BaseModel):
    days: int = Field(default=3, ge=1, le=90)
    holidays: list[date] = Field(default_factory=list, max_length=1000)
    version: int | None = None

@router.get('/policy')
def policy(db=Depends(db_session), user=Depends(require_roles('admin'))):
    rows=db.scalars(select(SLAPolicy).order_by(SLAPolicy.id.desc())).all()
    history=[{'id':p.id,'days':p.days,'holidays':p.holidays,'actor_id':p.actor_id,'created_at':utc(p.created_at).isoformat()} for p in rows]
    return {'days':rows[0].days if rows else 3,'holidays':rows[0].holidays if rows else [],'version':rows[0].id if rows else None,'history':history,'timezone':'Asia/Ho_Chi_Minh'}

@router.put('/policy')
def update_policy(body:PolicyInput, db=Depends(db_session), user=Depends(require_roles('admin'))):
    lock(db);previous=current_policy(db)
    if body.version != (previous.id if previous else None):
        raise HTTPException(409,'Quy định đã thay đổi. Vui lòng tải lại trước khi lưu.')
    db.add(SLAPolicy(days=body.days,holidays=sorted({d.isoformat() for d in body.holidays}),actor_id=user.id))
    db.commit();return policy(db,user)

@router.get('/summary')
def summary(db=Depends(db_session), user=Depends(current_user)):
    query=select(SLACycle,Invoice.approval_status).join(Invoice,Invoice.id==SLACycle.invoice_id).join(InvoiceFile,InvoiceFile.id==Invoice.file_id)
    if user.role=='employee': query=query.where(InvoiceFile.uploaded_by==user.id)
    rows=db.execute(query.order_by(SLACycle.submitted_at,SLACycle.id)).all()
    cycles=[c for c,state in rows]
    latest_rows={c.invoice_id:(c,state) for c,state in rows}
    invoices={str(k):serialize(c,invoice_status=state) for k,(c,state) in latest_rows.items()}
    pending=[v for v in invoices.values() if v['status'] in ('in_time','due_soon','overdue')]
    closed=[serialize(c) for c in cycles if c.processed_at]
    on_time=sum(c['on_time'] for c in closed)
    pending_query=select(func.count(Invoice.id)).join(InvoiceFile,InvoiceFile.id==Invoice.file_id).where(Invoice.approval_status=='pending')
    if user.role=='employee': pending_query=pending_query.where(InvoiceFile.uploaded_by==user.id)
    pending_total=db.scalar(pending_query)
    return {'invoices':invoices,'counts':{s:sum(v['status']==s for v in pending) for s in ('in_time','due_soon','overdue')},
            'pending':pending_total,'untracked_pending':max(0,pending_total-len(pending)),'completed':len(closed),'on_time':on_time,'late':len(closed)-on_time,
            'on_time_percent':round(on_time*100/len(closed),1) if closed else None,
            'average_working_hours':round(sum(c['processing_working_seconds'] for c in closed)/3600/len(closed),1) if closed else None,
            'history':[serialize(c) for c in cycles], 'as_of':datetime.now(timezone.utc).isoformat()}
