"""Travel advance and settlement ledger. No bank transfer or AI decision-making."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Integer, Boolean, String, ForeignKey, Numeric, JSON, Date, DateTime, LargeBinary, UniqueConstraint, select, func
from sqlalchemy.orm import mapped_column
from .core import Base, db_session, current_user, require_roles
from .models import User, Schedule, Invoice, InvoiceFile, Notification, ExtractionRun
from . import approval_sla as sla
from .finance import CATEGORIES, fold

router=APIRouter(prefix='/api/v1/travel',tags=['Travel advance and settlement'])
EDITABLE={'received','settlement_returned'}
OFFICIAL={'settlement_approved','closed'}
STATUS_LABELS={'advance_draft':'Nháp đề nghị','advance_submitted':'Chờ Admin duyệt tạm ứng','advance_returned':'Bổ sung đề nghị',
    'advance_rejected':'Tạm ứng bị từ chối','advance_approved':'Đã duyệt, chờ cấp tiền','disbursed':'Đã cấp, chờ xác nhận nhận tiền',
    'received':'Đã nhận, khai báo chi phí','settlement_submitted':'Kế toán đang kiểm tra','settlement_returned':'Bổ sung quyết toán',
    'settlement_reviewed':'Chờ Admin phê duyệt','settlement_approved':'Đã duyệt, chờ đối chiếu giao dịch',
    'settlement_rejected':'Quyết toán bị từ chối','closed':'Đã quyết toán'}

class TravelCase(Base):
    __tablename__='travel_cases'
    id=mapped_column(Integer,primary_key=True)
    schedule_id=mapped_column(ForeignKey('schedules.id'),unique=True)
    owner_id=mapped_column(ForeignKey('users.id'),index=True)
    schedule_snapshot=mapped_column(JSON)
    requested=mapped_column(Numeric(18,2))
    approved=mapped_column(Numeric(18,2),nullable=True)
    purpose=mapped_column(String(2000))
    note=mapped_column(String(2000),default='')
    status=mapped_column(String(40),default='advance_draft',index=True)
    version=mapped_column(Integer,default=1)
    created_at=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    updated_at=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class TravelExpense(Base):
    __tablename__='travel_expenses'
    id=mapped_column(Integer,primary_key=True)
    case_id=mapped_column(ForeignKey('travel_cases.id'),index=True)
    invoice_id=mapped_column(ForeignKey('invoices.id'),unique=True,nullable=True)
    description=mapped_column(String(2000))
    category=mapped_column(String(40))
    occurred_on=mapped_column(Date)
    quantity=mapped_column(Numeric(18,4),nullable=True)
    unit_price=mapped_column(Numeric(18,4),nullable=True)
    amount=mapped_column(Numeric(18,2))
    purpose=mapped_column(String(2000),default='')
    no_invoice_reason=mapped_column(String(2000),default='')
    invoice_snapshot=mapped_column(JSON,nullable=True)
    review_status=mapped_column(String(20),default='pending')
    accepted=mapped_column(Numeric(18,2),nullable=True)
    review_reason=mapped_column(String(2000),default='')
    reviewed_by=mapped_column(ForeignKey('users.id'),nullable=True)
    deleted=mapped_column(Boolean,default=False)

class TravelTransaction(Base):
    __tablename__='travel_transactions'
    __table_args__=(UniqueConstraint('case_id','request_key'),UniqueConstraint('case_id','kind','reference'))
    id=mapped_column(Integer,primary_key=True)
    case_id=mapped_column(ForeignKey('travel_cases.id'),index=True)
    kind=mapped_column(String(30))
    amount=mapped_column(Numeric(18,2))
    paid_on=mapped_column(Date)
    method=mapped_column(String(80))
    reference=mapped_column(String(255))
    request_key=mapped_column(String(80))
    actor_id=mapped_column(ForeignKey('users.id'))
    received_at=mapped_column(DateTime(timezone=True),nullable=True)
    created_at=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class TravelEvidence(Base):
    __tablename__='travel_evidence'
    id=mapped_column(Integer,primary_key=True)
    case_id=mapped_column(ForeignKey('travel_cases.id'),index=True)
    expense_id=mapped_column(ForeignKey('travel_expenses.id'),nullable=True)
    transaction_id=mapped_column(ForeignKey('travel_transactions.id'),nullable=True)
    filename=mapped_column(String(255))
    mime=mapped_column(String(80))
    data=mapped_column(LargeBinary)
    checksum=mapped_column(String(64))
    actor_id=mapped_column(ForeignKey('users.id'))
    created_at=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class TravelHistory(Base):
    __tablename__='travel_history'
    id=mapped_column(Integer,primary_key=True)
    case_id=mapped_column(ForeignKey('travel_cases.id'),index=True)
    actor_id=mapped_column(ForeignKey('users.id'),nullable=True)
    action=mapped_column(String(80))
    payload=mapped_column(JSON,default=dict)
    event_key=mapped_column(String(120),unique=True,nullable=True)
    created_at=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class TravelSLA(Base):
    __tablename__='travel_sla_cycles'
    id=mapped_column(Integer,primary_key=True)
    case_id=mapped_column(ForeignKey('travel_cases.id'),index=True)
    policy_id=mapped_column(ForeignKey('approval_sla_policies.id'),nullable=True)
    days=mapped_column(Integer)
    holidays=mapped_column(JSON)
    submitted_at=mapped_column(DateTime(timezone=True))
    due_at=mapped_column(DateTime(timezone=True))
    processed_at=mapped_column(DateTime(timezone=True),nullable=True)
    outcome=mapped_column(String(20),nullable=True)
    @property
    def invoice_id(self): return self.case_id

def fail(message,code=409): raise HTTPException(code,message)
def now(): return datetime.now(timezone.utc)
def money(value): return str(Decimal(value).quantize(Decimal('.01')))
def rows(db,case): return db.scalars(select(TravelExpense).where(TravelExpense.case_id==case.id,TravelExpense.deleted.is_(False)).order_by(TravelExpense.id)).all()
def txs(db,case): return db.scalars(select(TravelTransaction).where(TravelTransaction.case_id==case.id).order_by(TravelTransaction.id)).all()
def allowed(db,user,case_id,write=False):
    q=select(TravelCase).where(TravelCase.id==case_id)
    if user.role=='employee': q=q.where(TravelCase.owner_id==user.id)
    elif user.role not in ('admin','accountant'): fail('Không có quyền truy cập',403)
    if write:q=q.with_for_update().execution_options(populate_existing=True)
    item=db.scalar(q)
    if not item:fail('Không tìm thấy hồ sơ trong phạm vi truy cập',404)
    return item

def history(db,case,user,action,payload=None):
    case.version+=1;case.updated_at=now()
    entry=TravelHistory(case_id=case.id,actor_id=user.id,action=action,payload={**(payload or {}),'_actor':{'name':user.full_name,'role':user.role}})
    db.add(entry);return entry

def notice(db,case,roles,title):
    ids=[case.owner_id] if 'employee' in roles else []
    ids+=db.scalars(select(User.id).where(User.role.in_([r for r in roles if r!='employee']),User.status=='active')).all()
    for uid in set(ids):
        db.add(Notification(user_id=uid,travel_case_id=case.id,title=title,message=f'Hồ sơ công tác #{case.id}: {case.schedule_snapshot["title"]}'))

def totals(db,case):
    expenses=rows(db,case);transactions=txs(db,case)
    amount=lambda kind,received=False:sum((t.amount for t in transactions if t.kind==kind and (not received or t.received_at)),Decimal('0'))
    issued,received=amount('disbursement'),amount('disbursement',True)
    declared=sum((e.amount for e in expenses),Decimal('0'))
    with_invoice=sum((e.amount for e in expenses if e.invoice_id),Decimal('0'))
    reviewed=bool(expenses) and all(e.accepted is not None for e in expenses)
    accepted=sum((e.accepted for e in expenses if e.accepted is not None),Decimal('0')) if reviewed else None
    official=accepted if case.status in OFFICIAL else None
    refund,supplement=amount('refund'),amount('supplement')
    declared_refund=amount('return_declaration')
    diff=received-declared
    final_diff=received-official if official is not None else None
    return {'requested':money(case.requested),'approved':money(case.approved) if case.approved is not None else None,
        'issued':money(issued),'received':money(received),'with_invoice':money(with_invoice),'without_invoice':money(declared-with_invoice),
        'declared':money(declared),'accepted_proposed':money(accepted) if accepted is not None else None,
        'accepted':money(official) if official is not None else None,'rejected':money(declared-official) if official is not None else None,
        'expected_refund':money(max(diff,0)),'expected_supplement':money(max(-diff,0)),
        'refund_required':money(max(final_diff,0)) if final_diff is not None else None,
        'supplement_required':money(max(-final_diff,0)) if final_diff is not None else None,
        'refund_paid':money(refund),'supplement_paid':money(supplement),
        'refund_declared':money(declared_refund),
        'refund_declaration_available':money(max(max(final_diff,0)-max(refund,declared_refund),0)) if final_diff is not None else None,
        'remaining':money(max(final_diff,0)-refund+max(-final_diff,0)-supplement) if final_diff is not None else None,
        'utilization_percent':str(round(declared*100/received,2)) if received>0 else None}

def sla_json(cycle):
    result=sla.serialize(cycle);result['case_id']=result.pop('invoice_id');return result

def serialize(db,case,detail=False):
    employee=db.get(User,case.owner_id)
    cycles=db.scalars(select(TravelSLA).where(TravelSLA.case_id==case.id).order_by(TravelSLA.id)).all()
    data={'id':case.id,'schedule_id':case.schedule_id,'owner_id':case.owner_id,'employee_name':employee.full_name,
        'team':employee.team,'schedule':case.schedule_snapshot,'purpose':case.purpose,'note':case.note,'status':case.status,
        'version':case.version,'created_at':sla.utc(case.created_at).isoformat(),'updated_at':sla.utc(case.updated_at).isoformat(),
        'totals':totals(db,case),'sla':sla_json(cycles[-1]) if cycles else None}
    if detail:
        history_rows=db.scalars(select(TravelHistory).where(TravelHistory.case_id==case.id).order_by(TravelHistory.id)).all()
        transactions=txs(db,case)
        actors={u.id:u for u in db.scalars(select(User).where(User.id.in_({h.actor_id for h in history_rows if h.actor_id}|{t.actor_id for t in transactions})))}
        def actor_info(actor_id,snapshot=None):
            actor=actors.get(actor_id)
            snapshot=snapshot if isinstance(snapshot,dict) else {}
            return {'actor_name':snapshot.get('name') or (actor.full_name if actor else 'Tài khoản không còn khả dụng' if actor_id else 'Hệ thống'),
                'actor_role':snapshot.get('role') or (actor.role if actor else None),
                'actor_role_source':'event' if snapshot.get('role') else 'current_account' if actor else None}
        data['expenses']=[{'id':e.id,'invoice_id':e.invoice_id,'description':e.description,'category':e.category,'occurred_on':str(e.occurred_on),
            'quantity':str(e.quantity) if e.quantity is not None else None,'unit_price':str(e.unit_price) if e.unit_price is not None else None,
            'amount':money(e.amount),'purpose':e.purpose,'no_invoice_reason':e.no_invoice_reason,'invoice_snapshot':e.invoice_snapshot,
            'review_status':e.review_status,'accepted':money(e.accepted) if e.accepted is not None else None,'review_reason':e.review_reason} for e in rows(db,case)]
        data['transactions']=[{'id':t.id,'kind':t.kind,'amount':money(t.amount),'paid_on':str(t.paid_on),'method':t.method,'reference':t.reference,'actor_id':t.actor_id,**actor_info(t.actor_id),'received_at':sla.utc(t.received_at).isoformat() if t.received_at else None} for t in transactions]
        evidence_rows=db.execute(select(TravelEvidence.id,TravelEvidence.expense_id,TravelEvidence.transaction_id,TravelEvidence.filename,TravelEvidence.created_at,func.length(TravelEvidence.data).label('file_size_bytes')).where(TravelEvidence.case_id==case.id).order_by(TravelEvidence.id)).mappings()
        data['evidence']=[{**dict(e),'created_at':sla.utc(e['created_at']).isoformat()} for e in evidence_rows]
        data['history']=[{'id':h.id,'actor_id':h.actor_id,**actor_info(h.actor_id,(h.payload or {}).get('_actor')),'action':h.action,'payload':h.payload,'created_at':sla.utc(h.created_at).isoformat()} for h in history_rows]
        data['sla_history']=[sla_json(c) for c in cycles]
    return data

def parse_vnd(value):
    """Whole VND only. Accept explicit Vietnamese grouping, never round money."""
    if value is None:return None
    if isinstance(value,bool):raise ValueError('Số tiền VND không hợp lệ')
    if isinstance(value,str):
        value=value.strip()
        if re.fullmatch(r'\d{1,3}(?:\.\d{3})+(?:,0+)?',value):value=value.split(',')[0].replace('.','')
        elif re.fullmatch(r'\d+,0+',value):value=value.split(',')[0]
        elif not re.fullmatch(r'-?\d+(?:\.\d+)?',value):raise ValueError('Nhập số tiền VND nguyên, ví dụ 10000000 hoặc 10.000.000')
    try:result=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError):raise ValueError('Số tiền VND không hợp lệ')
    if not result.is_finite() or result!=result.to_integral_value():raise ValueError('Số tiền VND phải là số nguyên đồng; không chấp nhận phần lẻ dưới 1 đồng')
    return result

class VNDInput(BaseModel):
    @field_validator('requested','amount','accepted',mode='before',check_fields=False)
    @classmethod
    def whole_vnd(cls,value):return parse_vnd(value)

class AdvanceInput(VNDInput):
    schedule_id:int
    requested:Decimal=Field(gt=0,max_digits=18,decimal_places=2)
    purpose:str=Field(min_length=1,max_length=2000)
    note:str=Field(default='',max_length=2000)
    @field_validator('purpose')
    @classmethod
    def not_blank(cls,v):
        if not v.strip():raise ValueError('Mục đích không được trống')
        return v.strip()

class Action(VNDInput):
    action:str
    version:int
    amount:Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=2)
    reason:str=Field(default='',max_length=2000)

class ExpenseInput(VNDInput):
    request_key:str|None=Field(default=None,min_length=8,max_length=80)
    invoice_id:int|None=None
    description:str=Field(default='',max_length=2000)
    category:str='travel'
    occurred_on:date|None=None
    quantity:Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=4)
    unit_price:Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=4)
    amount:Decimal|None=Field(default=None,ge=0,max_digits=18,decimal_places=2)
    purpose:str=Field(default='',max_length=2000)
    no_invoice_reason:str=Field(default='',max_length=2000)

class ReviewInput(VNDInput):
    accepted:Decimal=Field(ge=0,max_digits=18,decimal_places=2)
    reason:str=Field(default='',max_length=2000)

class TransactionInput(VNDInput):
    kind:str
    amount:Decimal=Field(gt=0,max_digits=18,decimal_places=2)
    paid_on:date
    method:str=Field(min_length=1,max_length=80)
    reference:str=Field(min_length=1,max_length=255)
    request_key:str=Field(min_length=8,max_length=80)
    @field_validator('reference','method','request_key')
    @classmethod
    def normalized(cls,value):
        if not value.strip():raise ValueError('Cần giá trị thực tế')
        return value.strip()

@router.get('/cases')
def cases(status:str='',employee_id:int|None=None,team:str='',starts:date|None=None,ends:date|None=None,db=Depends(db_session),user=Depends(current_user)):
    if user.role not in ('employee','accountant','admin'):fail('Không có quyền xem hồ sơ',403)
    q=select(TravelCase).join(User,User.id==TravelCase.owner_id)
    if user.role=='employee':q=q.where(TravelCase.owner_id==user.id)
    if employee_id:q=q.where(TravelCase.owner_id==employee_id)
    if team:q=q.where(User.team==team)
    if status:q=q.where(TravelCase.status==status)
    if starts:q=q.where(TravelCase.created_at>=datetime.combine(starts,datetime.min.time(),sla.TZ))
    if ends:q=q.where(TravelCase.created_at<datetime.combine(ends+timedelta(days=1),datetime.min.time(),sla.TZ))
    if starts and ends and starts>ends:fail('Ngày bắt đầu phải trước ngày kết thúc',422)
    return [serialize(db,c) for c in db.scalars(q.order_by(TravelCase.id.desc())).all()]

@router.post('/cases',status_code=201)
def create(body:AdvanceInput,db=Depends(db_session),user=Depends(require_roles('employee'))):
    schedule=db.scalar(select(Schedule).where(Schedule.id==body.schedule_id).with_for_update())
    if not schedule or schedule.assigned_to!=user.id:fail('Chỉ chọn lịch công tác của chính mình',403)
    if schedule.status=='cancelled':fail('Lịch công tác đã hủy')
    if db.scalar(select(TravelCase.id).where(TravelCase.schedule_id==schedule.id)):fail('Lịch này đã có hồ sơ tạm ứng')
    case=TravelCase(schedule_id=schedule.id,owner_id=user.id,requested=body.requested,purpose=body.purpose,note=body.note,
        schedule_snapshot={'title':schedule.title,'destination':schedule.destination,'starts_at':sla.utc(schedule.starts_at).isoformat(),'ends_at':sla.utc(schedule.ends_at).isoformat()},version=0)
    db.add(case);db.flush();history(db,case,user,'created');db.commit();return serialize(db,case,True)

@router.get('/cases/{case_id}')
def get(case_id:int,db=Depends(db_session),user=Depends(current_user)):return serialize(db,allowed(db,user,case_id),True)

@router.put('/cases/{case_id}')
def edit(case_id:int,body:AdvanceInput,db=Depends(db_session),user=Depends(require_roles('employee'))):
    case=allowed(db,user,case_id,True)
    if case.status not in ('advance_draft','advance_returned','advance_rejected'):fail('Không thể sửa đề nghị ở bước hiện tại')
    if body.schedule_id!=case.schedule_id:fail('Không thể đổi liên kết lịch công tác')
    history(db,case,user,'advance_edited',{'previous':{'requested':money(case.requested),'purpose':case.purpose,'note':case.note}})
    case.requested,case.purpose,case.note=body.requested,body.purpose,body.note
    db.commit();return serialize(db,case,True)

@router.post('/cases/{case_id}/actions')
def action(case_id:int,body:Action,db=Depends(db_session),user=Depends(current_user)):
    case=allowed(db,user,case_id,True)
    if body.version!=case.version:fail('Hồ sơ đã thay đổi. Vui lòng tải lại.')
    a=body.action
    transitions={
        'submit_advance':('employee',{'advance_draft','advance_returned','advance_rejected'},'advance_submitted'),
        'approve_advance':('admin',{'advance_submitted'},'advance_approved'),
        'reject_advance':('admin',{'advance_submitted'},'advance_rejected'),
        'return_advance':('admin',{'advance_submitted'},'advance_returned'),
        'submit_settlement':('employee',EDITABLE,'settlement_submitted'),
        'return_settlement':('accountant',{'settlement_submitted'},'settlement_returned'),
        'forward_settlement':('accountant',{'settlement_submitted'},'settlement_reviewed'),
        'approve_settlement':('admin',{'settlement_reviewed'},'settlement_approved'),
        'reject_settlement':('admin',{'settlement_reviewed'},'settlement_rejected'),
        'admin_return':('admin',{'settlement_reviewed','settlement_rejected'},'settlement_returned'),
        'close':('accountant',{'settlement_approved'},'closed')}
    if a not in transitions:fail('Thao tác không hợp lệ',422)
    role,states,target=transitions[a]
    if user.role!=role or (role!='employee' and user.id==case.owner_id):fail('Không có quyền hoặc không được tự duyệt hồ sơ',403)
    if case.status not in states:fail('Không thể bỏ qua bước hoặc xử lý lại hồ sơ')
    if ('reject' in a or 'return' in a) and not body.reason.strip():fail('Cần ghi rõ lý do',422)
    if a=='submit_advance':
        s=db.scalar(select(Schedule).where(Schedule.id==case.schedule_id).with_for_update())
        if s.assigned_to!=case.owner_id or s.status=='cancelled':fail('Lịch không còn phù hợp')
        case.schedule_snapshot={'title':s.title,'destination':s.destination,'starts_at':sla.utc(s.starts_at).isoformat(),'ends_at':sla.utc(s.ends_at).isoformat()}
    if a=='approve_advance':
        s=db.scalar(select(Schedule).where(Schedule.id==case.schedule_id).with_for_update().execution_options(populate_existing=True))
        snapshot={'title':s.title,'destination':s.destination,'starts_at':sla.utc(s.starts_at).isoformat(),'ends_at':sla.utc(s.ends_at).isoformat()}
        if snapshot!=case.schedule_snapshot or s.status=='cancelled':fail('Lịch đã thay đổi sau khi gửi; cần trả về để nhân viên cập nhật đề nghị')
        if body.amount is None or body.amount<=0:fail('Số tiền được duyệt phải lớn hơn 0',422)
        if body.amount!=case.requested and not body.reason.strip():fail('Điều chỉnh số tiền cần lý do',422)
        case.approved=body.amount
    if a=='submit_settlement':
        sla.lock(db)
        expenses=rows(db,case);transactions=txs(db,case)
        if not expenses:fail('Cần khai báo chi phí trước khi gửi')
        if any(t.kind=='disbursement' and not t.received_at for t in transactions):fail('Cần xác nhận nhận tiền đã cấp')
        if sla.utc(db.get(Schedule,case.schedule_id).ends_at)>now():fail('Chỉ quyết toán sau khi kết thúc chuyến công tác')
        for e in expenses:
            if e.invoice_id:
                invoice=db.scalar(select(Invoice).where(Invoice.id==e.invoice_id).with_for_update())
                if not invoice or invoice.total_amount!=e.amount or str(invoice.updated_at)!=(e.invoice_snapshot or {}).get('updated_at'):
                    fail('Hóa đơn nguồn đã thay đổi; hãy mở sửa khoản chi để đối chiếu và lưu lại trước khi gửi')
            e.review_status='pending';e.accepted=None;e.reviewed_by=None;e.review_reason=''
        policy=sla.current_policy(db);days=policy.days if policy else 3;holidays=list(policy.holidays) if policy else []
        submitted=now();db.add(TravelSLA(case_id=case.id,policy_id=policy.id if policy else None,days=days,holidays=holidays,submitted_at=submitted,due_at=sla.deadline(submitted,days,holidays)))
    if a=='forward_settlement' and any(e.accepted is None for e in rows(db,case)):fail('Kế toán cần kiểm tra tất cả khoản chi')
    if a in ('return_settlement','approve_settlement','reject_settlement','admin_return'):
        cycle=db.scalar(select(TravelSLA).where(TravelSLA.case_id==case.id).order_by(TravelSLA.id.desc()).limit(1))
        if cycle and not cycle.processed_at:
            cycle.processed_at=now();cycle.outcome='approved' if a=='approve_settlement' else 'returned' if 'return' in a else 'rejected'
    if a=='close' and Decimal(totals(db,case)['remaining'])!=0:fail('Chưa hoàn tất nghĩa vụ hoàn ứng hoặc thanh toán bổ sung')
    case.status=target;history(db,case,user,a,{'reason':body.reason,'amount':money(body.amount) if body.amount is not None else None})
    recipients={'submit_advance':['admin'],'approve_advance':['accountant','employee'],'submit_settlement':['accountant'],
        'forward_settlement':['admin'],'approve_settlement':['employee','accountant']}.get(a,['employee'])
    notice(db,case,recipients,{'submit_advance':'Đề nghị tạm ứng mới','approve_advance':'Tạm ứng đã được duyệt, chờ cấp tiền',
        'reject_advance':'Đề nghị tạm ứng bị từ chối','return_advance':'Đề nghị tạm ứng cần bổ sung',
        'submit_settlement':'Hồ sơ quyết toán chờ kiểm tra','return_settlement':'Kế toán yêu cầu bổ sung quyết toán',
        'forward_settlement':'Quyết toán chờ phê duyệt cuối cùng','approve_settlement':'Quyết toán đã được duyệt, cần đối chiếu hoàn ứng/thanh toán bổ sung',
        'reject_settlement':'Quyết toán bị từ chối','admin_return':'Admin yêu cầu bổ sung quyết toán','close':'Đã hoàn thành quyết toán'}.get(a,'Hồ sơ công tác đã được xử lý'))
    db.commit();return serialize(db,case,True)

@router.post('/cases/{case_id}/expenses')
def add_expense(case_id:int,body:ExpenseInput,db=Depends(db_session),user=Depends(require_roles('employee'))):
    case=allowed(db,user,case_id,True)
    sla.lock(db)
    key=f'expense:{case.id}:{body.request_key}' if body.request_key else None
    signature=hashlib.sha256(json.dumps(body.model_dump(mode='json',exclude={'request_key'}),sort_keys=True).encode()).hexdigest()
    previous=db.scalar(select(TravelHistory).where(TravelHistory.event_key==key)) if key else None
    if previous:
        if previous.payload.get('request_signature')!=signature:fail('Mã yêu cầu đã được dùng cho khoản chi khác')
        return serialize(db,case,True)
    if case.status not in EDITABLE:fail('Chỉ khai báo khi đã nhận tiền hoặc hồ sơ được trả về')
    values=expense_values(db,user,body)
    if body.invoice_id:
        if db.scalar(select(TravelExpense.id).where(TravelExpense.invoice_id==body.invoice_id)):fail('Hóa đơn đã liên kết hồ sơ; không tính trùng')
        # The existing verification report remains the authority for duplicate
        # warnings; identity/hash checks here prevent double-settlement claims.
        invoice=db.get(Invoice,body.invoice_id);file=db.get(InvoiceFile,invoice.file_id)
        linked=db.execute(select(TravelExpense,Invoice,InvoiceFile).join(Invoice,TravelExpense.invoice_id==Invoice.id).join(InvoiceFile,Invoice.file_id==InvoiceFile.id).where(TravelExpense.deleted.is_(False))).all()
        for e,other,source in linked:
            identity=lambda x:(x.seller_tax_code,x.invoice_number,x.invoice_symbol,x.invoice_date,x.total_amount)
            if (file.checksum_sha256 and file.checksum_sha256==source.checksum_sha256) or (all(v is not None and str(v).strip() for v in identity(invoice)) and identity(invoice)==identity(other)):
                fail('Chứng từ trùng nội dung hoặc định danh đã thuộc hồ sơ khác; cần đối chiếu, không tự tính hai lần')
    expense=TravelExpense(case_id=case.id,**values);db.add(expense);db.flush()
    event=history(db,case,user,'expense_added',{'expense_id':expense.id,'invoice_id':body.invoice_id,'amount':money(values['amount']),'request_signature':signature})
    event.event_key=key
    db.commit();return serialize(db,case,True)

def expense_values(db,user,body):
    if body.category not in CATEGORIES:fail('Danh mục không hợp lệ',422)
    values=body.model_dump(exclude={'request_key'})
    if body.invoice_id:
        invoice=db.scalar(select(Invoice).where(Invoice.id==body.invoice_id).with_for_update())
        if not invoice or db.get(InvoiceFile,invoice.file_id).uploaded_by!=user.id:fail('Chỉ dùng hóa đơn của chính mình',403)
        latest=db.scalar(select(ExtractionRun).where(ExtractionRun.invoice_id==invoice.id).order_by(ExtractionRun.id.desc()).limit(1))
        if latest and latest.status in ('pending','queued','processing','running'):fail('OCR chưa hoàn tất; chờ xử lý trước khi liên kết hóa đơn')
        if latest and latest.status in ('failed','error'):fail('Trích xuất hóa đơn thất bại; mở Chi tiết hóa đơn để kiểm tra trước khi liên kết')
        observed=((latest.extracted_json or {}).get('_ocr',{}).get('currency_observation') or {}) if latest else {}
        if observed.get('state')=='conflicting' or (observed.get('state')=='observed' and observed.get('code')!=invoice.currency):
            fail('Đơn vị tiền tệ chưa khớp bằng chứng OCR; cần đối chiếu tại Chi tiết hóa đơn, không tự quy đổi')
        if not invoice.currency or not invoice.currency.strip():fail('Chưa xác định đơn vị tiền tệ; hãy mở chi tiết hóa đơn để đối chiếu')
        if invoice.currency!='VND':fail('Chỉ liên kết chi phí VND; hệ thống không tự quy đổi ngoại tệ')
        if invoice.total_amount is None:fail('Chưa trích xuất được tổng thanh toán; hãy kiểm tra và bổ sung tại Chi tiết hóa đơn trước khi liên kết')
        if not Decimal(str(invoice.total_amount)).is_finite() or invoice.total_amount<0:fail('Tổng thanh toán không hợp lệ; không tự tạo hoặc suy đoán số tiền')
        if invoice.validation_status=='error':fail('Hóa đơn còn lỗi xử lý; cần kiểm tra trước khi liên kết')
        if invoice.document_type not in ('bill','einvoice'):fail('Chứng từ chưa được xác định là khoản chi')
        if not invoice.invoice_date:fail('Cần kiểm tra ngày hóa đơn trước khi liên kết')
        values.update(description=body.description.strip() or invoice.seller_name or 'Chi phí có hóa đơn',amount=invoice.total_amount,occurred_on=invoice.invoice_date,quantity=None,unit_price=None,
            invoice_snapshot={'invoice_number':invoice.invoice_number,'seller_name':invoice.seller_name,'seller_tax_code':invoice.seller_tax_code,'total_amount':money(invoice.total_amount),'updated_at':str(invoice.updated_at)})
    else:
        if not body.description.strip() or not body.no_invoice_reason.strip() or not body.purpose.strip() or body.amount is None or body.occurred_on is None:fail('Cần tên, ngày, số tiền, mục đích và lý do không có hóa đơn',422)
        if body.quantity is not None and body.unit_price is not None and abs(body.quantity*body.unit_price-body.amount)>Decimal('.01'):fail('Số lượng × đơn giá không khớp tổng tiền; không tự sửa dữ liệu',422)
    if values['occurred_on']>now().astimezone(sla.TZ).date():fail('Ngày chi phí không thể ở tương lai',422)
    return values

@router.put('/cases/{case_id}/expenses/{expense_id}')
def edit_expense(case_id:int,expense_id:int,body:ExpenseInput,db=Depends(db_session),user=Depends(require_roles('employee'))):
    case=allowed(db,user,case_id,True);e=db.get(TravelExpense,expense_id)
    if not e or e.case_id!=case.id or e.deleted:fail('Không tìm thấy khoản chi',404)
    if case.status not in EDITABLE:fail('Khoản chi đang khóa chỉnh sửa')
    if body.invoice_id!=e.invoice_id:fail('Không thay hóa đơn của khoản chi; hãy xóa rồi liên kết lại')
    values=expense_values(db,user,body)
    history(db,case,user,'expense_edited',{'expense_id':e.id,'previous':{'amount':money(e.amount),'description':e.description,
        'occurred_on':str(e.occurred_on),'category':e.category,'quantity':str(e.quantity) if e.quantity is not None else None,
        'unit_price':str(e.unit_price) if e.unit_price is not None else None,'purpose':e.purpose,'no_invoice_reason':e.no_invoice_reason,
        'accepted':money(e.accepted) if e.accepted is not None else None,'review_reason':e.review_reason}})
    for k,v in values.items():setattr(e,k,v)
    e.accepted=None;e.review_status='pending';e.reviewed_by=None;e.review_reason='';db.commit();return serialize(db,case,True)

@router.delete('/cases/{case_id}/expenses/{expense_id}')
def delete_expense(case_id:int,expense_id:int,db=Depends(db_session),user=Depends(require_roles('employee'))):
    case=allowed(db,user,case_id,True);e=db.get(TravelExpense,expense_id)
    if not e or e.case_id!=case.id or e.deleted:fail('Không tìm thấy khoản chi',404)
    if case.status not in EDITABLE:fail('Khoản chi đang khóa chỉnh sửa')
    history(db,case,user,'expense_removed',{'expense_id':e.id,'invoice_id':e.invoice_id,'amount':money(e.amount)})
    e.deleted=True;e.invoice_id=None;db.commit();return serialize(db,case,True)

@router.post('/cases/{case_id}/expenses/{expense_id}/review')
def review(case_id:int,expense_id:int,body:ReviewInput,db=Depends(db_session),user=Depends(require_roles('accountant'))):
    case=allowed(db,user,case_id,True);e=db.get(TravelExpense,expense_id)
    if user.id==case.owner_id:fail('Không tự kiểm tra hồ sơ của mình',403)
    if case.status!='settlement_submitted':fail('Hồ sơ không ở bước kế toán kiểm tra')
    if not e or e.case_id!=case.id or e.deleted:fail('Không tìm thấy khoản chi',404)
    if body.accepted>e.amount:fail('Không chấp nhận vượt chi phí khai báo',422)
    if body.accepted!=e.amount and not body.reason.strip():fail('Loại hoặc điều chỉnh khoản chi cần lý do',422)
    e.accepted=body.accepted;e.review_reason=body.reason;e.reviewed_by=user.id;e.review_status='accepted' if body.accepted==e.amount else 'rejected' if body.accepted==0 else 'partial'
    history(db,case,user,'expense_reviewed',{'expense_id':e.id,'accepted':money(e.accepted),'reason':body.reason});db.commit();return serialize(db,case,True)

@router.post('/cases/{case_id}/transactions')
def transaction(case_id:int,body:TransactionInput,db=Depends(db_session),user=Depends(current_user)):
    case=allowed(db,user,case_id,True)
    old=db.scalar(select(TravelTransaction).where(TravelTransaction.case_id==case.id,TravelTransaction.request_key==body.request_key))
    if old:
        if old.actor_id!=user.id or (old.kind,old.amount,old.paid_on,old.method,old.reference)!=(body.kind,body.amount,body.paid_on,body.method,body.reference):fail('Mã yêu cầu đã được dùng cho giao dịch khác')
        return serialize(db,case,True)
    if body.paid_on>now().astimezone(sla.TZ).date():fail('Ngày giao dịch không thể ở tương lai',422)
    if not body.reference.strip() or not body.method.strip():fail('Cần phương thức và tham chiếu giao dịch thực tế',422)
    if db.scalar(select(TravelTransaction.id).where(TravelTransaction.case_id==case.id,TravelTransaction.kind==body.kind,TravelTransaction.reference==body.reference)):
        fail('Tham chiếu giao dịch này đã được ghi nhận; không ghi hai lần')
    t=totals(db,case)
    if body.kind=='disbursement':
        if user.role!='accountant' or user.id==case.owner_id:fail('Chỉ kế toán cấp tiền',403)
        if case.status not in ('advance_approved','disbursed','received'):fail('Tạm ứng chưa được duyệt hoặc đang quyết toán')
        if body.amount+Decimal(t['issued'])>case.approved:fail('Không cấp vượt số tiền Admin đã duyệt')
        case.status='disbursed';recipients=['employee']
    elif body.kind=='return_declaration':
        if user.role!='employee' or case.status!='settlement_approved':fail('Chỉ khai báo hoàn ứng sau khi quyết toán được duyệt',403)
        if body.amount>Decimal(t['refund_declaration_available']):fail('Không còn nghĩa vụ hoàn ứng chưa khai báo hoặc số tiền vượt nghĩa vụ còn lại')
        recipients=['accountant']
    elif body.kind in ('refund','supplement'):
        if user.role!='accountant' or user.id==case.owner_id:fail('Chỉ kế toán xác nhận giao dịch thực tế',403)
        if case.status!='settlement_approved':fail('Quyết toán chưa được Admin phê duyệt')
        required=Decimal(t['refund_required' if body.kind=='refund' else 'supplement_required'])
        paid=Decimal(t['refund_paid' if body.kind=='refund' else 'supplement_paid'])
        if body.amount+paid>required:fail('Giao dịch vượt nghĩa vụ quyết toán đã duyệt')
        recipients=['employee']
    else:fail('Loại giao dịch không hợp lệ',422)
    entry=TravelTransaction(case_id=case.id,actor_id=user.id,**body.model_dump());db.add(entry);db.flush()
    history(db,case,user,'transaction_recorded',{'transaction_id':entry.id,'kind':entry.kind,'amount':money(entry.amount)})
    notice(db,case,recipients,'Tạm ứng đã cấp, vui lòng xác nhận nhận tiền' if body.kind=='disbursement' else 'Đã ghi nhận giao dịch hoàn ứng/quyết toán')
    db.commit();return serialize(db,case,True)

@router.post('/cases/{case_id}/transactions/{transaction_id}/receive')
def receive(case_id:int,transaction_id:int,db=Depends(db_session),user=Depends(require_roles('employee'))):
    case=allowed(db,user,case_id,True);t=db.get(TravelTransaction,transaction_id)
    if not t or t.case_id!=case.id or t.kind!='disbursement':fail('Chưa có giao dịch cấp tiền phù hợp',404)
    if t.received_at:fail('Giao dịch đã được xác nhận nhận tiền')
    if case.status!='disbursed':fail('Không thể xác nhận ở bước này')
    t.received_at=now();db.flush()
    if all(x.received_at for x in txs(db,case) if x.kind=='disbursement'):case.status='received'
    history(db,case,user,'money_received',{'transaction_id':t.id});notice(db,case,['accountant'],'Nhân viên đã xác nhận nhận tiền tạm ứng')
    db.commit();return serialize(db,case,True)

@router.post('/cases/{case_id}/evidence')
async def evidence(case_id:int,file:UploadFile=File(...),expense_id:int|None=None,transaction_id:int|None=None,db=Depends(db_session),user=Depends(current_user)):
    case=allowed(db,user,case_id,True)
    if case.status=='closed':fail('Hồ sơ đã đóng')
    if expense_id and transaction_id:fail('Chỉ liên kết một khoản chi hoặc giao dịch',422)
    if user.role=='employee':
        if case.status not in EDITABLE|{'settlement_approved'}:fail('Chỉ bổ sung chứng từ sau khi xác nhận nhận tiền hoặc khi hồ sơ được trả về',403)
        if case.status=='settlement_approved':
            t=db.get(TravelTransaction,transaction_id) if transaction_id else None
            balance=totals(db,case)
            if expense_id or not t or t.case_id!=case.id or t.actor_id!=user.id or t.kind!='return_declaration' or Decimal(balance['refund_required'])<=Decimal(balance['refund_paid']):
                fail('Chỉ đính kèm bằng chứng hoàn ứng của bạn khi còn nghĩa vụ hoàn ứng',403)
    else:
        t=db.get(TravelTransaction,transaction_id) if transaction_id else None
        allowed_kinds={'disbursement'} if case.status in ('disbursed','received') else {'refund','supplement'} if case.status=='settlement_approved' else set()
        if user.role!='accountant' or user.id==case.owner_id or expense_id or not t or t.case_id!=case.id or t.actor_id!=user.id or t.kind not in allowed_kinds:
            fail('Chỉ kế toán đính kèm bằng chứng cho giao dịch do chính mình ghi nhận tại bước phù hợp',403)
    if expense_id:
        e=db.get(TravelExpense,expense_id)
        if not e or e.case_id!=case.id or e.deleted:fail('Khoản chi không thuộc hồ sơ',404)
    if transaction_id:
        t=db.get(TravelTransaction,transaction_id)
        if not t or t.case_id!=case.id:fail('Giao dịch không thuộc hồ sơ',404)
        if user.id!=t.actor_id and user.id!=case.owner_id:fail('Không được đính kèm thay người thực hiện giao dịch',403)
    data=await file.read(20*1024*1024+1);name=Path(file.filename or 'evidence').name[:255];ext=Path(name).suffix.lower()
    signatures={'.pdf':(b'%PDF','application/pdf'),'.jpg':(b'\xff\xd8','image/jpeg'),'.jpeg':(b'\xff\xd8','image/jpeg'),'.png':(b'\x89PNG\r\n\x1a\n','image/png')}
    if ext not in signatures or not data or len(data)>20*1024*1024 or not data.startswith(signatures[ext][0]):fail('Bằng chứng cần là PDF/JPG/PNG hợp lệ, tối đa 20 MB',422)
    checksum=hashlib.sha256(data).hexdigest()
    if db.scalar(select(TravelEvidence.id).where(TravelEvidence.case_id==case.id,TravelEvidence.checksum==checksum,TravelEvidence.expense_id==expense_id,TravelEvidence.transaction_id==transaction_id)):fail('Bằng chứng đã được đính kèm')
    db.add(TravelEvidence(case_id=case.id,expense_id=expense_id,transaction_id=transaction_id,filename=name,mime=signatures[ext][1],data=data,checksum=checksum,actor_id=user.id))
    history(db,case,user,'evidence_added',{'filename':name,'expense_id':expense_id,'transaction_id':transaction_id});db.commit();return serialize(db,case,True)

@router.get('/evidence/{evidence_id}')
def download_evidence(evidence_id:int,db=Depends(db_session),user=Depends(current_user)):
    e=db.get(TravelEvidence,evidence_id)
    if not e:fail('Không tìm thấy bằng chứng',404)
    allowed(db,user,e.case_id)
    return Response(e.data,media_type=e.mime,headers={'Content-Disposition':'attachment; filename="evidence'+Path(e.filename).suffix.lower()+'"','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})

def check_schedule_edit(db,schedule_id,changes=None):
    case=db.scalar(select(TravelCase).where(TravelCase.schedule_id==schedule_id))
    if changes and set(changes)<={'status'} and changes.get('status') in ('in_progress','completed'):return
    if case and case.approved is not None:fail('Lịch đã liên kết tạm ứng được duyệt; giữ nguyên thông tin chuyến đi và lịch sử')

def official_invoice_costs(db,invoice_rows):
    """Project accepted costs for analytics only; never mutate source invoices."""
    from types import SimpleNamespace
    eligible={e.invoice_id:e for e in db.scalars(select(TravelExpense).join(TravelCase).where(TravelExpense.invoice_id.is_not(None),TravelExpense.deleted.is_(False),TravelCase.status.in_(OFFICIAL)))}
    result=[]
    for invoice,file,owner,assignment in invoice_rows:
        e=eligible.get(invoice.id)
        if e:
            values={column.key:getattr(invoice,column.key) for column in Invoice.__table__.columns}
            values.update(total_amount=e.accepted,approval_status='approved',_travel_official=True)
            if e.accepted!=invoice.total_amount:values.update(vat_amount=None,vat_rate=None,subtotal=None)
            invoice=SimpleNamespace(**values)
            assignment=SimpleNamespace(category=e.category)
        result.append((invoice,file,owner,assignment))
    return result

def manual_budget_cost(db,budget,user):
    if budget.currency!='VND':return Decimal('0')
    q=select(TravelExpense.amount,TravelExpense.accepted).join(TravelCase).join(User,User.id==TravelCase.owner_id).where(TravelExpense.invoice_id.is_(None),TravelExpense.deleted.is_(False),TravelCase.status.in_(OFFICIAL),TravelExpense.occurred_on>=budget.starts_on,TravelExpense.occurred_on<=budget.ends_on)
    if user.role=='employee':q=q.where(TravelCase.owner_id==user.id)
    if budget.team:q=q.where(User.team==budget.team)
    if budget.category:q=q.where(TravelExpense.category==budget.category)
    return sum((accepted for amount,accepted in db.execute(q) if accepted is not None),Decimal('0'))

def invoice_locked(db,invoice_id):
    return db.scalar(select(TravelExpense.id).join(TravelCase).where(TravelExpense.invoice_id==invoice_id,TravelExpense.deleted.is_(False),TravelCase.status.not_in(EDITABLE))) is not None

def sweep(db):
    """Called by the existing SLA scheduler with its transaction-wide lock."""
    for cycle,case in db.execute(select(TravelSLA,TravelCase).join(TravelCase,TravelCase.id==TravelSLA.case_id).where(TravelSLA.processed_at.is_(None),TravelCase.status.in_(['settlement_submitted','settlement_reviewed']))):
        status=sla.serialize(cycle)['status']
        if status not in ('due_soon','overdue'):continue
        key=f'travel-sla:{cycle.id}:{status}:{case.status}'
        if db.scalar(select(TravelHistory.id).where(TravelHistory.event_key==key)):continue
        roles=['accountant'] if case.status=='settlement_submitted' else ['admin']
        if status=='overdue' and 'admin' not in roles:roles.append('admin')
        notice(db,case,roles,'Quyết toán quá hạn phê duyệt' if status=='overdue' else 'Quyết toán sắp đến hạn phê duyệt')
        db.add(TravelHistory(case_id=case.id,action='sla_'+status,payload={'cycle_id':cycle.id},event_key=key))

@router.get('/summary')
def summary(starts:date|None=None,ends:date|None=None,employee_id:int|None=None,team:str='',db=Depends(db_session),user=Depends(current_user)):
    data=cases('',employee_id,team,starts,ends,db,user)
    total=lambda key:money(sum((Decimal(c['totals'][key]) for c in data if c['totals'][key] is not None),Decimal('0')))
    return {'issued':total('issued'),'received':total('received'),'accepted':total('accepted'),'refund_paid':total('refund_paid'),
        'supplement_paid':total('supplement_paid'),'unsettled_advance':money(sum((max(Decimal(c['totals']['issued'])-Decimal(c['totals']['refund_paid']),0) for c in data if c['status']!='closed'),Decimal('0'))),
        'unsettled_basis':'Tiền thực cấp trừ hoàn ứng đã xác nhận của hồ sơ chưa đóng, bao gồm khoản chưa xác nhận nhận tiền.',
        'open_cases':sum(c['status']!='closed' for c in data),'awaiting_review_cases':sum(c['status'] in ('advance_submitted','settlement_submitted','settlement_reviewed') for c in data),'closed_cases':sum(c['status']=='closed' for c in data),'currency':'VND','cases':data,
        'accounting_note':'Tạm ứng là khoản phải thu, hoàn ứng không phải doanh thu. Chi phí chỉ chính thức sau khi Admin duyệt; không cộng lại hóa đơn đã có trong báo cáo hiện tại.'}

@router.get('/export')
def export(starts:date|None=None,ends:date|None=None,employee_id:int|None=None,team:str='',db=Depends(db_session),user=Depends(current_user)):
    from openpyxl import Workbook
    from .report_workbook import report_sheet,append_report_row
    from .main import excel_text
    wb=Workbook();ws=wb.active;ws.title='Tam ung va quyet toan'
    ws.append(['Hồ sơ','Nhân viên','Chuyến công tác','Trạng thái','Đã cấp','Đã nhận','Chi phí khai báo','Chi phí được duyệt','Đã hoàn ứng','Đã thanh toán bổ sung','Còn phải xử lý'])
    def exact(value):
        if value is None:return None
        number=Decimal(value)
        return number if len(number.as_tuple().digits)<=15 else str(value)
    for c in cases('',employee_id,team,starts,ends,db,user):
        t=c['totals'];ws.append([c['id'],excel_text(c['employee_name']),excel_text(c['schedule']['title']),STATUS_LABELS[c['status']]]+[exact(t[k]) for k in ('issued','received','declared','accepted','refund_paid','supplement_paid','remaining')])
    for row in ws.iter_rows(min_row=2,min_col=5):
        for cell in row:cell.number_format='#,##0.00'
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    from openpyxl.utils import get_column_letter
    for i in range(1,12):ws.column_dimensions[get_column_letter(i)].width=25
    out=BytesIO();wb.save(out)
    return Response(out.getvalue(),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':'attachment; filename="travel-settlement.xlsx"'})

def chat_answer(db,user,question,context=None):
    q=fold(question)
    if user.role not in ('employee','accountant','admin'):fail('Không có quyền truy vấn hồ sơ',403)
    from . import finance_chat
    import re
    from .chatbot_queries import _period,period_bounds
    match=re.search(r'(?:ho so|chuyen cong tac|chuyen)\s*#?(\d+)\b',q)
    deictic=any(x in q for x in ('chuyen nay','chuyen cong tac nay','ho so nay'))
    selected_id=int(match.group(1)) if match else (context or {}).get('travel_case_id') if deictic else None
    selected=allowed(db,user,selected_id) if selected_id else None
    if deictic and selected is None:return 'Chưa xác định được chuyến công tác đang nói tới. Bạn hãy nêu số hồ sơ, ví dụ “quyết toán hồ sơ #12”.'
    # Query only local data; no travel financial details are sent to Gemini.
    period=_period(question);start=end=None
    if period:
        try:start,end=period_bounds(period)
        except (ValueError,TypeError):pass
    # Expense questions use occurrence dates, not dates of case creation.
    if period and any(x in q for x in ('chi phi','da chi')):
        query=select(TravelExpense,TravelCase).join(TravelCase).where(TravelExpense.deleted.is_(False))
        if selected:query=query.where(TravelCase.id==selected.id)
        if user.role=='employee':query=query.where(TravelCase.owner_id==user.id)
        if start:query=query.where(TravelExpense.occurred_on>=start)
        if end:query=query.where(TravelExpense.occurred_on<=end)
        expenses=db.execute(query).all()
        declared=sum((e.amount for e,c in expenses),Decimal('0'))
        accepted=sum((e.accepted for e,c in expenses if c.status in OFFICIAL and e.accepted is not None),Decimal('0'))
        return f"Theo ngày phát sinh khoản chi trong kỳ được hỏi: đã khai báo {finance_chat.amount(declared,'VND')}; chi phí đã được Admin duyệt {finance_chat.amount(accepted,'VND')}; {len(expenses)} khoản chi. Không tính tiền tạm ứng thành chi phí và không cộng lại hóa đơn đã liên kết."
    result=summary(start,end,None,'',db,user)
    if selected:
        items=[serialize(db,selected)]
    else:items=result['cases']
    if not items:return 'Chưa có hồ sơ tạm ứng/quyết toán trong phạm vi quyền và thời gian được hỏi.'
    amount=lambda key:finance_chat.amount(sum((Decimal(c['totals'][key]) for c in items if c['totals'][key] is not None),Decimal('0')),'VND')
    answer=f"Có {len(items)} hồ sơ trong phạm vi được phép. Đã nhận tạm ứng: {amount('received')}; chi phí khai báo: {amount('declared')}; chi phí đã được Admin duyệt: {amount('accepted')}; hoàn ứng dự kiến: {amount('expected_refund')}; đã hoàn thực tế: {amount('refund_paid')}."
    answer+='\n'+'\n'.join(f"- Hồ sơ #{c['id']} · {c['schedule']['title']} · {STATUS_LABELS[c['status']]} · Chênh lệch chưa xử lý: "+(finance_chat.amount(c['totals']['remaining'],'VND') if c['totals']['remaining'] is not None else 'chưa có quyết toán chính thức') for c in items)
    return answer+'\nTạm ứng không phải chi phí đã duyệt; dự kiến không thay thế kết quả phê duyệt.'
