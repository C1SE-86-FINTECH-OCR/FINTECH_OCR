"""Regression tests for FINTECH OCR validation (safe, read-only to real project).

All test invoices and their history are created in an isolated in-memory SQLite
engine. This module never opens or modifies backend/fintech_ocr.db.

Prerequisite: main.py with the latest-validation-round warnings fix; OCR v4.
"""

from datetime import date

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core import Base
from app.main import inv_ser, validators
from app.models import Invoice, InvoiceFile, InvoiceItem, User, ValidationResult


@pytest.fixture
def sample():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            actor = User(
                full_name="Regression Employee",
                email="regression@example.invalid",
                role="employee",
                password_hash="test-only",
            )
            db.add(actor)
            db.flush()
            source = InvoiceFile(
                uploaded_by=actor.id,
                original_filename="sample.jpg",
                file_type="jpg",
                mime_type="image/jpeg",
                file_size_bytes=20,
                storage_key="not-a-real-file.jpg",
                checksum_sha256="a" * 64,
            )
            db.add(source)
            db.flush()
            invoice = Invoice(
                file_id=source.id,
                document_type="einvoice",
                invoice_number="0000003",
                invoice_symbol="HM/17E",
                invoice_date=date(2017, 10, 16),
                seller_name="Cong ty co phan ABC",
                seller_tax_code="0101243150",
                buyer_name="Cong ty TNHH Bao Ngoc",
                buyer_tax_code="0101243150",
                subtotal=8_000_000,
                vat_rate=10,
                vat_amount=800_000,
                total_amount=8_800_000,
                approval_status="draft",
            )
            db.add(invoice)
            db.flush()
            db.add(InvoiceItem(
                invoice_id=invoice.id,
                line_no=1,
                description="Synthetic service",
                amount=8_000_000,
            ))
            db.commit()
            yield db, invoice
    finally:
        engine.dispose()


def validate_and_read(db, invoice):
    validators(db, invoice)
    db.commit()
    db.refresh(invoice)
    return inv_ser(invoice, db, details=True)


def test_01_valid_financial_values_have_no_current_warnings(sample):
    db, invoice = sample
    detail = validate_and_read(db, invoice)
    assert detail["validation_status"] == "valid"
    assert detail["warnings"] == []
    assert detail["subtotal"] == 8_000_000
    assert detail["vat_amount"] == 800_000
    assert detail["total_amount"] == 8_800_000


def test_02_wrong_vat_causes_both_financial_warnings(sample):
    db, invoice = sample
    invoice.vat_amount = 900_000
    detail = validate_and_read(db, invoice)
    assert detail["validation_status"] == "needs_review"
    assert {x["rule"] for x in detail["warnings"]} == {"ARITH", "VAT-ARITH"}


def test_03_corrected_invoice_clears_old_warnings_but_preserves_history(sample):
    db, invoice = sample
    invoice.vat_amount = 900_000
    bad = validate_and_read(db, invoice)
    assert len(bad["warnings"]) == 2
    old_rows = db.scalars(select(ValidationResult).where(ValidationResult.invoice_id == invoice.id)).all()
    bad_round = max(x.validation_round for x in old_rows)

    invoice.vat_amount = 800_000
    good = validate_and_read(db, invoice)
    assert good["validation_status"] == "valid"
    assert good["warnings"] == []

    rows = db.scalars(select(ValidationResult).where(ValidationResult.invoice_id == invoice.id)).all()
    assert any(x.validation_round == bad_round and not x.passed for x in rows)
    assert max(x.validation_round for x in rows) == bad_round + 1


def test_04_new_bad_run_shows_only_new_errors(sample):
    db, invoice = sample
    invoice.vat_amount = 900_000
    validate_and_read(db, invoice)
    invoice.vat_amount = 800_000
    validate_and_read(db, invoice)
    invoice.invoice_number = None
    latest = validate_and_read(db, invoice)
    assert latest["validation_status"] == "needs_review"
    assert [w["rule"] for w in latest["warnings"]] == ["INV-NO"]


def test_05_invalid_buyer_tax_code_is_detected(sample):
    db, invoice = sample
    invoice.buyer_tax_code = "invalid-tax-code"
    latest = validate_and_read(db, invoice)
    assert latest["validation_status"] == "needs_review"
    assert "BUYER-TAX" in {w["rule"] for w in latest["warnings"]}


def test_06_missing_supplier_tax_code_is_detected(sample):
    db, invoice = sample
    invoice.seller_tax_code = None
    latest = validate_and_read(db, invoice)
    assert latest["validation_status"] == "needs_review"
    assert "TAX-CODE" in {w["rule"] for w in latest["warnings"]}


def test_07_missing_total_is_detected(sample):
    db, invoice = sample
    invoice.total_amount = None
    latest = validate_and_read(db, invoice)
    assert latest["validation_status"] == "needs_review"
    assert "TOTAL" in {w["rule"] for w in latest["warnings"]}


def test_08_revalidate_valid_invoice_makes_new_round_without_warnings(sample):
    db, invoice = sample
    first = validate_and_read(db, invoice)
    second = validate_and_read(db, invoice)
    assert first["warnings"] == second["warnings"] == []
    assert db.scalar(
        select(func.max(ValidationResult.validation_round)).where(ValidationResult.invoice_id == invoice.id)
    ) == 2
