import csv
from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import PureWindowsPath
from urllib.parse import quote
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from openpyxl import Workbook
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import gemini_chat
from .core import current_user, db_session, require_roles, settings
from .models import AuditLog, Invoice, InvoiceFile, Schedule, User
from .report_workbook import NUMBER_FORMAT, append_report_row, report_sheet
from .risk_checks import assess_invoice_risks
from .travel_models import TravelAdvance, TravelAdvanceEvent, TravelExpense, TravelPayment, TravelPaymentEvidence

router = APIRouter(prefix='/api/v1/travel-advances', tags=['travel-advances'])
accountant = require_roles('accountant')
finance_read = require_roles('accountant', 'admin')
employee = require_roles('employee')
VN = ZoneInfo('Asia/Ho_Chi_Minh')
ZERO = Decimal('0.00')
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2, allow_inf_nan=False)]
PositiveMoney = Annotated[Money, Field(gt=0)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Category = Literal['allowance', 'lodging', 'tickets', 'transport', 'meals', 'other']
State = Literal['draft', 'pending', 'approved', 'disbursed', 'settlement_pending', 'checking',
                'refund_due', 'supplement_due', 'settled', 'rejected', 'cancelled']
Action = Literal['submit', 'approve', 'reject', 'cancel', 'disburse', 'request_settlement', 'review', 'settle']


class AdvanceInput(BaseModel):
    request_id: UUID
    schedule_id: Annotated[int, Field(gt=0)]
    requested: PositiveMoney
    reason: Note | None = None
    notes: Note | None = None


class ExpenseInput(BaseModel):
    invoice_id: Annotated[int, Field(gt=0)]
    category: Category
    description: Note
    incurred_on: date
    amount: PositiveMoney


class ReviewInput(BaseModel):
    accepted: Money
    reason: Note


class ActionInput(BaseModel):
    action: Action
    amount: Money | None = None
    paid_on: date | None = None
    reason: Note | None = None


class PaymentInput(BaseModel):
    kind: Literal['refund', 'supplement']
    amount: PositiveMoney
    paid_on: date
    method: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
    reference: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    evidence: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    notes: Note | None = None


def fail(detail, status=422):
    raise HTTPException(status_code=status, detail=detail)


def utc_timestamp(value):
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def vn_day(value):
    return utc_timestamp(value).astimezone(VN).date()


def may_approve(user):
    return user.role in ('admin', 'accountant') and user.id in settings.travel_advance_approver_ids


def permitted(query, user):
    if user.role == 'employee':
        return query.where(TravelAdvance.employee_id == user.id)
    if user.role not in ('accountant', 'admin'):
        fail('Bạn không có quyền truy cập hồ sơ', 403)
    return query


def advance_for(db, user, advance_id, *, lock=False):
    query = permitted(select(TravelAdvance).where(TravelAdvance.id == advance_id), user)
    advance = db.scalar(query.with_for_update() if lock else query)
    if not advance:
        fail('Không tìm thấy hồ sơ', 404)
    return advance


def fields(row, *names):
    return {name: getattr(row, name) for name in names}


def serialize_money(values):
    return {key: format(value, '.2f') for key, value in values.items()}


def balances(disbursed, accepted, refunded, supplemented, finalized):
    difference = disbursed - accepted
    refund_due = max(difference, ZERO) if finalized else ZERO
    supplement_due = max(-difference, ZERO) if finalized else ZERO
    return {
        'disbursed': disbursed, 'accepted': accepted, 'difference': difference,
        'refund_due': refund_due, 'refunded': refunded, 'refund_remaining': refund_due - refunded,
        'supplement_due': supplement_due, 'supplemented': supplemented,
        'supplement_remaining': supplement_due - supplemented,
    }


def list_rows(db, user, *, status=None, employee_id=None, schedule_id=None, period='all',
              year=None, month=None, quarter=None, date_from=None, date_to=None, unsettled_only=False, search=''):
    if period not in ('all', 'month', 'quarter', 'year', 'custom'):
        fail('Kỳ thống kê không hợp lệ')
    accepted = select(TravelExpense.advance_id.label('id'), func.sum(TravelExpense.accepted).label('amount')).where(
        TravelExpense.status == 'accepted').group_by(TravelExpense.advance_id).subquery()
    payments = select(
        TravelPayment.advance_id.label('id'),
        func.sum(TravelPayment.amount).filter(TravelPayment.kind == 'refund').label('refunded'),
        func.sum(TravelPayment.amount).filter(TravelPayment.kind == 'supplement').label('supplemented'),
    ).group_by(TravelPayment.advance_id).subquery()
    query = permitted(select(TravelAdvance, accepted.c.amount, payments.c.refunded, payments.c.supplemented)
        .outerjoin(accepted, accepted.c.id == TravelAdvance.id)
        .outerjoin(payments, payments.c.id == TravelAdvance.id), user)
    term = search.strip()
    if term:
        code = term.upper().removeprefix('TU-')
        conditions = []
        if code.isascii() and code.isdecimal() and len(code) <= 10 and int(code) <= 2147483647:
            conditions.append(TravelAdvance.id == int(code))
        if user.role != 'employee':
            conditions.append(func.lower(TravelAdvance.employee_name).contains(term.lower(), autoescape=True))
        query = query.where(or_(*conditions) if conditions else False)
    if unsettled_only:
        query = query.where(TravelAdvance.status.not_in(('settled', 'cancelled', 'rejected')))
    if status:
        query = query.where(TravelAdvance.status == status)
    if employee_id:
        query = query.where(TravelAdvance.employee_id == employee_id)
    if schedule_id:
        query = query.where(TravelAdvance.schedule_id == schedule_id)
    if period == 'custom':
        if not date_from or not date_to or date_from > date_to:
            fail('Khoảng ngày không hợp lệ')
        query = query.where(TravelAdvance.starts_on.between(date_from, date_to))
    elif period != 'all':
        today = datetime.now(VN).date()
        year = today.year if year is None else year
        if not 1 <= year <= 9999:
            fail('Năm không hợp lệ')
        query = query.where(func.extract('year', TravelAdvance.starts_on) == year)
        trip_month = func.extract('month', TravelAdvance.starts_on)
        if period == 'month':
            month = today.month if month is None else month
            if not 1 <= month <= 12:
                fail('Tháng không hợp lệ')
            query = query.where(trip_month == month)
        elif period == 'quarter':
            quarter = (today.month - 1) // 3 + 1 if quarter is None else quarter
            if not 1 <= quarter <= 4:
                fail('Quý không hợp lệ')
            start = (quarter - 1) * 3 + 1
            query = query.where(trip_month.between(start, start + 2))
    return db.execute(query.order_by(TravelAdvance.id.desc())).all()


def advance_summary(row, accepted, refunded, supplemented):
    money = balances(row.disbursed, accepted or ZERO, refunded or ZERO, supplemented or ZERO,
                     row.status in ('refund_due', 'supplement_due', 'settled'))
    return {
        **fields(row, 'id', 'employee_id', 'employee_name', 'employee_code', 'department',
                 'schedule_id', 'trip_title', 'starts_on', 'ends_on', 'reason', 'notes', 'status',
                 'disbursed_on', 'approved_by', 'disbursed_by'),
        'created_at': utc_timestamp(row.created_at),
        'code': f'TU-{row.id:06d}',
        **serialize_money({**money, 'requested': row.requested}),
        'approved': format(row.approved, '.2f') if row.approved is not None else None,
    }


def history(db, user, row):
    row = db.scalar(select(TravelAdvance).where(TravelAdvance.id == row.id)
                    .with_for_update(read=True).execution_options(populate_existing=True))
    expenses = db.execute(select(TravelExpense, Invoice).join(
        Invoice, Invoice.id == TravelExpense.invoice_id).where(
        TravelExpense.advance_id == row.id).order_by(TravelExpense.id)).all()
    payments = db.execute(select(TravelPayment, TravelPaymentEvidence.filename).outerjoin(
        TravelPaymentEvidence, TravelPaymentEvidence.payment_id == TravelPayment.id).where(
        TravelPayment.advance_id == row.id).order_by(TravelPayment.id)).all()
    events = db.execute(select(TravelAdvanceEvent, User.full_name).join(
        User, User.id == TravelAdvanceEvent.actor_id).where(
        TravelAdvanceEvent.advance_id == row.id).order_by(TravelAdvanceEvent.id)).all()
    accepted = sum((expense.accepted for expense, _ in expenses if expense.status == 'accepted'), ZERO)
    totals = {kind: sum((p.amount for p, _ in payments if p.kind == kind), ZERO) for kind in ('refund', 'supplement')}
    return {
        **advance_summary(row, accepted, totals['refund'], totals['supplement']),
        'can_approve': may_approve(user),
        'expenses': [{
            **fields(expense, 'id', 'invoice_id', 'category', 'description', 'incurred_on',
                     'status', 'review_reason', 'reviewed_by'),
            **serialize_money(fields(expense, 'amount', 'accepted')),
            'invoice': fields(invoice, 'invoice_number', 'validation_status', 'approval_status',
                              'lookup_status', 'confidence_score'),
            'risks': assess_invoice_risks(db, invoice, role=user.role)['flags'],
        } for expense, invoice in expenses],
        'payments': [{
            **fields(payment, 'id', 'kind', 'paid_on', 'method', 'reference', 'evidence',
                     'recorded_by', 'notes'),
            'created_at': utc_timestamp(payment.created_at),
            'filename': filename,
            **serialize_money(fields(payment, 'amount')),
        } for payment, filename in payments],
        'events': [{**fields(event, 'id', 'actor_id', 'action', 'details'),
                    'created_at': utc_timestamp(event.created_at), 'actor_name': name}
                   for event, name in events],
    }


def record(db, row, user, action, details=None):
    db.add(TravelAdvanceEvent(advance_id=row.id, actor_id=user.id, action=action, details=details or {}))
    db.add(AuditLog(actor_id=user.id, entity_type='travel_advance', entity_id=row.id, action='travel_advance.' + action))


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail('Dữ liệu đã được ghi nhận hoặc đã thay đổi. Hãy tải lại hồ sơ.', 409)


class Filters(BaseModel):
    status: State | None = None
    employee_id: int | None = None
    schedule_id: int | None = None
    period: str = 'all'
    year: int | None = None
    month: int | None = None
    quarter: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    unsettled_only: bool = False
    search: str = Field(default='', max_length=150)


@router.get('')
def list_advances(filters: Filters = Depends(), db: Session = Depends(db_session), user=Depends(current_user)):
    rows = list_rows(db, user, **filters.model_dump())
    items = [advance_summary(*row) for row in rows]
    keys = ('disbursed', 'accepted', 'refund_remaining', 'supplement_remaining', 'refunded', 'supplemented')
    return {
        'items': items,
        'totals': serialize_money({key: sum((Decimal(item[key]) for item in items), ZERO) for key in keys}),
        'unsettled': sum(item['status'] not in ('settled', 'cancelled', 'rejected') for item in items),
        'pending_work': sum(item['status'] in ('pending', 'approved', 'settlement_pending', 'checking',
                                               'refund_due', 'supplement_due') for item in items),
        'settled': sum(item['status'] == 'settled' for item in items),
    }


@router.get('/filter-options')
def filter_options(db: Session = Depends(db_session), user=Depends(finance_read)):
    employees = db.execute(select(User.id, User.full_name, User.employee_code).join(
        TravelAdvance, TravelAdvance.employee_id == User.id).distinct().order_by(User.full_name, User.id))
    employee_options = [{'id': key, 'name': name, 'code': code} for key, name, code in employees]
    trips = db.execute(select(Schedule.id, Schedule.title).join(
        TravelAdvance, TravelAdvance.schedule_id == Schedule.id).distinct().order_by(Schedule.title, Schedule.id))
    return {'employees': employee_options, 'trips': [{'id': key, 'name': title} for key, title in trips]}


REPORT_MONEY = ('requested', 'approved', 'disbursed', 'accepted', 'refund_due', 'refunded', 'refund_remaining',
                'supplement_due', 'supplemented', 'supplement_remaining')
REPORT_LABELS = ('Đề nghị', 'Được duyệt', 'Đã ứng', 'Chi phí hợp lệ', 'Phải hoàn', 'Đã hoàn', 'Còn phải hoàn',
                 'Phải chi thêm', 'Đã chi thêm', 'Còn phải chi thêm')


def csv_text(value):
    return "'" + value if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')) else value


def report_rows(items, group_by):
    if group_by == 'case':
        yield ('Mã', 'Nhân viên', 'Mã nhân viên', 'Phòng ban', 'Chuyến công tác', 'Bắt đầu', 'Kết thúc',
               'Trạng thái', *REPORT_LABELS)
        for item in items:
            yield tuple(item[key] for key in (
                'code', 'employee_name', 'employee_code', 'department', 'trip_title', 'starts_on', 'ends_on',
                'status', *REPORT_MONEY))
        return
    id_field, label_field = ('employee_id', 'employee_name') if group_by == 'employee' else ('schedule_id', 'trip_title')
    yield ('ID', 'Nhân viên' if group_by == 'employee' else 'Chuyến công tác', 'Số hồ sơ', *REPORT_LABELS)
    groups = {}
    for item in items:
        groups.setdefault(item[id_field], []).append(item)
    for key, group in groups.items():
        totals = [sum((Decimal(item[field] or '0.00') for item in group), ZERO) for field in REPORT_MONEY]
        yield (key, group[0][label_field], len(group), *totals)


@router.get('/report.xlsx')
def export_excel(filters: Filters = Depends(), group_by: Literal['case', 'employee', 'trip'] = 'case',
                 db: Session = Depends(db_session), user=Depends(finance_read)):
    items = (advance_summary(*row) for row in list_rows(db, user, **filters.model_dump()))
    rows = report_rows(items, group_by)
    header = next(rows)
    widths = (16, 28, 18, 22, 32, 16, 16, 21) if group_by == 'case' else (12, 32, 14)
    first_money = len(widths) + 1
    date_columns = (6, 7) if group_by == 'case' else ()
    money_columns = range(first_money, len(header) + 1)
    formats = {**dict.fromkeys(date_columns, 'dd/mm/yyyy'), **dict.fromkeys(money_columns, NUMBER_FORMAT)}
    workbook = Workbook(write_only=True)
    sheet = report_sheet(workbook, 'Tạm ứng công tác', (*widths, *([19] * len(REPORT_MONEY))), landscape=True)
    append_report_row(sheet, header, emphasis='header')
    for row in rows:
        values = [csv_text(value) for value in row[:first_money - 1]]
        values.extend(Decimal(value) if value is not None else None for value in row[first_money - 1:])
        append_report_row(sheet, values, center=date_columns, right=money_columns, formats=formats)
    output = BytesIO()
    workbook.save(output)
    return Response(output.getvalue(), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename=tam-ung-cong-tac.xlsx'})


@router.get('/report.csv')
def export_report(filters: Filters = Depends(), group_by: Literal['case', 'employee', 'trip'] = 'case',
                  db: Session = Depends(db_session), user=Depends(finance_read)):
    file = StringIO()
    writer = csv.writer(file)
    items = (advance_summary(*row) for row in list_rows(db, user, **filters.model_dump()))
    writer.writerows([csv_text(value) for value in row] for row in report_rows(items, group_by))
    return Response('\ufeff' + file.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=tam-ung-cong-tac.csv'})


@router.get('/{advance_id}')
def get_advance(advance_id: int, db: Session = Depends(db_session), user=Depends(current_user)):
    return history(db, user, advance_for(db, user, advance_id))


@router.post('', status_code=201)
def create_advance(data: AdvanceInput, db: Session = Depends(db_session), user=Depends(employee)):
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    existing = db.scalar(select(TravelAdvance).where(
        TravelAdvance.employee_id == user.id, TravelAdvance.request_id == str(data.request_id)))
    if existing:
        if (existing.schedule_id, existing.requested, existing.reason, existing.notes) != (
                data.schedule_id, data.requested, data.reason or '', data.notes):
            fail('Mã yêu cầu đã được sử dụng', 409)
        return history(db, user, existing)
    trip = db.scalar(select(Schedule).where(Schedule.id == data.schedule_id, Schedule.assigned_to == user.id).with_for_update())
    if not trip:
        fail('Không tìm thấy chuyến công tác', 404)
    if trip.status == 'cancelled':
        fail('Chuyến công tác đã hủy', 409)
    row = TravelAdvance(request_id=str(data.request_id), employee_id=user.id, employee_name=user.full_name,
                        employee_code=user.employee_code, department=user.team, schedule_id=trip.id,
                        trip_title=trip.title, starts_on=vn_day(trip.starts_at), ends_on=vn_day(trip.ends_at),
                        requested=data.requested, reason=data.reason or '', notes=data.notes)
    db.add(row)
    db.flush()
    record(db, row, user, 'created', {'requested': str(data.requested), 'schedule_id': trip.id})
    commit(db)
    return history(db, user, row)


def ensure_not_future(day):
    if not day or day > datetime.now(VN).date():
        fail('Ngày giao dịch không được để trống hoặc nằm trong tương lai')


@router.post('/{advance_id}/expenses', status_code=201)
def add_expense(advance_id: int, data: ExpenseInput, db: Session = Depends(db_session), user=Depends(employee)):
    row = advance_for(db, user, advance_id, lock=True)
    if row.status not in ('draft', 'pending', 'approved', 'disbursed', 'settlement_pending', 'checking'):
        fail('Hồ sơ đã khóa bổ sung chứng từ', 409)
    invoice = db.scalar(select(Invoice).join(InvoiceFile).where(
        Invoice.id == data.invoice_id, InvoiceFile.uploaded_by == user.id))
    if not invoice:
        fail('Không tìm thấy chứng từ của bạn', 404)
    expense = TravelExpense(advance_id=row.id, **data.model_dump())
    db.add(expense)
    record(db, row, user, 'expense_added', data.model_dump(mode='json'))
    commit(db)
    return history(db, user, row)


def validate_expense(db, expense, amount):
    invoice = db.scalar(select(Invoice).where(Invoice.id == expense.invoice_id).with_for_update())
    if (invoice.validation_status != 'valid' or invoice.approval_status != 'approved'
            or invoice.currency != 'VND' or invoice.total_amount is None
            or invoice.lookup_status in ('mismatch', 'not_found')):
        fail('Chứng từ phải qua kiểm tra hợp lệ, được phê duyệt và có số tiền VND', 409)
    if amount > min(expense.amount, invoice.total_amount):
        fail('Số tiền chấp nhận vượt mức đề nghị hoặc giá trị chứng từ')
    source = invoice.source_file
    fingerprints = [Invoice.id == invoice.id, InvoiceFile.checksum_sha256 == source.checksum_sha256]
    if all((invoice.seller_tax_code, invoice.invoice_symbol, invoice.invoice_number, invoice.invoice_date)):
        fingerprints.append(
            (func.lower(func.trim(Invoice.seller_tax_code)) == invoice.seller_tax_code.strip().lower())
            & (func.lower(func.trim(Invoice.invoice_symbol)) == invoice.invoice_symbol.strip().lower())
            & (func.lower(func.trim(Invoice.invoice_number)) == invoice.invoice_number.strip().lower())
            & (Invoice.invoice_date == invoice.invoice_date)
        )
    duplicate = db.scalar(select(TravelExpense.id).join(Invoice, Invoice.id == TravelExpense.invoice_id)
        .join(InvoiceFile).where(TravelExpense.status == 'accepted', TravelExpense.id != expense.id,
                                 or_(*fingerprints)).limit(1))
    if duplicate:
        fail('Chứng từ trùng một khoản chi đã được chấp nhận', 409)


def lock_expense_reviews(db):
    if db.get_bind().dialect.name == 'postgresql':
        # Identical documents can have different Invoice IDs and belong to different cases.
        db.execute(select(func.pg_advisory_xact_lock(614880318)))


@router.patch('/{advance_id}/expenses/{expense_id}')
def review_expense(advance_id: int, expense_id: int, data: ReviewInput,
                   db: Session = Depends(db_session), user=Depends(accountant)):
    row = advance_for(db, user, advance_id, lock=True)
    if row.status != 'checking':
        fail('Hồ sơ chưa ở bước kiểm tra chứng từ', 409)
    expense = db.scalar(select(TravelExpense).where(TravelExpense.id == expense_id, TravelExpense.advance_id == row.id))
    if not expense:
        fail('Không tìm thấy khoản chi', 404)
    if data.accepted > ZERO:
        lock_expense_reviews(db)
        validate_expense(db, expense, data.accepted)
    previous = format(expense.accepted, '.2f')
    expense.status = 'accepted' if data.accepted > ZERO else 'excluded'
    expense.accepted, expense.review_reason, expense.reviewed_by = data.accepted, data.reason, user.id
    record(db, row, user, 'expense_reviewed', {'expense_id': expense.id, 'previous': previous, **data.model_dump(mode='json')})
    commit(db)
    return history(db, user, row)


TRANSITIONS = {
    'submit': ({'draft'}, 'pending'),
    'approve': ({'pending'}, 'approved'),
    'reject': ({'pending'}, 'rejected'),
    'cancel': ({'draft', 'pending'}, 'cancelled'),
    'disburse': ({'approved'}, 'disbursed'),
    'request_settlement': ({'disbursed'}, 'settlement_pending'),
    'review': ({'settlement_pending'}, 'checking'),
    'settle': ({'checking'}, 'settled'),
}


@router.post('/{advance_id}/actions')
def advance_action(advance_id: int, data: ActionInput, db: Session = Depends(db_session), user=Depends(current_user)):
    row = advance_for(db, user, advance_id, lock=True)
    action = data.action
    if action in ('approve', 'reject'):
        allowed = may_approve(user)
    elif action in ('submit', 'cancel', 'request_settlement'):
        allowed = user.role == 'employee'
    else:
        allowed = user.role == 'accountant'
    if not allowed:
        fail('Bạn không có quyền thực hiện thao tác này', 403)
    valid, next_state = TRANSITIONS[action]
    if row.status not in valid:
        fail('Trạng thái hồ sơ không phù hợp', 409)
    if action in ('submit', 'approve', 'disburse'):
        trip_status = db.scalar(select(Schedule.status).where(Schedule.id == row.schedule_id).with_for_update())
        if trip_status == 'cancelled':
            fail('Chuyến công tác đã hủy', 409)
    audit_details = data.model_dump(mode='json', exclude={'action'}, exclude_none=True)
    if action == 'approve':
        if data.amount is None or not ZERO < data.amount <= row.requested:
            fail('Số tiền duyệt phải lớn hơn 0 và không vượt số tiền đề nghị')
        row.approved, row.approved_by = data.amount, user.id
    elif action == 'reject' and not data.reason:
        fail('Vui lòng nhập lý do từ chối')
    elif action == 'disburse':
        ensure_not_future(data.paid_on)
        if data.amount is None or not ZERO < data.amount <= row.approved:
            fail('Số tiền thực chi phải lớn hơn 0 và không vượt số tiền đã duyệt')
        row.disbursed, row.disbursed_on, row.disbursed_by = data.amount, data.paid_on, user.id
    elif action == 'settle':
        expenses = db.scalars(select(TravelExpense).where(TravelExpense.advance_id == row.id)).all()
        if any(expense.status == 'pending' for expense in expenses):
            fail('Còn chứng từ chưa kiểm tra', 409)
        lock_expense_reviews(db)
        accepted = ZERO
        for expense in expenses:
            if expense.status == 'accepted':
                validate_expense(db, expense, expense.accepted)
                accepted += expense.accepted
        difference = row.disbursed - accepted
        audit_details.update(serialize_money({'accepted': accepted, 'disbursed': row.disbursed, 'difference': difference}))
        if difference != ZERO:
            next_state = 'refund_due' if difference > ZERO else 'supplement_due'
    record(db, row, user, action, {**audit_details, 'from': row.status, 'to': next_state})
    row.status = next_state
    commit(db)
    return history(db, user, row)


@router.post('/{advance_id}/payments', status_code=201)
def record_payment(advance_id: int, data: PaymentInput, db: Session = Depends(db_session), user=Depends(accountant)):
    row = advance_for(db, user, advance_id, lock=True)
    reference = data.reference.casefold()
    existing = db.scalar(select(TravelPayment).where(TravelPayment.kind == data.kind, TravelPayment.reference == reference))
    if existing:
        compared = ('kind', 'amount', 'paid_on', 'method', 'evidence', 'notes')
        if existing.advance_id == row.id and fields(existing, *compared) == fields(data, *compared):
            return history(db, user, row)
        fail('Mã giao dịch hoặc phiếu đã được sử dụng', 409)
    if row.status != ('refund_due' if data.kind == 'refund' else 'supplement_due'):
        fail('Hồ sơ chưa chờ xử lý khoản thanh toán này', 409)
    ensure_not_future(data.paid_on)
    if data.paid_on < row.disbursed_on:
        fail('Ngày giao dịch không được trước ngày chi tạm ứng')
    accepted = db.scalar(select(func.sum(TravelExpense.accepted)).where(
        TravelExpense.advance_id == row.id, TravelExpense.status == 'accepted')) or ZERO
    paid = db.scalar(select(func.sum(TravelPayment.amount)).where(
        TravelPayment.advance_id == row.id, TravelPayment.kind == data.kind)) or ZERO
    remaining = abs(row.disbursed - accepted) - paid
    if data.amount > remaining:
        fail('Số tiền giao dịch vượt số dư còn lại')
    payment = TravelPayment(advance_id=row.id, recorded_by=user.id, **{**data.model_dump(), 'reference': reference})
    db.add(payment)
    if data.amount == remaining:
        row.status = 'settled'
    record(db, row, user, data.kind, {**data.model_dump(mode='json'), 'reference': reference,
                                    'remaining': str(remaining - data.amount), 'status': row.status})
    commit(db)
    return history(db, user, row)


@router.post('/{advance_id}/expenses/{expense_id}/ai-review')
def advise_expense(advance_id: int, expense_id: int, db: Session = Depends(db_session), user=Depends(accountant)):
    row = advance_for(db, user, advance_id)
    result = db.execute(select(TravelExpense, Invoice).join(Invoice, Invoice.id == TravelExpense.invoice_id)
                        .where(TravelExpense.id == expense_id, TravelExpense.advance_id == row.id)).one_or_none()
    if not result:
        fail('Không tìm thấy khoản chi', 404)
    expense, invoice = result
    risks = assess_invoice_risks(db, invoice, role=user.role)
    facts = {
        'category': expense.category, 'claimed_vnd': str(expense.amount),
        'currency': invoice.currency, 'ocr_status': invoice.validation_status,
        'lookup_status': invoice.lookup_status, 'approval_status': invoice.approval_status,
        'risk_codes': [flag['code'] for flag in risks['flags']],
        **{field: str(value) if value is not None else None for field, value in
           fields(invoice, 'subtotal', 'vat_amount', 'total_amount', 'confidence_score').items()},
    }
    db.rollback()
    try:
        return {'advice': gemini_chat.travel_receipt_advice(facts)}
    except gemini_chat.GeminiUnavailable as error:
        fail(gemini_chat.friendly_error(error.code), 429 if error.code == 'quota' else 503)


@router.post('/{advance_id}/payments/{payment_id}/evidence', status_code=201)
def upload_payment_evidence(advance_id: int, payment_id: int, file: UploadFile = File(...),
                            db: Session = Depends(db_session), user=Depends(accountant)):
    row = advance_for(db, user, advance_id, lock=True)
    payment = db.scalar(select(TravelPayment.id).where(TravelPayment.id == payment_id, TravelPayment.advance_id == row.id))
    if not payment:
        fail('Không tìm thấy giao dịch', 404)
    filename = PureWindowsPath(file.filename or 'chung-tu').name[:255]
    types = {
        '.pdf': ('application/pdf', b'%PDF-'),
        '.png': ('image/png', b'\x89PNG\r\n\x1a\n'),
        '.jpg': ('image/jpeg', b'\xff\xd8\xff'),
        '.jpeg': ('image/jpeg', b'\xff\xd8\xff'),
    }
    file_type = types.get(PureWindowsPath(filename).suffix.lower())
    limit = min(settings.max_upload_mb, 10) * 1024 * 1024
    content = file.file.read(limit + 1)
    if not file_type or not content.startswith(file_type[1]):
        fail('Chứng từ phải là PDF, PNG hoặc JPEG hợp lệ')
    if len(content) > limit:
        fail('Tệp chứng từ vượt giới hạn dung lượng', 413)
    existing = db.get(TravelPaymentEvidence, payment_id)
    if existing:
        if existing.filename == filename and existing.content == content:
            return history(db, user, row)
        fail('Giao dịch đã có tệp chứng từ', 409)
    db.add(TravelPaymentEvidence(payment_id=payment_id, filename=filename, mime_type=file_type[0], content=content))
    record(db, row, user, 'payment_evidence', {'payment_id': payment_id, 'filename': filename})
    commit(db)
    return history(db, user, row)


@router.get('/{advance_id}/payments/{payment_id}/evidence')
def download_payment_evidence(advance_id: int, payment_id: int, db: Session = Depends(db_session), user=Depends(current_user)):
    row = advance_for(db, user, advance_id)
    evidence = db.scalar(select(TravelPaymentEvidence).join(TravelPayment).where(
        TravelPayment.id == payment_id, TravelPayment.advance_id == row.id))
    if not evidence:
        fail('Không tìm thấy tệp chứng từ', 404)
    return Response(evidence.content, media_type=evidence.mime_type, headers={
        'Content-Disposition': "attachment; filename*=UTF-8''" + quote(evidence.filename, safe=''),
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
    })
