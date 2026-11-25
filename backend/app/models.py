from datetime import datetime,timezone,date
from sqlalchemy import String,Integer,ForeignKey,DateTime,Date,Numeric,Text,Boolean,Float,UniqueConstraint,JSON,LargeBinary
from sqlalchemy.orm import Mapped,mapped_column,relationship
from .core import Base

def now():return datetime.now(timezone.utc)
class User(Base):
    __tablename__='users'
    id:Mapped[int]=mapped_column(primary_key=True)
    full_name:Mapped[str]=mapped_column(String(150))
    email:Mapped[str]=mapped_column(String(255),unique=True,index=True)
    password_hash:Mapped[str]=mapped_column(Text)
    role:Mapped[str]=mapped_column(String(20),default='employee')
    phone:Mapped[str|None]=mapped_column(String(30),nullable=True)
    team:Mapped[str|None]=mapped_column(String(120),nullable=True)
    employee_code:Mapped[str|None]=mapped_column(String(40),nullable=True)
    avatar_data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    avatar_mime:Mapped[str|None]=mapped_column(String(30),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='active')
    created_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'),nullable=True)
    last_login_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
class RevokedToken(Base):
    __tablename__='revoked_tokens'
    jti:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    expires_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    revoked_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class InvoiceFile(Base):
    __tablename__='invoice_files'
    id:Mapped[int]=mapped_column(primary_key=True)
    uploaded_by:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    original_filename:Mapped[str]=mapped_column(String(255))
    file_type:Mapped[str]=mapped_column(String(10))
    mime_type:Mapped[str]=mapped_column(String(100))
    file_size_bytes:Mapped[int]=mapped_column(Integer)
    storage_provider:Mapped[str]=mapped_column(String(30),default='local')
    storage_key:Mapped[str]=mapped_column(Text)
    checksum_sha256:Mapped[str]=mapped_column(String(64))
    uploaded_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Invoice(Base):
    __tablename__='invoices'
    id:Mapped[int]=mapped_column(primary_key=True)
    file_id:Mapped[int]=mapped_column(ForeignKey('invoice_files.id'),unique=True)
    invoice_number:Mapped[str|None]=mapped_column(String(50))
    invoice_symbol:Mapped[str|None]=mapped_column(String(40))
    invoice_date:Mapped[date|None]=mapped_column(Date)
    seller_name:Mapped[str|None]=mapped_column(String(255))
    seller_tax_code:Mapped[str|None]=mapped_column(String(25))
    buyer_name:Mapped[str|None]=mapped_column(String(255))
    buyer_tax_code:Mapped[str|None]=mapped_column(String(25))
    currency:Mapped[str]=mapped_column(String(3),default='VND')
    subtotal:Mapped[float|None]=mapped_column(Numeric(18,2))
    vat_rate:Mapped[float|None]=mapped_column(Numeric(5,2))
    vat_amount:Mapped[float|None]=mapped_column(Numeric(18,2))
    total_amount:Mapped[float|None]=mapped_column(Numeric(18,2))
    confidence_score:Mapped[float|None]=mapped_column(Float)
    validation_status:Mapped[str|None]=mapped_column(String(20),default='needs_review')
    approval_status:Mapped[str]=mapped_column(String(20),default='draft')
    lookup_status:Mapped[str]=mapped_column(String(20),default='not_checked')
    document_type:Mapped[str]=mapped_column(String(20),default='unknown')
    is_corrected:Mapped[bool]=mapped_column(Boolean,default=False)
    reviewed_by:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    reviewed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    qr_url:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,onupdate=now)
    source_file:Mapped[InvoiceFile]=relationship()
class InvoiceMessage(Base):
    __tablename__ = 'invoice_messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class InvoiceItem(Base):
    __tablename__='invoice_items'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'),index=True)
    line_no:Mapped[int]=mapped_column(Integer)
    description:Mapped[str]=mapped_column(Text)
    unit:Mapped[str|None]=mapped_column(String(30))
    quantity:Mapped[float|None]=mapped_column(Numeric(18,3))
    unit_price:Mapped[float|None]=mapped_column(Numeric(18,2))
    amount:Mapped[float|None]=mapped_column(Numeric(18,2))
