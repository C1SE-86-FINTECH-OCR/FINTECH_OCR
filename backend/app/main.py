from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timezone, date
from decimal import Decimal
from zoneinfo import ZoneInfo
from io import BytesIO
from pathlib import Path
from uuid import uuid4
from collections import Counter,defaultdict
from math import isfinite
import hashlib, re, json, unicodedata, time
import logging
from copy import copy
from weakref import WeakKeyDictionary
import jwt
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Query, Body, Response, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse,StreamingResponse,JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import bindparam, inspect as sa_inspect, select,func,desc,text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from openpyxl import Workbook
from .core import Base,engine,db_session,current_user,require_roles,settings,hash_password,verify_password,make_token,bearer,storage_dir,SessionLocal
from .models import *
from .invoice_search import apply_invoice_search, normalize_search
from .extraction import text_from_file,extract_fields,extract_line_items,validate
from .risk_checks import assess_invoice_risks
from . import gemini_chat
from . import chatbot_queries

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    # Keep schema creation confined to the local SQLite development database.
    # PostgreSQL schemas are managed explicitly; application startup must not
    # issue DDL against either the main or isolated PostgreSQL database.
    if settings.app_env == 'development' and settings.database_url.startswith('sqlite'):
        Base.metadata.create_all(bind=engine)
    storage_dir()
    yield
app=FastAPI(title='FINTECH OCR API',version='0.1.0',lifespan=lifespan,description='API bản MVP của C1SE.86; AI provider và tra cứu thuế tự động chưa tích hợp')
app.add_middleware(CORSMiddleware,allow_origins=[s.strip() for s in settings.cors_origins.split(',')],allow_methods=['*'],allow_headers=['*'],allow_credentials=True)

_OPTIONAL_PHASE2_COLUMNS={
    'invoices':{'submitted_at','source_type'},
    'invoice_files':{'storage_url'},
    'invoice_lookups':{'query_snapshot','notes'},
    'notifications':{'type','read_at'},
    'schedules':{'start_date','end_date','created_at','updated_at'},
}
_SCHEMA_COLUMN_CACHE=WeakKeyDictionary()

def _phase2_has_column(db,table,column):
    if column not in _OPTIONAL_PHASE2_COLUMNS.get(table,set()) and not (table=='schedules' and column in {'start_date','end_date','created_at','updated_at'}):
        raise ValueError(f'Unsupported optional schema column: {table}.{column}')
    bind=db.get_bind()
    cached=_SCHEMA_COLUMN_CACHE.setdefault(bind,{})
    if table not in cached:
        # Inspect through the Session's active connection. A separate Engine
        # connection can roll back an uncommitted SQLite StaticPool transaction.
        cached[table]={entry['name'] for entry in sa_inspect(db.connection()).get_columns(table)}
    return column in cached[table]

def _phase2_write_optional(db,table,row_id,values):
    available={key:value for key,value in values.items() if _phase2_has_column(db,table,key)}
    if not available:return False
    params={'phase2_row_id':row_id}
    assignments=[]
    for column,value in available.items():
        if column=='query_snapshot':
            params[column]=json.dumps(value,ensure_ascii=False)
            expression=f'CAST(:{column} AS jsonb)' if db.get_bind().dialect.name=='postgresql' else f':{column}'
        else:
            params[column]=value
            expression=f':{column}'
        assignments.append(f'{column}={expression}')
    db.execute(text(f"UPDATE {table} SET {','.join(assignments)} WHERE id=:phase2_row_id"),params)
    return True

def _phase2_read_optional(db,table,row_id,column):
    if not _phase2_has_column(db,table,column):return None
    return db.execute(text(f'SELECT {column} FROM {table} WHERE id=:phase2_row_id'),{'phase2_row_id':row_id}).scalar_one_or_none()

def safe_validation_value(value):
    if isinstance(value,float) and not isfinite(value):return 'non-finite number'
    if isinstance(value,dict):return {key:safe_validation_value(item) for key,item in value.items()}
    if isinstance(value,(list,tuple)):return [safe_validation_value(item) for item in value]
    return value

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request,exc):
    return JSONResponse(status_code=422,content=jsonable_encoder({'detail':safe_validation_value(exc.errors())}))

def fail(message:str,status=400):raise HTTPException(status_code=status,detail=message)
def ser(u):return {'id':u.id,'full_name':u.full_name,'email':u.email,'role':u.role,'status':u.status,'last_login_at':u.last_login_at.isoformat() if u.last_login_at else None}
def profile_ser(u):return {**ser(u),'phone':u.phone,'team':u.team,'employee_code':u.employee_code,'avatar_url':f'/profile/avatar?v={u.updated_at.isoformat() if u.updated_at else u.id}' if u.avatar_data else None}
def decimal(v):return float(v) if v is not None else None
def excel_text(v):
    if v is None:return ''
    value=str(v)
    # Neutralize control characters Excel may ignore before formula parsing.
    value=''.join(' ' if char in '\t\r\n' else '' if unicodedata.category(char) in ('Cc','Cf') else char for char in value)
    if value.lstrip().startswith(('=','+','-','@')):return "'"+value
    return value
def inv_ser(i,db,details=False):
    f=i.source_file
    source_type=_phase2_read_optional(db,'invoices',i.id,'source_type')
    payload={'id':i.id,'file_id':i.file_id,'filename':f.original_filename,'uploaded_by':f.uploaded_by,'invoice_number':i.invoice_number,'invoice_symbol':i.invoice_symbol,'invoice_date':i.invoice_date.isoformat() if i.invoice_date else None,'seller_name':i.seller_name,'seller_tax_code':i.seller_tax_code,'buyer_name':i.buyer_name,'buyer_tax_code':i.buyer_tax_code,'currency':i.currency,'subtotal':decimal(i.subtotal),'vat_rate':decimal(i.vat_rate),'vat_amount':decimal(i.vat_amount),'total_amount':decimal(i.total_amount),'confidence_score':i.confidence_score,'validation_status':i.validation_status,'approval_status':i.approval_status,'lookup_status':i.lookup_status,'document_type':i.document_type,'source_type':source_type,'qr_url':i.qr_url,'created_at':i.created_at.isoformat() if i.created_at else None,'updated_at':i.updated_at.isoformat() if i.updated_at else None}
    if details:
        payload['items']=[{'id':x.id,'line_no':x.line_no,'description':x.description,'unit':x.unit,'quantity':decimal(x.quantity),'unit_price':decimal(x.unit_price),'amount':decimal(x.amount)} for x in db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id==i.id).order_by(InvoiceItem.line_no)).all()]
        # Only show findings from the most recent validation run. Older failures
        # remain in validation_results for audit/history; they are not current warnings.
        latest_round=db.scalar(
            select(func.max(ValidationResult.validation_round)).where(
                ValidationResult.invoice_id==i.id
            )
        )
        checks=(
            db.scalars(
                select(ValidationResult)
                .where(
                    ValidationResult.invoice_id==i.id,
                    ValidationResult.validation_round==latest_round,
                )
                .order_by(ValidationResult.id)
            ).all()
            if latest_round is not None else []
        )
        payload['warnings']=[
            {'rule':v.rule_code,'message':v.message,'passed':v.passed}
            for v in checks if not v.passed
        ][:8]
        payload['history']=[{'action':x.action,'reason':x.reason,'created_at':x.created_at.isoformat(),'by':x.action_by} for x in db.scalars(select(InvoiceApproval).where(InvoiceApproval.invoice_id==i.id).order_by(InvoiceApproval.id)).all()]
        submitted_at=_phase2_read_optional(db,'invoices',i.id,'submitted_at')
        if submitted_at is None:
            submitted_at=db.scalar(select(InvoiceApproval.created_at).where(InvoiceApproval.invoice_id==i.id,InvoiceApproval.action=='submitted').order_by(desc(InvoiceApproval.id)).limit(1))
        payload['submitted_at']=submitted_at.isoformat() if hasattr(submitted_at,'isoformat') else str(submitted_at) if submitted_at else None
    return payload

def invoice_q(db,user):
    q=select(Invoice).join(InvoiceFile,Invoice.file_id==InvoiceFile.id)
    return q if user.role in ('admin','accountant') else q.where(InvoiceFile.uploaded_by==user.id)
def invoice_allowed(db,user,invoice_id):
    obj=db.scalar(invoice_q(db,user).where(Invoice.id==invoice_id))
    if not obj:fail('KhÃ´ng tÃ¬m tháº¥y hÃ³a Ä‘Æ¡n hoáº·c báº¡n khÃ´ng cÃ³ quyá»n xem',404)
    return obj
def audit(db,actor,action,etype,eid):db.add(AuditLog(actor_id=actor,action=action,entity_type=etype,entity_id=eid))
def notify(db,recipient,title,message,invoice_id=None,schedule_id=None,event_type='legacy'):
    item=Notification(user_id=recipient,title=title,message=message,invoice_id=invoice_id,schedule_id=schedule_id)
    db.add(item);db.flush()
    _phase2_write_optional(db,'notifications',item.id,{'type':event_type})
    return item
def validators(db,i):
    # Each validation run gets a unique round, regardless of the number of rules.
    # Do not derive the round from row-count/5: rule sets may vary between runs.
    latest_round=db.scalar(
        select(func.max(ValidationResult.validation_round)).where(
            ValidationResult.invoice_id==i.id
        )
    )
    round_no=(latest_round or 0)+1
    db.flush()
    items=db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id==i.id).order_by(InvoiceItem.line_no)).all()
    results=validate(i,items)
    for code,passed,msg in results:
        db.add(ValidationResult(invoice_id=i.id,validation_round=round_no,rule_code=code,passed=passed,severity='warning',message=msg if not passed else 'OK'))
    i.validation_status='valid' if all(ok for _,ok,_ in results) else 'needs_review'

class LoginBody(BaseModel):
    email:str
    password:str
class NewUser(BaseModel):
    full_name:str=Field(min_length=2,max_length=150)
    email:EmailStr
    password:str=Field(min_length=8,max_length=128)
    role:str
    status:str=Field(default='active',pattern='^(active|disabled)$')
class UpdateUser(BaseModel):
    email:EmailStr|None=None
    full_name:str|None=Field(default=None,min_length=2,max_length=150)
    role:str|None=None
    status:str|None=None
    @field_validator('full_name','email','role','status',mode='before')
    @classmethod
    def reject_null_patch_values(cls,value):
        if value is None:raise ValueError('Trường cập nhật không được để trống')
        return value
class InvoiceItemInput(BaseModel):
    description:str=Field(min_length=1,max_length=2000)
    unit:str|None=Field(default=None,max_length=30)
    quantity:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    unit_price:float|None=Field(default=None,ge=0,allow_inf_nan=False)
    amount:float=Field(ge=0,allow_inf_nan=False)
    @field_validator('description')
    @classmethod
    def trim_description(cls,value):
        value=value.strip()
        if not value:raise ValueError('Mô tả không được để trống')
        return value
class UpdateInvoice(BaseModel):
    invoice_number:str|None=None
    invoice_symbol:str|None=None
    invoice_date:date|None=None
    seller_name:str|None=None
    seller_tax_code:str|None=None
    buyer_name:str|None=None
    buyer_tax_code:str|None=None
    subtotal:float|None=Field(default=None,allow_inf_nan=False)
    vat_rate:float|None=Field(default=None,allow_inf_nan=False)
    vat_amount:float|None=Field(default=None,allow_inf_nan=False)
    total_amount:float|None=Field(default=None,allow_inf_nan=False)
    items:list[InvoiceItemInput]|None=None
    @field_validator('items',mode='before')
    @classmethod
    def reject_null_items(cls,value):
        if value is None:raise ValueError('Danh sách mặt hàng không được để trống; cần gửi dạng danh sách')
        return value
class Decision(BaseModel):
    action:str
    reason:str|None=None
class LookupInput(BaseModel):
    result:str
    note:str|None=None
class ScheduleInput(BaseModel):
    title:str=Field(min_length=1,max_length=255)
    destination:str=Field(min_length=1,max_length=255)
    starts_at:datetime
    ends_at:datetime
    assigned_to:int
    notes:str|None=Field(default=None,max_length=5000)
