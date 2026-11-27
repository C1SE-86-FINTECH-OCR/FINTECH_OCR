from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, LargeBinary, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .core import Base
from .models import now


class TravelAdvance(Base):
    __tablename__ = 'travel_advances'

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36))
    employee_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey('schedules.id'), index=True)
    employee_name: Mapped[str] = mapped_column(String(150))
    employee_code: Mapped[str | None] = mapped_column(String(40))
    department: Mapped[str | None] = mapped_column(String(120))
    trip_title: Mapped[str] = mapped_column(String(255))
    starts_on: Mapped[date]
    ends_on: Mapped[date]
    reason: Mapped[str] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    requested: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    approved: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    disbursed: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    disbursed_on: Mapped[date | None]
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    disbursed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(24), default='draft', index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint('employee_id', 'request_id'),
        CheckConstraint('requested > 0 AND (approved IS NULL OR (approved > 0 AND approved <= requested))',
                        name='ck_advance_request_amounts'),
        CheckConstraint('disbursed >= 0 AND (disbursed = 0 OR (approved IS NOT NULL AND disbursed <= approved))',
                        name='ck_advance_disbursed_amount'),
    )


class TravelExpense(Base):
    __tablename__ = 'travel_expenses'

    id: Mapped[int] = mapped_column(primary_key=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey('travel_advances.id'), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey('invoices.id'), index=True)
    category: Mapped[str] = mapped_column(String(24))
    description: Mapped[str] = mapped_column(Text)
    incurred_on: Mapped[date]
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    accepted: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=0)
    status: Mapped[str] = mapped_column(String(12), default='pending')
    review_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (
        UniqueConstraint('advance_id', 'invoice_id'),
        CheckConstraint('amount > 0 AND accepted >= 0 AND accepted <= amount', name='ck_travel_expense_amounts'),
    )


class TravelPayment(Base):
    __tablename__ = 'travel_payments'

    id: Mapped[int] = mapped_column(primary_key=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey('travel_advances.id'), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    paid_on: Mapped[date]
    method: Mapped[str] = mapped_column(String(40))
    reference: Mapped[str] = mapped_column(String(120))
    evidence: Mapped[str] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint('kind', 'reference'),
        CheckConstraint('amount > 0', name='ck_travel_payment_amount'),
    )


class TravelAdvanceEvent(Base):
    __tablename__ = 'travel_advance_events'

    id: Mapped[int] = mapped_column(primary_key=True)
    advance_id: Mapped[int] = mapped_column(ForeignKey('travel_advances.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TravelPaymentEvidence(Base):
    __tablename__ = 'travel_payment_evidence'

    payment_id: Mapped[int] = mapped_column(ForeignKey('travel_payments.id'), primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(30))
    content: Mapped[bytes] = mapped_column(LargeBinary)