class ExtractionRun(Base):
    __tablename__='extraction_runs'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    method:Mapped[str]=mapped_column(String(32))
    raw_text:Mapped[str|None]=mapped_column(Text)
    extracted_json:Mapped[dict|None]=mapped_column(JSON)
    confidence_score:Mapped[float|None]=mapped_column(Float)
    status:Mapped[str]=mapped_column(String(20),default='completed')
    error_message:Mapped[str|None]=mapped_column(Text)
    started_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ValidationResult(Base):
    __tablename__='validation_results'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'),index=True)
    validation_round:Mapped[int]=mapped_column(Integer,default=1)
    rule_code:Mapped[str]=mapped_column(String(40))
    passed:Mapped[bool]=mapped_column(Boolean)
    severity:Mapped[str]=mapped_column(String(15),default='warning')
    message:Mapped[str]=mapped_column(Text)
    checked_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class InvoiceCorrection(Base):
    __tablename__='invoice_corrections'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    field_name:Mapped[str]=mapped_column(String(64))
    old_value:Mapped[str|None]=mapped_column(Text)
    new_value:Mapped[str|None]=mapped_column(Text)
    corrected_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    corrected_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class InvoiceFlag(Base):
    __tablename__='invoice_flags'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    flag_type:Mapped[str]=mapped_column(String(30))
    reason:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(20),default='open')
class Conversation(Base):
    __tablename__='conversations'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
    title:Mapped[str]=mapped_column(String(255))
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ChatMessage(Base):
    __tablename__='chat_messages'
    id:Mapped[int]=mapped_column(primary_key=True)
    conversation_id:Mapped[int]=mapped_column(ForeignKey('conversations.id'))
    role:Mapped[str]=mapped_column(String(20))
    content:Mapped[str]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class ChatMessageSource(Base):
    __tablename__='chat_message_sources'
    message_id:Mapped[int]=mapped_column(ForeignKey('chat_messages.id'),primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'),primary_key=True)
class Report(Base):
    __tablename__='reports'
    id:Mapped[int]=mapped_column(primary_key=True)
    requested_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    filters:Mapped[dict]=mapped_column(JSON,default=dict)
    filename:Mapped[str|None]=mapped_column(String(255),nullable=True)
    row_count:Mapped[int|None]=mapped_column(Integer,nullable=True)
    total_amount:Mapped[float|None]=mapped_column(Numeric(18,2),nullable=True)
    status:Mapped[str]=mapped_column(String(20),default='completed')
    artifact_data:Mapped[bytes|None]=mapped_column(LargeBinary,nullable=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class InvoiceEmbedding(Base):
    __tablename__='invoice_embeddings'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    embedding_model:Mapped[str]=mapped_column(String(100))
    # Development placeholder. Implement pgvector Vector(dimension) once the model is selected.
    vector_data:Mapped[dict|None]=mapped_column(JSON)
class AuditLog(Base):
    __tablename__='audit_logs'
    id:Mapped[int]=mapped_column(primary_key=True)
    actor_id:Mapped[int|None]=mapped_column(ForeignKey('users.id'))
    action:Mapped[str]=mapped_column(String(100))
    entity_type:Mapped[str]=mapped_column(String(40))
    entity_id:Mapped[int|None]=mapped_column(Integer)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Notification(Base):
    __tablename__='notifications'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    invoice_id:Mapped[int|None]=mapped_column(ForeignKey('invoices.id'))
    schedule_id:Mapped[int|None]=mapped_column(ForeignKey('schedules.id'))
    title:Mapped[str]=mapped_column(String(255))
    message:Mapped[str]=mapped_column(Text)
    is_read:Mapped[bool]=mapped_column(Boolean,default=False)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Schedule(Base):
    __tablename__='schedules'
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(255))
    destination:Mapped[str]=mapped_column(String(255))
    starts_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    ends_at:Mapped[datetime]=mapped_column(DateTime(timezone=True))
    start_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    end_date:Mapped[date|None]=mapped_column(Date,nullable=True)
    assigned_to:Mapped[int]=mapped_column(ForeignKey('users.id'))
    created_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    status:Mapped[str]=mapped_column(String(20),default='planned')
    notes:Mapped[str|None]=mapped_column(Text,nullable=True)
    completed_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),default=now,nullable=True)
    updated_at:Mapped[datetime|None]=mapped_column(DateTime(timezone=True),default=now,onupdate=now,nullable=True)
class InvoiceApproval(Base):
    __tablename__='invoice_approvals'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    action_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    action:Mapped[str]=mapped_column(String(25))
    reason:Mapped[str|None]=mapped_column(Text)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class InvoiceLookup(Base):
    __tablename__='invoice_lookups'
    id:Mapped[int]=mapped_column(primary_key=True)
    invoice_id:Mapped[int]=mapped_column(ForeignKey('invoices.id'))
    checked_by:Mapped[int]=mapped_column(ForeignKey('users.id'))
    result:Mapped[str]=mapped_column(String(20))
    note:Mapped[str|None]=mapped_column(Text)
    checked_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)


class DirectMessage(Base):
    __tablename__ = 'direct_messages'
    id: Mapped[int] = mapped_column(primary_key=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