class ScheduleEdit(BaseModel):
    title:str|None=Field(default=None,min_length=1,max_length=255)
    destination:str|None=Field(default=None,min_length=1,max_length=255)
    starts_at:datetime|None=None
    ends_at:datetime|None=None
    assigned_to:int|None=None
    notes:str|None=Field(default=None,max_length=5000)
    status:str|None=None
class ChatInput(BaseModel):
    question:str=Field(default='',max_length=1000)
    conversation_id:int|None=Field(default=None,gt=0)
    image_base64:str|None=None
class ProfileEdit(BaseModel):
    full_name:str=Field(min_length=2,max_length=150)
    phone:str|None=Field(default=None,max_length=30)
    team:str|None=Field(default=None,max_length=120)
    @field_validator('full_name')
    @classmethod
    def trim_full_name(cls,value):
        value=value.strip()
        if len(value)<2:raise ValueError('Họ tên phải có ít nhất 2 ký tự')
        return value
    @field_validator('phone')
    @classmethod
    def validate_phone(cls,value):
        if value is not None:
            value=value.strip()
            if value and not re.fullmatch(r'[+()\-\d .]{7,30}',value):raise ValueError('Số điện thoại không hợp lệ')
            return value or None
        return None
    @field_validator('team')
    @classmethod
    def trim_team(cls,value):return (value.strip() or None) if value is not None else None
class PasswordEdit(BaseModel):
    current_password:str
    new_password:str=Field(min_length=8,max_length=128)
    @field_validator('new_password')
    @classmethod
    def strong_password(cls,value):
        if not (re.search(r'[A-Z]',value) and re.search(r'[a-z]',value) and re.search(r'\d',value) and re.search(r'[^A-Za-z0-9]',value)):
            raise ValueError('Mật khẩu cần có chữ hoa, chữ thường, chữ số và ký tự đặc biệt')
        return value

@app.get('/health')
def health():return {'status':'ok','project':'FINTECH OCR','mode':settings.app_env}
@app.post('/api/v1/auth/login')
def login(data:LoginBody,db:Session=Depends(db_session)):
    user=db.scalar(select(User).where(func.lower(User.email)==data.email.strip().lower()))
    if not user or not verify_password(data.password,user.password_hash):fail('Email ho\u1eb7c m\u1eadt kh\u1ea9u kh\u00f4ng \u0111\u00fang',401)
    if user.status!='active':fail('T\u00e0i kho\u1ea3n \u0111\u00e3 b\u1ecb v\u00f4 hi\u1ec7u h\u00f3a',403)
    user.last_login_at=datetime.now(timezone.utc);db.commit()
    return {'access_token':make_token(user.id,user.role),'token_type':'bearer','user':profile_ser(user)}
@app.get('/api/v1/auth/me')
def me(user=Depends(current_user)):return profile_ser(user)
@app.post('/api/v1/auth/logout')
def logout(credentials:HTTPAuthorizationCredentials=Depends(bearer),user=Depends(current_user),db:Session=Depends(db_session)):
    claims=jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=['HS256'])
    db.add(RevokedToken(jti=claims['jti'],user_id=user.id,expires_at=datetime.fromtimestamp(claims['exp'],timezone.utc)));db.commit()
    return {'message':'Đã đăng xuất'}
@app.get('/api/v1/users')
def users(db:Session=Depends(db_session),user=Depends(require_roles('admin'))):return [ser(u) for u in db.scalars(select(User).order_by(User.id)).all()]
@app.get('/api/v1/directory/employees')
def directory_employees(db:Session=Depends(db_session),user=Depends(require_roles('admin','accountant'))):
    return [ser(u) for u in db.scalars(select(User).where(User.role.in_(['employee','accountant']),User.status=='active').order_by(User.full_name)).all()]

def employee_profile_data(target,viewer,scores):
    score=next(((index+1,row['completed']) for index,row in enumerate(scores) if row['user_id']==target.id),None)
    result={'id':target.id,'full_name':target.full_name,'role':target.role,'completed_trips':score[1] if score else 0,'rank':score[0] if score else None}
    if viewer.role in ('admin','accountant') or viewer.id==target.id:
        result.update(email=target.email,status=target.status)
    return result

@app.get('/api/v1/directory/profiles')
def search_employee_profiles(search:str='',limit:int=Query(5,ge=1,le=250),db:Session=Depends(db_session),user=Depends(current_user)):
    words=normalize_search(search).split()
    if not words:return []
    targets=db.scalars(select(User).where(User.role=='employee').order_by(User.full_name,User.id)).all()
    scores=ranking(period='all',db=db,user=user)
    return [employee_profile_data(target,user,scores) for target in targets if all(word in normalize_search(target.full_name) for word in words)][:limit]

@app.get('/api/v1/directory/profiles/{user_id}')
def employee_profile(user_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    target=db.get(User,user_id)
    if not target or target.role!='employee':fail('Không tìm thấy hồ sơ nhân viên',404)
    return employee_profile_data(target,user,ranking(period='all',db=db,user=user))

@app.post('/api/v1/users',status_code=201)
def add_user(body:NewUser,db:Session=Depends(db_session),user=Depends(require_roles('admin'))):
    if body.role not in ('admin','accountant','employee'):fail('Vai trò không hợp lệ')
    if db.scalar(select(User).where(func.lower(User.email)==body.email.lower())):fail('Email đã được sử dụng',409)
    u=User(full_name=body.full_name,email=body.email.lower(),password_hash=hash_password(body.password),role=body.role,status=body.status,created_by=user.id)
    db.add(u);db.flush();audit(db,user.id,'user.created','user',u.id);db.commit();return ser(u)
@app.patch('/api/v1/users/{user_id}')
def patch_user(user_id:int,body:UpdateUser,db:Session=Depends(db_session),user=Depends(require_roles('admin'))):
    u=db.get(User,user_id)
    if not u:fail('Không tìm thấy người dùng',404)
    if body.role and body.role not in ('admin','accountant','employee'):fail('Vai trò không hợp lệ')
    if body.status and body.status not in ('active','disabled'):fail('Trạng thái không hợp lệ')
    if u.id==user.id and (body.status=='disabled' or (body.role and body.role!='admin')):fail('Không thể tự vô hiệu hóa/hạ quyền tài khoản đang dùng')
    if body.email is not None:
        body.email=body.email.lower()
        if db.scalar(select(User).where(func.lower(User.email)==body.email,User.id!=user_id)):fail('Email đã được sử dụng',409)
    for k,v in body.model_dump(exclude_unset=True).items():setattr(u,k,v)
    audit(db,user.id,'user.updated','user',u.id);db.commit();return ser(u)
@app.delete('/api/v1/users/{user_id}',status_code=204)
def delete_user(user_id:int,db:Session=Depends(db_session),user=Depends(require_roles('admin'))):
    target=db.get(User,user_id)
    if not target:fail('Không tìm thấy người dùng',404)
    if target.id==user.id:fail('Bạn không thể xóa tài khoản đang sử dụng')
    # Serialize deletion with new uploads referencing this account in PostgreSQL.
    target=db.scalar(select(User).where(User.id==user_id).with_for_update())
    if not target:fail('Không tìm thấy người dùng',404)
    if db.scalar(select(InvoiceFile.id).where(InvoiceFile.uploaded_by==user_id).limit(1)):
        fail('Tài khoản có dữ liệu hóa đơn quan trọng, không thể xóa. Bạn có thể vô hiệu hóa tài khoản.',409)
    for model, column in ((Invoice,Invoice.reviewed_by),(InvoiceApproval,InvoiceApproval.action_by),
                          (InvoiceCorrection,InvoiceCorrection.corrected_by),(InvoiceLookup,InvoiceLookup.checked_by)):
        if db.scalar(select(model.id).where(column==user_id).limit(1)):
            fail('Tài khoản có lịch sử xử lý hóa đơn quan trọng, không thể xóa. Bạn có thể vô hiệu hóa tài khoản.',409)
    try:
        existing_tables=set(sa_inspect(db.connection()).get_table_names())
        def remove(model, condition):
            if model.__tablename__ in existing_tables:
                db.execute(model.__table__.delete().where(condition))
        # Remove personal data in dependency order; retain other users' schedules
        # and audit events without retaining a reference to a deleted identity.
        conversations=select(Conversation.id).where(Conversation.user_id==user_id)
        chat_ids=select(ChatMessage.id).where(ChatMessage.conversation_id.in_(conversations))
        remove(ChatMessageSource,ChatMessageSource.message_id.in_(chat_ids))
        remove(ChatMessage,ChatMessage.conversation_id.in_(conversations))
        remove(Conversation,Conversation.user_id==user_id)
        remove(DirectMessage,(DirectMessage.sender_id==user_id)|(DirectMessage.recipient_id==user_id))
        remove(InvoiceMessage,(InvoiceMessage.sender_id==user_id)|(InvoiceMessage.recipient_id==user_id))
        remove(Notification,Notification.user_id==user_id)
        remove(RevokedToken,RevokedToken.user_id==user_id)
        remove(Report,Report.requested_by==user_id)
        assigned=select(Schedule.id).where(Schedule.assigned_to==user_id)
        db.execute(Notification.__table__.update().where(Notification.schedule_id.in_(assigned)).values(schedule_id=None))
        remove(Schedule,Schedule.assigned_to==user_id)
        db.execute(Schedule.__table__.update().where(Schedule.created_by==user_id).values(created_by=user.id))
        db.execute(User.__table__.update().where(User.created_by==user_id).values(created_by=None))
        db.execute(AuditLog.__table__.update().where(AuditLog.actor_id==user_id).values(actor_id=None))
        audit(db,user.id,'user.deleted','user',target.id)
        db.delete(target)
        db.commit()
    except IntegrityError:
        db.rollback()
        fail('Tài khoản có dữ liệu liên quan. Vui lòng vô hiệu hóa thay vì xóa.',409)
    return Response(status_code=204)

@app.get('/api/v1/profile')
def profile(user=Depends(current_user)):return profile_ser(user)
@app.patch('/api/v1/profile')
def profile_edit(body:ProfileEdit,user=Depends(current_user),db:Session=Depends(db_session)):
    for field,value in body.model_dump(exclude_unset=True).items():setattr(user,field,value)
    db.commit();return profile_ser(user)
@app.post('/api/v1/profile/avatar')
async def profile_avatar_upload(file:UploadFile=File(...),user=Depends(current_user),db:Session=Depends(db_session)):
    filename=(file.filename or '').lower();mime=file.content_type or ''
    if not (filename.endswith(('.jpg','.jpeg')) and mime in ('image/jpeg','image/jpg') or filename.endswith('.png') and mime=='image/png'):
        fail('Ảnh đại diện chỉ chấp nhận JPG hoặc PNG')
    data=await file.read(5*1024*1024+1)
    if not data or len(data)>5*1024*1024:fail('Ảnh phải có dung lượng tối đa 5 MB')
    if mime=='image/png' and not data.startswith(b'\x89PNG\r\n\x1a\n'):fail('File PNG không hợp lệ')
    if mime in ('image/jpeg','image/jpg') and not data.startswith(b'\xff\xd8\xff'):fail('File JPG không hợp lệ')
    user.avatar_data=data;user.avatar_mime='image/png' if mime=='image/png' else 'image/jpeg';db.commit()
    return profile_ser(user)
@app.get('/api/v1/profile/avatar')
def profile_avatar(user=Depends(current_user)):
    if not user.avatar_data:fail('Chưa có ảnh đại diện',404)
    return Response(content=user.avatar_data,media_type=user.avatar_mime or 'image/jpeg',headers={'Cache-Control':'private, no-store, max-age=0'})
@app.put('/api/v1/profile/password')
def password_edit(body:PasswordEdit,user=Depends(current_user),db:Session=Depends(db_session)):
    if not verify_password(body.current_password,user.password_hash):fail('Mật khẩu hiện tại không đúng')
    if verify_password(body.new_password,user.password_hash):fail('Mật khẩu mới phải khác mật khẩu hiện tại')
    user.password_hash=hash_password(body.new_password);audit(db,user.id,'profile.password_changed','user',user.id);db.commit()
    return {'message':'Đã đổi mật khẩu'}
@app.get('/api/v1/invoices')
def invoices(search:str='',approval_status:str='',validation_status:str='',document_type:str='',invoice_date_from:date|None=None,invoice_date_to:date|None=None,limit:int=Query(250,ge=1,le=250),offset:int=Query(0,ge=0),db:Session=Depends(db_session),user=Depends(current_user)):
    query=invoice_q(db,user)
    if invoice_date_from and invoice_date_to and invoice_date_from>invoice_date_to:fail('Ngày bắt đầu không được sau ngày kết thúc',422)
    query,search_rank=apply_invoice_search(query,db,search)
    if approval_status:query=query.where(Invoice.approval_status==approval_status)
    if validation_status:query=query.where(Invoice.validation_status==validation_status)
    if document_type:query=query.where(Invoice.document_type==document_type)
    if invoice_date_from:query=query.where(Invoice.invoice_date>=invoice_date_from)
    if invoice_date_to:query=query.where(Invoice.invoice_date<=invoice_date_to)
    rows = db.execute(
        query.outerjoin(User, User.id == InvoiceFile.uploaded_by)
        .add_columns(User.full_name)
        .order_by(*([search_rank] if search_rank is not None else []), desc(Invoice.created_at), desc(Invoice.id))
        .offset(offset).limit(limit)
    ).all()
    return [dict(inv_ser(invoice, db), uploaded_by_name=name) for invoice, name in rows]


class InvoiceMessageInput(BaseModel):
    body: str = Field(max_length=2000)
    recipient_id: int | None = None


@app.get('/api/v1/messages')
def direct_messages(db: Session = Depends(db_session), user=Depends(current_user)):
    if user.role not in ('admin', 'accountant', 'employee'):
        fail('Bạn không có quyền truy cập tin nhắn', 403)
    peer_roles = {'admin': ('admin', 'accountant', 'employee'), 'accountant': ('admin', 'employee'), 'employee': ('admin', 'accountant')}[user.role]
    peers = db.scalars(select(User).where(User.role.in_(peer_roles), User.id != user.id).order_by(User.full_name, User.id)).all()
    messages = db.scalars(select(DirectMessage).where(
        (DirectMessage.sender_id == user.id) | (DirectMessage.recipient_id == user.id)
    ).order_by(DirectMessage.id)).all()
    return {
        'peers': [{'id': p.id, 'name': p.full_name, 'role': p.role, 'active': p.status == 'active'} for p in peers],
        'messages': [{'id': m.id, 'sender_id': m.sender_id, 'recipient_id': m.recipient_id,
                      'body': m.body, 'created_at': m.created_at.isoformat()} for m in messages],
    }


@app.post('/api/v1/messages', status_code=201)
def send_direct_message(body: InvoiceMessageInput, db: Session = Depends(db_session), user=Depends(current_user)):
    if user.role not in ('admin', 'accountant', 'employee'):
        fail('Bạn không có quyền gửi tin nhắn', 403)
    recipient = db.get(User, body.recipient_id) if body.recipient_id else None
    peer_roles = {'admin': ('admin', 'accountant', 'employee'), 'accountant': ('admin', 'employee'), 'employee': ('admin', 'accountant')}[user.role]
    if not recipient or recipient.id == user.id or recipient.role not in peer_roles or recipient.status != 'active':
        fail('Người nhận hiện không thể nhận tin nhắn', 409)
    message = body.body.strip()
    if not message:
        fail('Vui lòng nhập nội dung tin nhắn', 422)
    db.add(DirectMessage(sender_id=user.id, recipient_id=recipient.id, body=message))
    notify(db, recipient.id, 'Tin nhắn mới', f'{user.full_name} đã gửi tin nhắn cho bạn.', event_type='direct_message')
    db.commit()
    return {'sent': True}


INVOICE_MESSAGE_TITLE = 'Tin nhắn về hóa đơn'


def message_invoice(db, user, invoice_id):
    invoice = invoice_allowed(db, user, invoice_id)
    if invoice.approval_status == 'draft' or (
        user.role != 'accountant' and invoice.source_file.uploaded_by != user.id
    ):
        fail('Bạn không có quyền trao đổi về hóa đơn này', 403)
    return invoice


@app.get('/api/v1/invoices/{invoice_id}/messages')
def invoice_messages(invoice_id: int, db: Session = Depends(db_session), user=Depends(current_user)):
    invoice = message_invoice(db, user, invoice_id)
    messages = db.scalars(
        select(InvoiceMessage).where(
            InvoiceMessage.invoice_id == invoice.id,
            (InvoiceMessage.sender_id == user.id) | (InvoiceMessage.recipient_id == user.id),
        ).order_by(InvoiceMessage.id)
    ).all()
    peer_ids = {m.recipient_id if m.sender_id == user.id else m.sender_id for m in messages}
    if user.role == 'accountant' and invoice.source_file.uploaded_by != user.id:
        peer_ids.add(invoice.source_file.uploaded_by)
    peers = db.execute(
        select(User.id, User.full_name, User.status).where(User.id.in_(peer_ids)).order_by(User.full_name, User.id)
    ).all() if peer_ids else []
    return {
        'peers': [{'id': id, 'name': name, 'active': status == 'active'} for id, name, status in peers],
        'messages': [
            {'id': m.id, 'sender_id': m.sender_id, 'recipient_id': m.recipient_id,
             'body': m.body, 'created_at': m.created_at.isoformat()}
            for m in messages
        ],
    }


@app.post('/api/v1/invoices/{invoice_id}/messages', status_code=201)
def send_invoice_message(invoice_id: int, body: InvoiceMessageInput, db: Session = Depends(db_session), user=Depends(current_user)):
    invoice = message_invoice(db, user, invoice_id)
    uploader_id = invoice.source_file.uploaded_by
    message = body.body.strip()
    if not message:
        fail('Vui lòng nhập nội dung tin nhắn', 422)
    if user.id != uploader_id:
        recipient_id = uploader_id
    else:
        recipient_id = body.recipient_id
        if recipient_id is None:
            fail('Vui lòng chọn người nhận', 422)
        existing = db.scalar(select(InvoiceMessage.id).where(
            InvoiceMessage.invoice_id == invoice.id,
            InvoiceMessage.sender_id == recipient_id,
            InvoiceMessage.recipient_id == user.id,
        ).limit(1))
        if existing is None:
            fail('Chỉ có thể trả lời kế toán đã nhắn về hóa đơn này', 403)

    recipient = db.get(User, recipient_id)
    if not recipient or recipient.status != 'active' or (user.id == uploader_id and recipient.role != 'accountant'):
        fail('Người nhận hiện không thể nhận tin nhắn', 409)
    db.add(InvoiceMessage(invoice_id=invoice.id, sender_id=user.id, recipient_id=recipient.id, body=message))
    number = invoice.invoice_number or f'#{invoice.id}'
    notify(db, recipient.id, INVOICE_MESSAGE_TITLE, f'{user.full_name} đã gửi tin nhắn về hóa đơn {number}.',
           invoice_id=invoice.id, event_type='invoice_message')
    db.commit()
    return {'sent': True}


@app.get('/api/v1/invoices/{invoice_id}')
def invoice_detail(invoice_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    return inv_ser(invoice_allowed(db,user,invoice_id),db,True)
@app.get('/api/v1/invoices/{invoice_id}/lookups')
def invoice_lookup_history(invoice_id:int,limit:int=Query(100,ge=1,le=250),offset:int=Query(0,ge=0),db:Session=Depends(db_session),user=Depends(current_user)):
    invoice_allowed(db,user,invoice_id)
    rows=db.scalars(
        select(InvoiceLookup)
        .where(InvoiceLookup.invoice_id==invoice_id)
        .order_by(desc(InvoiceLookup.checked_at),desc(InvoiceLookup.id))
        .offset(offset)
        .limit(limit)
    ).all()
    history=[]
    for item in rows:
        notes=_phase2_read_optional(db,'invoice_lookups',item.id,'notes')
        snapshot=_phase2_read_optional(db,'invoice_lookups',item.id,'query_snapshot')
        if isinstance(snapshot,str):
            try:
                snapshot=json.loads(snapshot)
            except ValueError:
                snapshot=None
        reviewer=db.get(User,item.checked_by)
        history.append({
            'id':item.id,
            'invoice_id':item.invoice_id,
            'checked_by':item.checked_by,
            'checked_by_name':reviewer.full_name if reviewer else None,
            'result':item.result,
            'checked_at':item.checked_at.isoformat() if item.checked_at else None,
            'note':notes if notes is not None else item.note,
            'query_snapshot':snapshot,
        })
    return history

@app.get('/api/v1/invoices/{invoice_id}/corrections')
def invoice_correction_history(invoice_id:int,limit:int=Query(100,ge=1,le=250),offset:int=Query(0,ge=0),db:Session=Depends(db_session),user=Depends(current_user)):
    invoice_allowed(db,user,invoice_id)
    rows=db.scalars(
        select(InvoiceCorrection)
        .where(InvoiceCorrection.invoice_id==invoice_id)
        .order_by(InvoiceCorrection.corrected_at,InvoiceCorrection.id)
        .offset(offset)
        .limit(limit)
    ).all()
    return [{
        'id':item.id,
        'invoice_id':item.invoice_id,
        'field_name':item.field_name,
        'old_value':item.old_value,
        'new_value':item.new_value,
        'corrected_by':item.corrected_by,
        'corrected_at':item.corrected_at.isoformat() if item.corrected_at else None,
    } for item in rows]

@app.get('/api/v1/invoices/{invoice_id}/risk-assessment')
def invoice_risk_assessment(invoice_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    # Read-only advisory endpoint with the same access control as invoice detail.
    i=invoice_allowed(db,user,invoice_id)
    return assess_invoice_risks(db,i,role=user.role)

@app.get('/api/v1/invoices/{invoice_id}/file')
def invoice_file(invoice_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    i=invoice_allowed(db,user,invoice_id)
    p=(storage_dir()/i.source_file.storage_key).resolve()
    if not p.is_relative_to(storage_dir()) or not p.is_file():fail('File gốc chưa có',404)
    return FileResponse(p,filename=i.source_file.original_filename,media_type=i.source_file.mime_type)
@app.get('/api/v1/invoices/{invoice_id}/thumbnail')
def invoice_thumbnail(invoice_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    i=invoice_allowed(db,user,invoice_id)
    root=storage_dir();p=(root/i.source_file.storage_key).resolve()
    if not p.is_relative_to(root) or not p.is_file():fail('File gá»‘c chÆ°a cÃ³',404)
    extension=Path(i.source_file.original_filename or p.name).suffix.lower()
    headers={'Cache-Control':'private, max-age=300','X-Content-Type-Options':'nosniff'}
    if extension=='.xml':return JSONResponse({'kind':'xml'},headers=headers)
    if extension in ('.jpg','.jpeg','.png'):
        mime='image/png' if extension=='.png' else 'image/jpeg'
        return FileResponse(p,media_type=mime,headers=headers)
    if extension=='.pdf':
        import pymupdf
        with pymupdf.open(p) as document:
            if not document.page_count:fail('PDF khÃ´ng cÃ³ trang nÃ o',404)
            page=document.load_page(0)
            pixmap=page.get_pixmap(matrix=pymupdf.Matrix(2,2),alpha=False,annots=True)
            thumbnail=pixmap.tobytes('png')
        return Response(content=thumbnail,media_type='image/png',headers=headers)
    fail('Äá»‹nh dáº¡ng file khÃ´ng há»— trá»£ thumbnail',415)
@app.post('/api/v1/invoices/upload',status_code=201)
async def upload_invoice(file:UploadFile=File(...),db:Session=Depends(db_session),user=Depends(require_roles('employee'))):
    filename=Path(file.filename or 'invoice').name
    ext=Path(filename).suffix.lower().lstrip('.')
    mime={'pdf':'application/pdf','jpg':'image/jpeg','png':'image/png','xml':'application/xml'}
    if ext not in mime:fail('Chỉ chấp nhận PDF/JPG/PNG/XML')
    data=await file.read(settings.max_upload_mb*1024*1024+1)
    if not data or len(data)>settings.max_upload_mb*1024*1024:fail(f'File r\u1ed7ng ho\u1eb7c v\u01b0\u1ee3t gi\u1edbi h\u1ea1n {settings.max_upload_mb} MB')
    if ext=='pdf' and not data.startswith(b'%PDF'):fail('File PDF không hợp lệ')
    if ext=='png' and not data.startswith(b'\x89PNG\r\n\x1a\n'):fail('File PNG không hợp lệ')
    if ext=='jpg' and not data.startswith(b'\xff\xd8'):fail('File JPG không hợp lệ')
    safe_name=str(uuid4())+'.'+ext
    file_path=storage_dir()/safe_name
    try:
        file_path.write_bytes(data)
        f=InvoiceFile(uploaded_by=user.id,original_filename=filename,file_type=ext,mime_type=mime[ext],file_size_bytes=len(data),storage_key=safe_name,checksum_sha256=hashlib.sha256(data).hexdigest())
        db.add(f);db.flush()
        i=Invoice(file_id=f.id,document_type='unknown',lookup_status='not_checked',validation_status='needs_review')
        db.add(i);db.flush()
        _phase2_write_optional(db,'invoice_files',f.id,{'storage_url':f'/api/v1/invoices/{i.id}/file'})
        _phase2_write_optional(db,'invoices',i.id,{'source_type':'xml' if ext=='xml' else 'ocr'})
        raw,method='', 'not-processed';err=None
        try:
            raw,method=text_from_file(data,ext)
            extracted=extract_fields(raw,ext)
            for k,v in extracted.items():setattr(i,k,v)
            extracted_items=extract_line_items(data,ext,raw)
            for item in extracted_items:
                values={key:value for key,value in item.items() if key!='line_no'}
                db.add(InvoiceItem(invoice_id=i.id,line_no=item['line_no'],**values))
            if i.document_type=='bill':i.lookup_status='not_applicable'
        except Exception as ex:
            logger.exception("Invoice extraction failed (invoice_id=%s, file_type=%s)", i.id, ext)
            extracted={};extracted_items=[];err=str(ex)[:250];method='failed';i.validation_status='error'
        extraction_payload={**extracted,'items':extracted_items} if not err else extracted
        db.add(ExtractionRun(invoice_id=i.id,method=method,raw_text=raw,extracted_json=jsonable_encoder(extraction_payload),confidence_score=i.confidence_score,status='failed' if err else 'completed',error_message=err))
        if not err:validators(db,i)
        notify(db,user.id,'K\u1ebft qu\u1ea3 x\u1eed l\u00fd h\u00f3a \u0111\u01a1n',f'H\u00f3a \u0111\u01a1n #{i.id} \u0111\u00e3 x\u1eed l\u00fd; tr\u1ea1ng th\u00e1i ki\u1ec3m tra: {i.validation_status}',invoice_id=i.id,event_type='extraction_finished')
        audit(db,user.id,'invoice.uploaded','invoice',i.id);db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            persisted_file=db.scalar(select(InvoiceFile.id).where(InvoiceFile.storage_key==safe_name)) is not None
        except Exception:
            # If commit outcome cannot be confirmed, keep the file to avoid a
            # committed InvoiceFile pointing at a file we removed.
            persisted_file=True
        if not persisted_file:
            file_path.unlink(missing_ok=True)
        raise
    db.refresh(i)
    return inv_ser(i,db,True)
@app.post('/api/v1/invoices/upload/batch')
async def upload_invoice_batch(files:list[UploadFile]=File(...),db:Session=Depends(db_session),user=Depends(require_roles('employee'))):
    if not files:fail('Cáº§n chá»n Ã­t nháº¥t má»™t file')
    results=[]
    for uploaded_file in files:
        filename=Path(uploaded_file.filename or 'invoice').name
        try:
            invoice=await upload_invoice(uploaded_file,db,user)
            results.append({'filename':filename,'status':'created','http_status':201,'invoice':invoice})
        except HTTPException as ex:
            db.rollback()
            results.append({'filename':filename,'status':'rejected','http_status':ex.status_code,'detail':ex.detail})
    return {'total':len(results),'created':sum(r['status']=='created' for r in results),'rejected':sum(r['status']=='rejected' for r in results),'results':results}
@app.put('/api/v1/invoices/{invoice_id}')
def edit_invoice(invoice_id:int,body:UpdateInvoice,db:Session=Depends(db_session),user=Depends(require_roles('employee'))):
    i=invoice_allowed(db,user,invoice_id)
    if i.approval_status not in ('draft','rejected'):fail('Chỉ chỉnh sửa hóa đơn nháp hoặc đã bị từ chối')
    changes=body.model_dump(exclude_unset=True)
    for key,val in changes.items():
        if key=='items':continue
        old=getattr(i,key)
        if val!=old:
            db.add(InvoiceCorrection(invoice_id=i.id,field_name=key,old_value=str(old) if old is not None else None,new_value=str(val) if val is not None else None,corrected_by=user.id))
            setattr(i,key,val)
    items_were_sent='items' in changes
    if items_were_sent:
        existing={item.line_no:item for item in db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id==i.id).order_by(InvoiceItem.line_no)).all()}
        item_fields=('description','unit','quantity','unit_price','amount')
        for line_no,line in enumerate(body.items,start=1):
            values=line.model_dump()
            current=existing.pop(line_no,None)
            if current is None:
                db.add(InvoiceItem(invoice_id=i.id,line_no=line_no,**values))
                db.add(InvoiceCorrection(invoice_id=i.id,field_name=f'items[{line_no}]',old_value=None,new_value=json.dumps(values,ensure_ascii=False,sort_keys=True),corrected_by=user.id))
                continue
            for field in item_fields:
                old=getattr(current,field)
                new=values[field]
                if old!=new:
                    db.add(InvoiceCorrection(invoice_id=i.id,field_name=f'items[{line_no}].{field}',old_value=str(old) if old is not None else None,new_value=str(new) if new is not None else None,corrected_by=user.id))
                    setattr(current,field,new)
        for line_no,item in existing.items():
            old=json.dumps({field:(str(getattr(item,field)) if getattr(item,field) is not None else None) for field in item_fields},ensure_ascii=False,sort_keys=True)
            db.add(InvoiceCorrection(invoice_id=i.id,field_name=f'items[{line_no}]',old_value=old,new_value=None,corrected_by=user.id))
            db.delete(item)
    i.is_corrected=True
    if i.approval_status=='rejected':i.approval_status='draft'
    validators(db,i);audit(db,user.id,'invoice.corrected','invoice',i.id);db.commit();return inv_ser(i,db,True)
@app.post('/api/v1/invoices/{invoice_id}/submit')
def submit_invoice(invoice_id:int,db:Session=Depends(db_session),user=Depends(require_roles('employee'))):
    i=invoice_allowed(db,user,invoice_id)
    if i.approval_status not in ('draft','rejected'):fail('Chỉ được gửi hóa đơn đang nháp hoặc đã bị từ chối')
    if i.validation_status=='error':fail('Hóa đơn đang lỗi xử lý; cần kiểm tra trước khi gửi')
    i.approval_status='pending';submitted_at=datetime.now(timezone.utc);db.add(InvoiceApproval(invoice_id=i.id,action_by=user.id,action='submitted'))
    _phase2_write_optional(db,'invoices',i.id,{'submitted_at':submitted_at})
    for u in db.scalars(select(User).where(User.role.in_(['accountant','admin']),User.status=='active')).all():
        notify(db,u.id,'Hóa đơn chờ phê duyệt',f'Hóa đơn #{i.id} được gửi bởi {user.full_name}',invoice_id=i.id,event_type='invoice_submitted')
    audit(db,user.id,'invoice.submitted','invoice',i.id);db.commit();return inv_ser(i,db,True)
@app.post('/api/v1/invoices/{invoice_id}/approval')
def approve(invoice_id:int,body:Decision,db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    i=invoice_allowed(db,user,invoice_id)
    if i.approval_status!='pending':fail('HÃ³a Ä‘Æ¡n khÃ´ng á»Ÿ tráº¡ng thÃ¡i chá» duyá»‡t')
    if body.action not in ('approved','rejected'):fail('Chỉ có thể approved/rejected')
    if body.action=='rejected' and not (body.reason or '').strip():fail('Từ chối phải nhập lý do')
    i.approval_status=body.action;i.reviewed_by=user.id;i.reviewed_at=datetime.now(timezone.utc)
    db.add(InvoiceApproval(invoice_id=i.id,action_by=user.id,action=body.action,reason=body.reason))
    decision_label='đã được phê duyệt' if body.action=='approved' else 'bị từ chối'
    decision_message=f'Hóa đơn #{i.id} {decision_label}'
    if body.reason:decision_message+=f' – Lý do: {body.reason}'
    notify(db,i.source_file.uploaded_by,'Kết quả phê duyệt',decision_message,invoice_id=i.id,event_type='invoice_decision')
    audit(db,user.id,'invoice.'+body.action,'invoice',i.id);db.commit();return inv_ser(i,db,True)
@app.post('/api/v1/invoices/{invoice_id}/lookup')
def lookup(invoice_id:int,body:LookupInput,db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    i=invoice_allowed(db,user,invoice_id)
    if i.document_type!='einvoice':fail('Chỉ hóa đơn điện tử mới tra cứu thuế; bill kiểm tra thủ công')
    required={'invoice_number':i.invoice_number,'invoice_symbol':i.invoice_symbol,'seller_tax_code':i.seller_tax_code,'invoice_date':i.invoice_date,'total_amount':i.total_amount}
    missing=[field for field,value in required.items() if value is None or (isinstance(value,str) and not value.strip())]
    if missing:fail('Thiếu dữ liệu tra cứu: '+', '.join(missing))
    if body.result not in ('verified','mismatch','not_found'):fail('Kết quả tra cứu không hợp lệ')
    i.lookup_status=body.result
    lookup_record=InvoiceLookup(invoice_id=i.id,checked_by=user.id,result=body.result,note=body.note)
    db.add(lookup_record);db.flush()
    _phase2_write_optional(db,'invoice_lookups',lookup_record.id,{
        'notes':body.note,
        'query_snapshot':{
            'invoice_number':i.invoice_number,
            'invoice_symbol':i.invoice_symbol,
            'seller_tax_code':i.seller_tax_code,
            'invoice_date':i.invoice_date.isoformat(),
            'total_amount':str(i.total_amount),
        },
    })
    audit(db,user.id,'invoice.lookup_recorded','invoice',i.id);db.commit();return inv_ser(i,db,True)
@app.get('/api/v1/dashboard/summary')
def summary(invoice_date_from:date|None=None,invoice_date_to:date|None=None,db:Session=Depends(db_session),user=Depends(current_user)):
    if invoice_date_from and invoice_date_to and invoice_date_from>invoice_date_to:fail('Ngày bắt đầu không được sau ngày kết thúc',422)
    query=invoice_q(db,user)
    if invoice_date_from:query=query.where(Invoice.invoice_date>=invoice_date_from)
    if invoice_date_to:query=query.where(Invoice.invoice_date<=invoice_date_to)
    rows=db.scalars(query).all()
    monthly=defaultdict(lambda:{'vat_amount':Decimal('0'),'total_amount':Decimal('0'),'invoice_count':0})
    suppliers=defaultdict(lambda:{'invoice_count':0,'total_amount':Decimal('0')})
    business_timezone=ZoneInfo('Asia/Ho_Chi_Minh')
    for invoice in rows:
        if invoice.invoice_date:
            month=invoice.invoice_date.strftime('%Y-%m')
        else:
            created_at=invoice.created_at
            if created_at.tzinfo is None:
                created_at=created_at.replace(tzinfo=timezone.utc)
            month=created_at.astimezone(business_timezone).strftime('%Y-%m')
        vat_amount=Decimal(str(invoice.vat_amount)) if invoice.vat_amount is not None else Decimal('0')
        total_amount=Decimal(str(invoice.total_amount)) if invoice.total_amount is not None else Decimal('0')
        monthly[month]['vat_amount']+=vat_amount
        monthly[month]['total_amount']+=total_amount
        monthly[month]['invoice_count']+=1
        supplier=invoice.seller_name or '(Chưa xác định nhà cung cấp)'
        suppliers[supplier]['invoice_count']+=1
        suppliers[supplier]['total_amount']+=total_amount
    return {
        'total_invoices':len(rows),
        'valid':sum(i.validation_status=='valid' for i in rows),
        'needs_review':sum(i.validation_status=='needs_review' for i in rows),
        'error':sum(i.validation_status=='error' for i in rows),
        'approved':sum(i.approval_status=='approved' for i in rows),
        'pending':sum(i.approval_status=='pending' for i in rows),
        'rejected':sum(i.approval_status=='rejected' for i in rows),
        'draft':sum(i.approval_status=='draft' for i in rows),
        'total_amount':float(round(sum((Decimal(str(i.total_amount)) if i.total_amount is not None else Decimal('0') for i in rows),Decimal('0')),2)),
        'monthly':[{'month':month,'vat_amount':float(round(values['vat_amount'],2)),'total_amount':float(round(values['total_amount'],2)),'amount':float(round(values['total_amount'],2)),'invoice_count':values['invoice_count']} for month,values in sorted(monthly.items())],
        'suppliers':[{'supplier':name,'invoice_count':values['invoice_count'],'total_amount':float(round(values['total_amount'],2))} for name,values in sorted(suppliers.items(),key=lambda item:(-item[1]['total_amount'],item[0].casefold()))],
    }
@app.get('/api/v1/notifications')
def notifications(db:Session=Depends(db_session),user=Depends(current_user)):
    result=[]
    items=db.scalars(select(Notification).where(Notification.user_id==user.id).order_by(desc(Notification.id)).limit(100)).all()
    if not items:return result
    has_type=_phase2_has_column(db,'notifications','type')
    has_read_at=_phase2_has_column(db,'notifications','read_at')
    extra_columns=['id']+(['type'] if has_type else [])+(['read_at'] if has_read_at else [])
    placeholders=','.join(f':notification_id_{index}' for index in range(len(items)))
    params={f'notification_id_{index}':item.id for index,item in enumerate(items)}
    extra_rows=db.execute(text(f"SELECT {','.join(extra_columns)} FROM notifications WHERE id IN ({placeholders})"),params).all()
    extras={row[0]:row[1:] for row in extra_rows}
    for item in items:
        values=extras.get(item.id,())
        index=0
        event_type=values[index] if has_type and values[index] else 'legacy'
        if event_type == 'legacy' and item.invoice_id is not None and item.title == INVOICE_MESSAGE_TITLE:
            event_type = 'invoice_message'
        if event_type == 'legacy' and item.invoice_id is None and item.title == 'Tin nhắn mới':
            event_type = 'direct_message'
        index+=1 if has_type else 0
        read_at=values[index] if has_read_at else None
        result.append({'id':item.id,'title':item.title,'message':item.message,'type':event_type,'is_read':item.is_read,'invoice_id':item.invoice_id,'schedule_id':item.schedule_id,'created_at':item.created_at.isoformat() if item.created_at else None,'read_at':read_at.isoformat() if hasattr(read_at,'isoformat') else str(read_at) if read_at else None})
    return result
@app.get('/api/v1/notifications/unread-count')
def notifications_unread_count(db:Session=Depends(db_session),user=Depends(current_user)):
    count=db.scalar(select(func.count(Notification.id)).where(Notification.user_id==user.id,Notification.is_read==False)) or 0
    return {'count':count}
@app.patch('/api/v1/notifications/{notification_id}/read')
def read_notif(notification_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    n=db.get(Notification,notification_id)
    if not n or n.user_id!=user.id:fail('Không tìm thấy thông báo',404)
    if not n.is_read:
        n.is_read=True
        _phase2_write_optional(db,'notifications',n.id,{'read_at':datetime.now(timezone.utc)})
    db.commit();return {'ok':True}
@app.patch('/api/v1/notifications/read-all')
def read_all(db:Session=Depends(db_session),user=Depends(current_user)):
    now=datetime.now(timezone.utc)
    for n in db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.is_read==False)).all():
        n.is_read=True
        _phase2_write_optional(db,'notifications',n.id,{'read_at':now})
    db.commit();return {'ok':True}
@app.get('/api/v1/schedules')
def schedules(assigned_to:int|None=None,status:str='',db:Session=Depends(db_session),user=Depends(current_user)):
    q=select(Schedule).order_by(Schedule.starts_at)
    if user.role != 'admin':
        if assigned_to is not None and assigned_to != user.id:
            fail('Bạn chỉ được xem lịch công tác của mình', 403)
        q=q.where(Schedule.assigned_to == user.id)
    elif assigned_to is not None:
        q=q.where(Schedule.assigned_to == assigned_to)
    if status:
        if status not in ('planned','in_progress','completed','cancelled'):fail('Trạng thái lịch không hợp lệ',422)
        q=q.where(Schedule.status==status)
    return [schedule_ser(s,db) for s in db.scalars(q).all()]
@app.get('/api/v1/schedules/{schedule_id}')
def schedule_detail(schedule_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    s=db.get(Schedule,schedule_id)
    if not s:fail('Không tìm thấy lịch',404)
    if user.role != 'admin' and s.assigned_to != user.id:
        fail('Bạn chỉ được xem lịch công tác của mình',403)
    return schedule_ser(s,db)
def schedule_ser(s,db):
    u=db.get(User,s.assigned_to)
    creator=db.get(User,s.created_by)
    start=schedule_db_datetime(s.starts_at);end=schedule_db_datetime(s.ends_at)
    created=schedule_db_datetime(getattr(s,'created_at',None)) if getattr(s,'created_at',None) else None
    completed=schedule_db_datetime(s.completed_at) if s.completed_at else None
    return {'id':s.id,'title':s.title,'destination':s.destination,'starts_at':start.isoformat(),'ends_at':end.isoformat(),'start_date':(getattr(s,'start_date',None) or start.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()).isoformat(),'end_date':(getattr(s,'end_date',None) or end.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()).isoformat(),'assigned_to':s.assigned_to,'employee_name':u.full_name if u else '-','created_by':s.created_by,'created_by_name':creator.full_name if creator else '—','notes':getattr(s,'notes',None),'status':s.status,'completed_at':completed.isoformat() if completed else None,'created_at':created.isoformat() if created else None,'updated_at':getattr(s,'updated_at',None).isoformat() if getattr(s,'updated_at',None) else None}
def schedule_db_datetime(value):
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value
def schedule_datetime(value):
    return value if value.tzinfo is not None else value.replace(tzinfo=ZoneInfo('Asia/Ho_Chi_Minh'))
def ensure_schedule_available(db,assigned_to,starts_at,ends_at,exclude_id=None):
    q=select(Schedule.id).where(Schedule.assigned_to==assigned_to,Schedule.status!='cancelled',Schedule.starts_at<ends_at,Schedule.ends_at>starts_at)
    if exclude_id is not None:q=q.where(Schedule.id!=exclude_id)
    conflict=db.scalar(q.limit(1))
    if conflict:fail('Nhân viên đã có lịch công tác trùng thời gian. Hãy chọn khung giờ khác.',409)
@app.post('/api/v1/schedules',status_code=201)
def schedule_create(data:ScheduleInput,db:Session=Depends(db_session),user=Depends(current_user)):
    if user.role == 'accountant':
        fail('Kế toán chỉ có quyền xem lịch công tác, không có quyền tạo hoặc thay đổi lịch', 403)
    if user.role != 'admin':
        fail('Chỉ có quản trị viên mới có quyền tạo và phân lịch công tác', 403)
    employee=db.get(User,data.assigned_to)
    if not employee or employee.role not in ('employee','accountant') or employee.status!='active':fail('Chỉ có thể giao lịch cho nhân viên hoặc kế toán đang hoạt động')
    starts_at=schedule_datetime(data.starts_at);ends_at=schedule_datetime(data.ends_at)
    if ends_at<=starts_at:fail('Thời gian kết thúc phải sau thời gian bắt đầu')
    ensure_schedule_available(db,employee.id,starts_at,ends_at)
    values=data.model_dump();values['title']=data.title.strip();values['destination']=data.destination.strip()
    if not values['title'] or not values['destination']:fail('Tên chuyến đi và địa điểm không được để trống',422)
    values['starts_at']=starts_at;values['ends_at']=ends_at
    if _phase2_has_column(db,'schedules','start_date'):values['start_date']=starts_at.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    if _phase2_has_column(db,'schedules','end_date'):values['end_date']=ends_at.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    values['created_at']=datetime.now(timezone.utc)
    values['updated_at']=values['created_at']
    s=Schedule(**values,created_by=user.id)
    db.add(s);db.flush()
    if employee.id != user.id:
        notify(db,employee.id,'Lịch công tác mới',f'{s.title} – {s.destination}',schedule_id=s.id,event_type='schedule_assigned')
    audit(db,user.id,'schedule.created','schedule',s.id);db.commit();return schedule_ser(s,db)
@app.patch('/api/v1/schedules/{schedule_id}')
def schedule_update(schedule_id:int,body:ScheduleEdit,db:Session=Depends(db_session),user=Depends(current_user)):
    s=db.get(Schedule,schedule_id)
    if not s:fail('Không tìm thấy lịch',404)
    if user.role == 'accountant':
        fail('Kế toán chỉ có quyền xem lịch công tác, không có quyền thay đổi lịch', 403)
    if user.role == 'employee':
        if s.assigned_to != user.id:
            fail('Nhân viên chỉ có thể tự điều chỉnh lịch công tác của chính mình', 403)
        if body.assigned_to is not None and body.assigned_to != user.id:
            fail('Bạn không thể chuyển giao lịch công tác cho người khác', 403)
    elif user.role != 'admin':
        fail('Không có quyền điều chỉnh lịch công tác', 403)
    changes=body.model_dump(exclude_unset=True)
    if not changes:fail('Không có thông tin nào để cập nhật')
    if any(key in changes and changes[key] is None for key in ('title','destination','starts_at','ends_at','assigned_to')):fail('Các thông tin bắt buộc không được để trống',422)
    old_assigned=s.assigned_to;previous_status=s.status
    employee=db.get(User,body.assigned_to) if body.assigned_to is not None else None
    if body.assigned_to is not None and (not employee or employee.role not in ('employee','accountant') or employee.status!='active'):fail('Chỉ có thể giao lịch cho nhân viên hoặc kế toán đang hoạt động')
    if body.status is not None and body.status not in ('planned','in_progress','completed','cancelled'):fail('Trạng thái lịch không hợp lệ')
    starts_at=schedule_datetime(body.starts_at) if body.starts_at is not None else schedule_db_datetime(s.starts_at)
    ends_at=schedule_datetime(body.ends_at) if body.ends_at is not None else schedule_db_datetime(s.ends_at)
    if ends_at<=starts_at:fail('Thời gian kết thúc phải sau thời gian bắt đầu')
    assigned_to=body.assigned_to if body.assigned_to is not None else s.assigned_to
    next_status=body.status if body.status is not None else s.status
    schedule_time_changed=(assigned_to!=s.assigned_to or starts_at!=schedule_db_datetime(s.starts_at) or ends_at!=schedule_db_datetime(s.ends_at))
    restoring_cancelled=s.status=='cancelled' and next_status!='cancelled'
    if (schedule_time_changed or restoring_cancelled) and next_status!='cancelled':ensure_schedule_available(db,assigned_to,starts_at,ends_at,s.id)
    desired_title=body.title.strip() if body.title is not None else s.title
    desired_destination=body.destination.strip() if body.destination is not None else s.destination
    if not desired_title or not desired_destination:fail('Tên chuyến đi và địa điểm không được để trống',422)
    old_notes=getattr(s,'notes',None)
    details_changed=(desired_title!=s.title or desired_destination!=s.destination or starts_at!=schedule_db_datetime(s.starts_at) or ends_at!=schedule_db_datetime(s.ends_at) or assigned_to!=s.assigned_to or ('notes' in changes and body.notes!=old_notes))
    status_changed=body.status is not None and body.status!=s.status
    for key,value in changes.items():
        if key in ('starts_at','ends_at','assigned_to','status'):continue
        setattr(s,key,value.strip() if isinstance(value,str) and key in ('title','destination') else value)
    s.title=desired_title;s.destination=desired_destination
    s.starts_at=starts_at;s.ends_at=ends_at;s.assigned_to=assigned_to
    if body.status is not None:s.status=body.status
    s.completed_at=datetime.now(timezone.utc) if s.status=='completed' and previous_status!='completed' else s.completed_at if s.status=='completed' else None
    now=datetime.now(timezone.utc);_phase2_write_optional(db,'schedules',s.id,{'start_date':starts_at.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date(),'end_date':ends_at.astimezone(ZoneInfo('Asia/Ho_Chi_Minh')).date(),'updated_at':now})
    if old_assigned!=assigned_to and old_assigned!=user.id:
        notify(db,old_assigned,'Lịch công tác đã thay đổi',f'Lịch “{s.title}” đã được phân công cho nhân viên khác.',schedule_id=s.id,event_type='schedule_changed')
    if details_changed or status_changed:
        if s.status=='cancelled':title='Lịch công tác đã hủy';message=f'Lịch “{s.title}” đã bị hủy.';event='schedule_cancelled'
        elif s.status=='completed' and previous_status!='completed':title='Chuyến công tác đã hoàn thành';message=f'Chuyến “{s.title}” đã được xác nhận hoàn thành.';event='schedule_completed'
        else:title='Lịch công tác đã thay đổi';message=f'Lịch “{s.title}” đã được cập nhật.';event='schedule_changed'
        if assigned_to!=user.id:
            notify(db,assigned_to,title,message,schedule_id=s.id,event_type=event)
    audit(db,user.id,'schedule.updated','schedule',s.id);db.commit();return schedule_ser(s,db)
@app.get('/api/v1/ranking')
def ranking(period:str=Query('all',pattern='^(all|month|quarter|year)$'),db:Session=Depends(db_session),user=Depends(current_user)):
    rows=db.scalars(select(Schedule).where(Schedule.status=='completed')).all()
    today=datetime.now(timezone.utc)
    def ok(s):
        t=s.completed_at or s.ends_at
        if period=='month':return t.year==today.year and t.month==today.month
        if period=='quarter':return t.year==today.year and (t.month-1)//3==(today.month-1)//3
        if period=='year':return t.year==today.year
        return True
    scores=Counter(x.assigned_to for x in rows if ok(x))
    return [{'user_id':uid,'full_name':db.get(User,uid).full_name,'completed':cnt} for uid,cnt in scores.most_common() if db.get(User,uid)]
def _report_invoice_query(db,user,approval_status='',validation_status='',document_type='',search='',invoice_date_from=None,invoice_date_to=None,seller_name='',lookup_status=''):
    q=invoice_q(db,user)
    if invoice_date_from and invoice_date_to and invoice_date_from>invoice_date_to:fail('Ngày bắt đầu không được sau ngày kết thúc',422)
    if approval_status:q=q.where(Invoice.approval_status==approval_status)
    if validation_status:q=q.where(Invoice.validation_status==validation_status)
    if document_type:q=q.where(Invoice.document_type==document_type)
    if seller_name:q=q.where(Invoice.seller_name==seller_name)
    if lookup_status:q=q.where(Invoice.lookup_status==lookup_status)
    if invoice_date_from:q=q.where(Invoice.invoice_date>=invoice_date_from)
    if invoice_date_to:q=q.where(Invoice.invoice_date<=invoice_date_to)
    if search:
        word=f'%{search.strip()}%'
        q=q.where(Invoice.invoice_number.ilike(word)|Invoice.seller_name.ilike(word))
    return q

def report_filters(approval_status,validation_status,document_type,search,invoice_date_from,invoice_date_to,seller_name,lookup_status):
    return {'approval_status':approval_status,'validation_status':validation_status,'document_type':document_type,'search':search,'invoice_date_from':invoice_date_from.isoformat() if invoice_date_from else None,'invoice_date_to':invoice_date_to.isoformat() if invoice_date_to else None,'seller_name':seller_name,'lookup_status':lookup_status}

def report_totals(rows):
    def total(field):
        values=[Decimal(str(getattr(i,field))) for i in rows if getattr(i,field) is not None]
        return float(round(sum(values,Decimal('0')),2)) if values else (0 if not rows else None)
    return {'invoice_count':len(rows),'subtotal':total('subtotal'),'vat_amount':total('vat_amount'),'total_amount':total('total_amount'),'currency':'VND'}

@app.get('/api/v1/reports/suppliers')
def reports_suppliers(db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    return [r for r in db.execute(select(Invoice.seller_name).where(Invoice.seller_name.is_not(None)).distinct().order_by(Invoice.seller_name)).scalars().all() if r]

@app.get('/api/v1/reports/summary')
def reports_summary(approval_status:str='',validation_status:str='',document_type:str='',search:str='',invoice_date_from:date|None=None,invoice_date_to:date|None=None,seller_name:str='',lookup_status:str='',db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    rows=db.scalars(_report_invoice_query(db,user,approval_status,validation_status,document_type,search,invoice_date_from,invoice_date_to,seller_name,lookup_status)).all()
    return report_totals(rows)

@app.get('/api/v1/reports/invoices')
def reports_invoices(approval_status:str='',validation_status:str='',document_type:str='',search:str='',invoice_date_from:date|None=None,invoice_date_to:date|None=None,seller_name:str='',lookup_status:str='',limit:int=Query(10,ge=1,le=50),offset:int=Query(0,ge=0),sort_by:str=Query('date',pattern='^(date|total)$'),sort_order:str=Query('desc',pattern='^(asc|desc)$'),db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    query=_report_invoice_query(db,user,approval_status,validation_status,document_type,search,invoice_date_from,invoice_date_to,seller_name,lookup_status)
    count=db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order=Invoice.total_amount if sort_by=='total' else Invoice.invoice_date
    rows=db.scalars(query.order_by(desc(order).nullslast() if sort_order=='desc' else order.asc().nullslast(),desc(Invoice.id)).limit(limit).offset(offset)).all()
    return {'items':[{'id':i.id,'invoice_number':i.invoice_number,'invoice_date':i.invoice_date.isoformat() if i.invoice_date else None,'seller_name':i.seller_name,'seller_tax_code':i.seller_tax_code,'subtotal':decimal(i.subtotal),'vat_amount':decimal(i.vat_amount),'total_amount':decimal(i.total_amount),'approval_status':i.approval_status,'validation_status':i.validation_status,'lookup_status':i.lookup_status,'document_type':i.document_type} for i in rows],'total':count}

@app.get('/api/v1/reports/export')
def export_excel(approval_status:str='',validation_status:str='',document_type:str='',search:str='',invoice_date_from:date|None=None,invoice_date_to:date|None=None,seller_name:str='',lookup_status:str='',sort_by:str=Query('date',pattern='^(date|total)$'),sort_order:str=Query('desc',pattern='^(asc|desc)$'),db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    order=Invoice.total_amount if sort_by=='total' else Invoice.invoice_date
    ordering=desc(order).nullslast() if sort_order=='desc' else order.asc().nullslast()
    rows=db.scalars(_report_invoice_query(db,user,approval_status,validation_status,document_type,search,invoice_date_from,invoice_date_to,seller_name,lookup_status).order_by(ordering,desc(Invoice.id))).all();w=Workbook();overview=w.active;overview.title='Tổng quan báo cáo'
    filters=report_filters(approval_status,validation_status,document_type,search,invoice_date_from,invoice_date_to,seller_name,lookup_status);totals=report_totals(rows)
    labels={'approval_status':'Phê duyệt','validation_status':'Kiểm tra','document_type':'Loại chứng từ','search':'Từ khóa','invoice_date_from':'Từ ngày','invoice_date_to':'Đến ngày','seller_name':'Nhà cung cấp','lookup_status':'Tra cứu'}
    states={'draft':'Nháp','pending':'Chờ xử lý','approved':'Đã phê duyệt','rejected':'Đã từ chối','valid':'Hợp lệ','needs_review':'Cần kiểm tra','error':'Lỗi','verified':'Đã xác minh','mismatch':'Không khớp','not_found':'Không tìm thấy','not_checked':'Chưa tra cứu','not_applicable':'Không áp dụng','einvoice':'Hóa đơn điện tử','bill':'Chứng từ','unknown':'Chưa xác định'}
    filter_summary=' · '.join(f"{labels.get(key,key)}: {states.get(value,value)}" for key,value in filters.items() if value) or 'Không lọc'
    overview.append(['BÁO CÁO HÓA ĐƠN']);overview.append(['Thời gian xuất',datetime.now().astimezone().strftime('%d/%m/%Y %H:%M:%S')]);overview.append(['Người xuất',excel_text(user.full_name)]);overview.append(['Điều kiện lọc',excel_text(filter_summary)]);overview.append(['Số hóa đơn',totals['invoice_count']]);overview.append(['Tổng trước thuế (VND)',totals['subtotal']]);overview.append(['Tổng VAT (VND)',totals['vat_amount']]);overview.append(['Tổng thanh toán (VND)',totals['total_amount']])
    overview.column_dimensions['A'].width=30;overview.column_dimensions['B'].width=75
    for cell in overview[1]:
        font=copy(cell.font);font.bold=True;font.sz=16;cell.font=font
    sheet=w.create_sheet('Danh sách hóa đơn');sheet.append(['ID','Số hóa đơn','Ký hiệu','Nhà cung cấp','Mã số thuế','Tên người mua','MST người mua','Ngày lập hóa đơn','Tiền trước thuế','Thuế suất (%)','Thuế VAT','Tổng thanh toán','Trạng thái kiểm tra','Trạng thái phê duyệt','Trạng thái tra cứu','Loại chứng từ'])
    for i in rows:sheet.append([i.id,excel_text(i.invoice_number),excel_text(i.invoice_symbol),excel_text(i.seller_name),excel_text(i.seller_tax_code),excel_text(i.buyer_name),excel_text(i.buyer_tax_code),i.invoice_date,i.subtotal,i.vat_rate,i.vat_amount,i.total_amount,excel_text(i.validation_status),excel_text(i.approval_status),excel_text(i.lookup_status),excel_text(i.document_type)])
    sheet.append(['','','','','','','','Tổng cộng',totals['subtotal'],None,totals['vat_amount'],totals['total_amount']])
    for row in sheet.iter_rows(min_row=2,max_row=len(rows)+2):
        row[7].number_format='dd/mm/yyyy'
        for cell in (row[8],row[10],row[11]):cell.number_format='#,##0.00'
    for cell in sheet[1]+sheet[len(rows)+2]:
        font=copy(cell.font);font.bold=True;cell.font=font
    sheet.freeze_panes='A2';sheet.auto_filter.ref=f'A1:P{len(rows)+1}'
    for col,width in zip('ABCDEFGHIJKLMNOP',[10,22,20,35,20,35,20,16,17,15,17,20,18,18,18,15]):sheet.column_dimensions[col].width=width
    item_sheet=w.create_sheet('Chi tiết hàng hóa');item_sheet.append(['ID hóa đơn','Số hóa đơn','Dòng','Mô tả','Đơn vị','Số lượng','Đơn giá (VND)','Thành tiền (VND)'])
    invoice_ids=[i.id for i in rows]
    if invoice_ids:
        item_rows=db.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids)).order_by(InvoiceItem.invoice_id,InvoiceItem.line_no)).all()
        invoice_numbers={i.id:i.invoice_number for i in rows}
        for item in item_rows:item_sheet.append([item.invoice_id,excel_text(invoice_numbers.get(item.invoice_id)),item.line_no,excel_text(item.description),excel_text(item.unit),decimal(item.quantity),decimal(item.unit_price),decimal(item.amount)])
    item_sheet.freeze_panes='A2';item_sheet.auto_filter.ref=item_sheet.dimensions
    for row in item_sheet.iter_rows(min_row=2):
        for cell in row[5:8]:cell.number_format='#,##0.00'
    for cell in item_sheet[1]:
        font=copy(cell.font);font.bold=True;cell.font=font
    for col,width in zip('ABCDEFGH',[12,22,14,45,16,15,20,20]):item_sheet.column_dimensions[col].width=width
    data=BytesIO();w.save(data);artifact=data.getvalue();stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f');filename=f'bao_cao_hoa_don_{stamp}.xlsx'
    record=Report(requested_by=user.id,filters=filters,filename=filename,row_count=len(rows),total_amount=totals['total_amount'],status='completed',artifact_data=artifact)
    db.add(record);db.flush();audit(db,user.id,'report.exported','report',record.id);db.commit()
    return StreamingResponse(BytesIO(artifact),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

@app.get('/api/v1/reports/history')
def reports_history(db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    rows=db.execute(select(Report.id,Report.created_at,User.full_name,Report.filters,Report.row_count,Report.total_amount,Report.status,Report.filename).join(User,User.id==Report.requested_by).order_by(desc(Report.id)).limit(100)).all()
    return [{'id':r.id,'created_at':r.created_at.isoformat() if r.created_at else None,'exported_by':r.full_name,'filters':r.filters,'row_count':r.row_count,'total_amount':decimal(r.total_amount),'status':r.status,'filename':r.filename} for r in rows]

@app.get('/api/v1/reports/history/{report_id}/download')
def download_report(report_id:int,db:Session=Depends(db_session),user=Depends(require_roles('accountant','admin'))):
    report=db.get(Report,report_id)
    if not report or not report.artifact_data:fail('Không tìm thấy báo cáo hoặc bạn không có quyền tải xuống',404)
    audit(db,user.id,'report.downloaded','report',report.id);db.commit()
    return StreamingResponse(BytesIO(report.artifact_data),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="{report.filename or "bao_cao.xlsx"}"'})
@app.get('/api/v1/audit-logs')
def audit_logs(db:Session=Depends(db_session),user=Depends(require_roles('admin'))):
    return [{'id':a.id,'actor_id':a.actor_id,'action':a.action,'entity_type':a.entity_type,'entity_id':a.entity_id,'created_at':a.created_at.isoformat()} for a in db.scalars(select(AuditLog).order_by(desc(AuditLog.id)).limit(200)).all()]
IMAGE_PREFIX = "[IMAGE_ATTACHED:"

def parse_image_data(image_data: str | None) -> tuple[bytes | None, str]:
    if not image_data:
        return None, "image/jpeg"
    mime_type = "image/jpeg"
    raw_b64 = image_data
    if "," in image_data and "data:" in image_data:
        header, raw_b64 = image_data.split(",", 1)
        if ";" in header:
            mime_type = header.split(";")[0].replace("data:", "").strip()
    try:
        import base64
        data_bytes = base64.b64decode(raw_b64)
        return data_bytes, mime_type
    except Exception:
        return None, "image/jpeg"

SECURITY_REFUSAL = (
    'Yêu cầu không thể thực hiện vì vi phạm chính sách bảo mật hệ thống. '
    'Trợ lý AI không được phép tiết lộ mã khóa API, thông tin xác thực, câu lệnh nội bộ hoặc dữ liệu nhạy cảm.'
)

@app.post('/api/v1/chatbot/ask')
def chat(body:ChatInput,db:Session=Depends(db_session),user=Depends(current_user)):
    """Answer with classification, role-scoped aggregates, general reasoning and response timing metrics."""
    t_start = time.perf_counter()
    db_time = 0.0
    llm_time = 0.0
    image_bytes, mime_type = parse_image_data(body.image_base64)
    effective_question = body.question.strip()
    if not effective_question and image_bytes:
        effective_question = 'Hãy đọc, nhận diện và phân tích chi tiết hình ảnh này.'
    elif not effective_question and not image_bytes:
        fail('Vui lòng nhập câu hỏi hoặc đính kèm hình ảnh', 400)

    conversation=db.get(Conversation,body.conversation_id) if body.conversation_id else None
    if body.conversation_id and (not conversation or conversation.user_id!=user.id):
        fail('Không tìm thấy cuộc trò chuyện hoặc bạn không có quyền truy cập',404)
    history=[];previous_answer=None;chat_history=[]
    if conversation:
        history=list(reversed(db.scalars(select(ChatMessage.content).where(
            ChatMessage.conversation_id==conversation.id,ChatMessage.role=='user'
        ).order_by(desc(ChatMessage.id)).limit(12)).all()))
        previous_answer=db.scalar(select(ChatMessage.content).where(
            ChatMessage.conversation_id==conversation.id,ChatMessage.role=='assistant'
        ).order_by(desc(ChatMessage.id)).limit(1))
        recent_msgs=db.scalars(select(ChatMessage).where(
            ChatMessage.conversation_id==conversation.id
        ).order_by(desc(ChatMessage.id)).limit(8)).all()
        for m in reversed(recent_msgs):
            t = m.content
            if t.startswith(IMAGE_PREFIX):
                idx = t.find("]\n")
                if idx != -1: t = t[idx+2:]
            chat_history.append({'role':m.role,'content':t})
    previous_plan=None
    for old_question in history:
        t = old_question
        if t.startswith(IMAGE_PREFIX):
            idx = t.find("]\n")
            if idx != -1: t = t[idx+2:]
        previous_plan=chatbot_queries.parse_plan(t,role=user.role,previous_context=previous_plan)

    classification=chatbot_queries.classify_chat_question(effective_question,role=user.role,previous_context=previous_plan)
    kind=classification['kind']
    if image_bytes and kind != 'security':
        kind = 'ordinary'
    plan=classification.get('plan') or chatbot_queries.parse_plan(effective_question,role=user.role,previous_context=previous_plan)

    facts={};display_labels={}
    mode='gemini-aggregates';fallback_reason=None;gemini_connected=None

    web_sources = []
    if kind=='security':
        mode='security-refusal'
        answer=SECURITY_REFUSAL
    elif kind=='ordinary' or image_bytes:
        mode='gemini-general'
        t_llm0 = time.perf_counter()
        try:
            import inspect
            call_params = inspect.signature(gemini_chat.general_answer).parameters
            call_kwargs: dict[str, Any] = {}
            if 'history' in call_params: call_kwargs['history'] = chat_history
            if 'image_bytes' in call_params and image_bytes: call_kwargs['image_bytes'] = image_bytes
            if 'mime_type' in call_params and image_bytes: call_kwargs['mime_type'] = mime_type
            if 'sources_collector' in call_params: call_kwargs['sources_collector'] = web_sources
            answer = gemini_chat.general_answer(effective_question, **call_kwargs)
            gemini_connected = True
            llm_time = round((time.perf_counter() - t_llm0) * 1000, 1)
        except gemini_chat.GeminiUnavailable as exc:
            mode='general-fallback';fallback_reason=exc.code;gemini_connected=False
            answer=gemini_chat.friendly_error(exc.code)
    else:
        t_db0 = time.perf_counter()
        queried=chatbot_queries.query_aggregates(db,user,plan,invoice_q(db,user))
        db_time=round((time.perf_counter()-t_db0)*1000,1)
        facts=queried['facts'];display_labels=queried['labels']
        metric=plan.get('metric');domain=plan.get('domain')
        no_data=(domain=='unsupported' or facts.get('denied')
                 or metric=='amount' and 'formatted_vnd' not in facts
                 or metric=='count' and facts.get('invoice_count')==0
                 or metric=='status_distribution' and not facts.get('rows')
                 or plan.get('group_by') and not facts.get('rows')
                 or metric=='schedule_stats' and not (facts.get('schedule_count') or facts.get('rows'))
                 or metric=='summary' and domain=='invoice' and facts.get('invoice_count')==0)
        safe_previous={k:previous_plan.get(k) for k in ('domain','metric','group_by','period','scope','format','status_filter')} if plan.get('contextual') and previous_plan else None
        if no_data:
            mode='backend-aggregate'
            answer=chatbot_queries.render_fallback(plan,facts,display_labels)
        else:
            t_llm0 = time.perf_counter()
            try:
                answer=gemini_chat.answer_for(plan,facts,safe_previous)
                gemini_connected=True
                llm_time=round((time.perf_counter()-t_llm0)*1000,1)
                if plan.get('format')=='table':
                    answer=chatbot_queries.render_fallback(plan,facts,display_labels)
                else:
                    answer=chatbot_queries.apply_display_labels(answer,display_labels)
                    if plan.get('format')=='list' and not re.search(r'(?m)^\s*[-*•]\s+',answer):
                        answer=chatbot_queries.render_fallback(plan,facts,display_labels)
                    if previous_answer and previous_answer.strip()==answer.strip() and history and effective_question!=history[-1].strip():
                        answer=chatbot_queries.render_fallback(plan,facts,display_labels)
            except gemini_chat.GeminiUnavailable as exc:
                mode='database-fallback';fallback_reason=exc.code;gemini_connected=False
                answer='Đang sử dụng chế độ dự phòng (số liệu truy vấn từ backend). '+chatbot_queries.render_fallback(plan,facts,display_labels)

    user_content = f"{IMAGE_PREFIX}{body.image_base64}]\n{effective_question}" if body.image_base64 else effective_question
    if not conversation:
        conversation=Conversation(user_id=user.id,title=effective_question[:100]);db.add(conversation);db.flush()
    db.add_all([ChatMessage(conversation_id=conversation.id,role='user',content=user_content),ChatMessage(conversation_id=conversation.id,role='assistant',content=answer)])
    db.commit()
    total_time=round((time.perf_counter()-t_start)*1000,1)
    return {
        'answer': answer,
        'mode': mode,
        'kind': kind,
        'fallback_reason': fallback_reason,
        'gemini_connected': gemini_connected,
        'conversation_id': conversation.id,
        'count_visible_invoices': facts.get('invoice_count'),
        'model': gemini_chat.active_model_name(),
        'web_sources': web_sources if kind == 'ordinary' else [],
        'db_time_ms': db_time,
        'llm_time_ms': llm_time,
        'total_time_ms': total_time,
    }

@contextmanager
def get_chat_db():
    override = app.dependency_overrides.get(db_session)
    if override:
        gen = override()
        try:
            yield next(gen)
        finally:
            try:
                next(gen)
            except StopIteration:
                pass
    else:
        with SessionLocal() as db:
            yield db

@app.post('/api/v1/chatbot/stream')
async def chat_stream(body:ChatInput,request:Request,user=Depends(current_user)):
    """Streaming response via Server-Sent Events with stop generation and TTFT measurement."""
    t_start=time.perf_counter()
    image_bytes, mime_type = parse_image_data(body.image_base64)
    effective_question = body.question.strip()
    if not effective_question and image_bytes:
        effective_question = 'Hãy đọc, nhận diện và phân tích chi tiết hình ảnh này.'
    elif not effective_question and not image_bytes:
        async def err_gen():
            yield f"event: error\ndata: {json.dumps({'error':'Vui lòng nhập câu hỏi hoặc đính kèm hình ảnh'},ensure_ascii=False)}\n\n"
        return StreamingResponse(err_gen(), media_type='text/event-stream')

    async def event_generator():
        t0=time.perf_counter()
        db_time=0.0
        with get_chat_db() as db:
            conversation=db.get(Conversation,body.conversation_id) if body.conversation_id else None
            if body.conversation_id and (not conversation or conversation.user_id!=user.id):
                yield f"event: error\ndata: {json.dumps({'error':'Cuộc trò chuyện không tồn tại hoặc bạn không có quyền'})}\n\n"
                return
            if not conversation:
                conversation=Conversation(user_id=user.id,title=effective_question[:100])
                db.add(conversation);db.commit();db.refresh(conversation)
            conv_id=conversation.id
            history=list(reversed(db.scalars(select(ChatMessage.content).where(
                ChatMessage.conversation_id==conv_id,ChatMessage.role=='user'
            ).order_by(desc(ChatMessage.id)).limit(12)).all()))
            recent_msgs=db.scalars(select(ChatMessage).where(
                ChatMessage.conversation_id==conv_id
            ).order_by(desc(ChatMessage.id)).limit(8)).all()
            chat_history=[]
            for m in reversed(recent_msgs):
                t = m.content
                if t.startswith(IMAGE_PREFIX):
                    idx = t.find("]\n")
                    if idx != -1: t = t[idx+2:]
                chat_history.append({'role':m.role,'content':t})
            previous_plan=None
            for old_q in history:
                t = old_q
                if t.startswith(IMAGE_PREFIX):
                    idx = t.find("]\n")
                    if idx != -1: t = t[idx+2:]
                previous_plan=chatbot_queries.parse_plan(t,role=user.role,previous_context=previous_plan)
            classification=chatbot_queries.classify_chat_question(effective_question,role=user.role,previous_context=previous_plan)
            kind=classification['kind']
            if image_bytes and kind != 'security':
                kind = 'ordinary'
            plan=classification.get('plan') or chatbot_queries.parse_plan(effective_question,role=user.role,previous_context=previous_plan)

            facts={};display_labels={};full_chunks=[]
            ttft_ms=None

            if kind=='security':
                answer=SECURITY_REFUSAL
                yield f"event: meta\ndata: {json.dumps({'conversation_id':conv_id,'kind':'security','model':gemini_chat.active_model_name(),'db_time_ms':0},ensure_ascii=False)}\n\n"
                yield f"event: delta\ndata: {json.dumps({'text':answer},ensure_ascii=False)}\n\n"
                ttft_ms=round((time.perf_counter()-t0)*1000,1)
                tot=round((time.perf_counter()-t0)*1000,1)
                yield f"event: done\ndata: {json.dumps({'conversation_id':conv_id,'kind':'security','ttft_ms':ttft_ms,'llm_time_ms':0,'total_time_ms':tot},ensure_ascii=False)}\n\n"
                user_content = f"{IMAGE_PREFIX}{body.image_base64}]\n{effective_question}" if body.image_base64 else effective_question
                db.add_all([ChatMessage(conversation_id=conv_id,role='user',content=user_content),ChatMessage(conversation_id=conv_id,role='assistant',content=answer)])
                db.commit()
                return

            if kind=='ordinary' or image_bytes:
                yield f"event: meta\ndata: {json.dumps({'conversation_id':conv_id,'kind':'ordinary','model':gemini_chat.active_model_name(),'db_time_ms':0},ensure_ascii=False)}\n\n"
                t_llm0=time.perf_counter()
                web_sources = []
                try:
                    import inspect
                    gen_params = inspect.signature(gemini_chat.stream_general).parameters
                    gen_kwargs: dict[str, Any] = {}
                    if 'history' in gen_params: gen_kwargs['history'] = chat_history
                    if 'image_bytes' in gen_params and image_bytes: gen_kwargs['image_bytes'] = image_bytes
                    if 'mime_type' in gen_params and image_bytes: gen_kwargs['mime_type'] = mime_type
                    if 'sources_collector' in gen_params: gen_kwargs['sources_collector'] = web_sources
                    async for fragment in gemini_chat.stream_general(effective_question, **gen_kwargs):
                        if await request.is_disconnected():
                            break
                        if ttft_ms is None:
                            ttft_ms=round((time.perf_counter()-t0)*1000,1)
                        full_chunks.append(fragment)
                        yield f"event: delta\ndata: {json.dumps({'text':fragment},ensure_ascii=False)}\n\n"
                except gemini_chat.GeminiUnavailable as exc:
                    err_text=gemini_chat.friendly_error(exc.code)
                    full_chunks.append(err_text)
                    if ttft_ms is None: ttft_ms=round((time.perf_counter()-t0)*1000,1)
                    yield f"event: delta\ndata: {json.dumps({'text':err_text},ensure_ascii=False)}\n\n"

                final_answer=''.join(full_chunks)
                t_end=time.perf_counter()
                llm_time=round((t_end-t_llm0)*1000,1)
                tot=round((t_end-t0)*1000,1)
                yield f"event: done\ndata: {json.dumps({'conversation_id':conv_id,'kind':'ordinary','ttft_ms':ttft_ms or tot,'llm_time_ms':llm_time,'total_time_ms':tot,'model':gemini_chat.active_model_name(),'web_sources':web_sources},ensure_ascii=False)}\n\n"
                user_content = f"{IMAGE_PREFIX}{body.image_base64}]\n{effective_question}" if body.image_base64 else effective_question
                db.add_all([ChatMessage(conversation_id=conv_id,role='user',content=user_content),ChatMessage(conversation_id=conv_id,role='assistant',content=final_answer)])
                db.commit()
                return

            # Business or Analysis
            t_db0=time.perf_counter()
            queried=chatbot_queries.query_aggregates(db,user,plan,invoice_q(db,user))
            db_time=round((time.perf_counter()-t_db0)*1000,1)
            facts=queried['facts'];display_labels=queried['labels']
            metric=plan.get('metric');domain=plan.get('domain')
            no_data=(domain=='unsupported' or facts.get('denied')
                     or metric=='amount' and 'formatted_vnd' not in facts
                     or metric=='count' and facts.get('invoice_count')==0
                     or metric=='status_distribution' and not facts.get('rows')
                     or plan.get('group_by') and not facts.get('rows')
                     or metric=='schedule_stats' and not (facts.get('schedule_count') or facts.get('rows'))
                     or metric=='summary' and domain=='invoice' and facts.get('invoice_count')==0)
            yield f"event: meta\ndata: {json.dumps({'conversation_id':conv_id,'kind':kind,'model':gemini_chat.active_model_name(),'db_time_ms':db_time,'count_visible_invoices':facts.get('invoice_count')},ensure_ascii=False)}\n\n"

            if plan.get('format')=='table' or no_data:
                fallback_text=chatbot_queries.render_fallback(plan,facts,display_labels)
                ttft_ms=round((time.perf_counter()-t0)*1000,1)
                yield f"event: delta\ndata: {json.dumps({'text':fallback_text},ensure_ascii=False)}\n\n"
                tot=round((time.perf_counter()-t0)*1000,1)
                yield f"event: done\ndata: {json.dumps({'conversation_id':conv_id,'kind':kind,'ttft_ms':ttft_ms,'db_time_ms':db_time,'llm_time_ms':0,'total_time_ms':tot,'count_visible_invoices':facts.get('invoice_count'),'model':gemini_chat.active_model_name()},ensure_ascii=False)}\n\n"
                user_content = f"{IMAGE_PREFIX}{body.image_base64}]\n{effective_question}" if body.image_base64 else effective_question
                db.add_all([ChatMessage(conversation_id=conv_id,role='user',content=user_content),ChatMessage(conversation_id=conv_id,role='assistant',content=fallback_text)])
                db.commit()
                return

            safe_previous={k:previous_plan.get(k) for k in ('domain','metric','group_by','period','scope','format','status_filter')} if plan.get('contextual') and previous_plan else None
            t_llm0=time.perf_counter()
            try:
                async for fragment in gemini_chat.stream_analysis(plan,facts,safe_previous):
                    if await request.is_disconnected():
                        break
                    if ttft_ms is None:
                        ttft_ms=round((time.perf_counter()-t0)*1000,1)
                    fragment_display=chatbot_queries.apply_display_labels(fragment,display_labels)
                    full_chunks.append(fragment_display)
                    yield f"event: delta\ndata: {json.dumps({'text':fragment_display},ensure_ascii=False)}\n\n"
            except gemini_chat.GeminiUnavailable as exc:
                fallback_text='Đang sử dụng chế độ dự phòng (số liệu truy vấn từ backend). '+chatbot_queries.render_fallback(plan,facts,display_labels)
                full_chunks.append(fallback_text)
                if ttft_ms is None: ttft_ms=round((time.perf_counter()-t0)*1000,1)
                yield f"event: delta\ndata: {json.dumps({'text':fallback_text},ensure_ascii=False)}\n\n"

            final_answer=''.join(full_chunks)
            if plan.get('format')=='list' and not re.search(r'(?m)^\s*[-*•]\s+',final_answer):
                final_answer=chatbot_queries.render_fallback(plan,facts,display_labels)
            t_end=time.perf_counter()
            llm_time=round((t_end-t_llm0)*1000,1)
            tot=round((t_end-t0)*1000,1)
            yield f"event: done\ndata: {json.dumps({'conversation_id':conv_id,'kind':kind,'ttft_ms':ttft_ms or tot,'db_time_ms':db_time,'llm_time_ms':llm_time,'total_time_ms':tot,'count_visible_invoices':facts.get('invoice_count'),'model':gemini_chat.active_model_name()},ensure_ascii=False)}\n\n"
            user_content = f"{IMAGE_PREFIX}{body.image_base64}]\n{effective_question}" if body.image_base64 else effective_question
            db.add_all([ChatMessage(conversation_id=conv_id,role='user',content=user_content),ChatMessage(conversation_id=conv_id,role='assistant',content=final_answer)])
            db.commit()

    return StreamingResponse(event_generator(),media_type='text/event-stream',headers={
        'Cache-Control':'no-cache','X-Accel-Buffering':'no','Connection':'keep-alive'
    })

@app.get('/api/v1/chatbot/status')
def chatbot_status(user=Depends(current_user)):
    return gemini_chat.health_check()

@app.get('/api/v1/chatbot/conversations')
def get_conversations(db:Session=Depends(db_session),user=Depends(current_user)):
    rows=db.scalars(select(Conversation).where(Conversation.user_id==user.id).order_by(desc(Conversation.id)).limit(50)).all()
    res=[]
    for c in rows:
        last_msg=db.scalar(select(ChatMessage.content).where(ChatMessage.conversation_id==c.id,ChatMessage.role=='user').order_by(ChatMessage.id.asc()).limit(1))
        preview=''
        if last_msg:
            if last_msg.startswith(IMAGE_PREFIX):
                idx=last_msg.find("]\n")
                if idx!=-1:
                    last_msg='[Hình ảnh] '+last_msg[idx+2:]
            preview=(last_msg[:60]+'...') if len(last_msg)>60 else last_msg
        res.append({
            'id':c.id,
            'title':c.title or 'Cuộc trò chuyện mới',
            'created_at':c.created_at.isoformat() if c.created_at else None,
            'preview':preview
        })
    return res

@app.get('/api/v1/chatbot/conversations/{conv_id}')
def get_conversation_detail(conv_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    c=db.get(Conversation,conv_id)
    if not c or c.user_id!=user.id:
        fail('Không tìm thấy cuộc trò chuyện',404)
    msgs=db.scalars(select(ChatMessage).where(ChatMessage.conversation_id==c.id).order_by(ChatMessage.id.asc())).all()
    res_msgs=[]
    for m in msgs:
        img=None
        text=m.content
        if text.startswith(IMAGE_PREFIX):
            idx=text.find("]\n")
            if idx!=-1:
                img=text[len(IMAGE_PREFIX):idx]
                text=text[idx+2:]
        res_msgs.append({'id':m.id,'role':m.role,'content':text,'image':img})
    return {
        'id':c.id,
        'title':c.title or 'Cuộc trò chuyện mới',
        'created_at':c.created_at.isoformat() if c.created_at else None,
        'messages':res_msgs
    }

@app.delete('/api/v1/chatbot/conversations/{conv_id}')
def delete_conversation(conv_id:int,db:Session=Depends(db_session),user=Depends(current_user)):
    c=db.get(Conversation,conv_id)
    if not c or c.user_id!=user.id:
        fail('Không tìm thấy cuộc trò chuyện',404)
    chat_msgs=db.scalars(select(ChatMessage).where(ChatMessage.conversation_id==c.id)).all()
    for cm in chat_msgs:
        db.delete(cm)
    db.delete(c)
    db.commit()
    return {'status':'deleted'}
