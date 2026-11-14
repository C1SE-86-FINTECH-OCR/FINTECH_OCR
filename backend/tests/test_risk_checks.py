"""Read-only invoice-risk tests. Uses in-memory SQLite, never fintech_ocr.db."""

from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core import Base
from app.models import Invoice, InvoiceFile, InvoiceItem, User, ValidationResult
from app.risk_checks import assess_invoice_risks
from app.main import inv_ser, validators, invoice_risk_assessment


@pytest.fixture
def sample():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        u = User(full_name="Test Employee", email="risk@example.invalid", password_hash="test", role="employee")
        v = User(full_name="Second Employee", email="risk2@example.invalid", password_hash="test", role="employee")
        db.add_all([u, v])
        db.flush()
        ids = (u.id, v.id)
        yield db, ids
    engine.dispose()


def make_invoice(db, owner, *, digest="a" * 64, number="0000003", symbol="HM/17E",
                 seller_tax="0101243150", buyer_tax="0401234567", buyer_name="Buyer Co",
                 seller_name="Seller Co", subtotal=8_000_000, vat_amount=800_000,
                 document_type="einvoice", day=date(2017, 10, 16)):
    f = InvoiceFile(uploaded_by=owner, original_filename="demo.jpg", file_type="jpg",
                    mime_type="image/jpeg", file_size_bytes=100, storage_key="dummy.jpg",
                    checksum_sha256=digest)
    db.add(f)
    db.flush()
    i = Invoice(file_id=f.id, invoice_number=number, invoice_symbol=symbol, invoice_date=day,
                seller_name=seller_name, seller_tax_code=seller_tax,
                buyer_name=buyer_name, buyer_tax_code=buyer_tax,
                subtotal=subtotal, vat_amount=vat_amount, vat_rate=10,
                total_amount=8_800_000, document_type=document_type)
    db.add(i)
    db.commit()
    db.add(InvoiceItem(invoice_id=i.id, line_no=1, description="Synthetic service", amount=subtotal))
    db.commit()
    return i


def codes(result):
    return {f["code"] for f in result["flags"]}


def test_01_clean_invoice_has_no_risk_flags(sample):
    db, users = sample
    i = make_invoice(db, users[0])
    r = assess_invoice_risks(db, i)
    assert r["has_flags"] is False
    assert r["flags"] == []
    assert r["tax_lookup_performed"] is False


def test_02_duplicate_bytes_detected_for_reviewer_without_exposing_ids(sample):
    db, users = sample
    make_invoice(db, users[0], number="1111111", symbol="X/26E", digest="a"*64)
    i = make_invoice(db, users[1], number="2222222", symbol="Y/26E", digest="a"*64)
    r = assess_invoice_risks(db, i, role="accountant")
    assert "DUPLICATE-FILE" in codes(r)
    assert "DUPLICATE-INVOICE" not in codes(r)
    assert next(x for x in r["flags"] if x["code"] == "DUPLICATE-FILE")["matched_count"] == 1
    assert "matched_invoice_ids" not in str(r)


def test_03_duplicate_invoice_same_business_key_different_bytes(sample):
    db, users = sample
    make_invoice(db, users[0], digest="a"*64)
    i = make_invoice(db, users[1], digest="b"*64)
    r = assess_invoice_risks(db, i, role="accountant")
    assert "DUPLICATE-INVOICE" in codes(r)
    assert "DUPLICATE-FILE" not in codes(r)


def test_04_same_number_different_seller_not_duplicate(sample):
    db, users = sample
    make_invoice(db, users[0], digest="a"*64)
    i = make_invoice(db, users[1], digest="b"*64, seller_tax="0401234567")
    assert "DUPLICATE-INVOICE" not in codes(assess_invoice_risks(db, i, role="accountant"))


def test_05_same_tax_code_with_different_company_names_warning(sample):
    db, users = sample
    i = make_invoice(db, users[0], buyer_tax="0101243150")
    assert "SAME-TAX-CODE" in codes(assess_invoice_risks(db, i))


def test_06_same_company_with_same_tax_code_not_flagged(sample):
    db, users = sample
    i = make_invoice(db, users[0], buyer_tax="0101243150", buyer_name="Seller Co")
    assert "SAME-TAX-CODE" not in codes(assess_invoice_risks(db, i))


def test_07_missing_financial_data_returns_advisory(sample):
    db, users = sample
    i = make_invoice(db, users[0], subtotal=None, vat_amount=None, symbol=None)
    r = assess_invoice_risks(db, i)
    assert "INCOMPLETE-FINANCIAL" in codes(r)
    assert "MISSING-SYMBOL" in codes(r)


def test_08_bill_missing_optional_fields_does_not_gain_einvoice_warning(sample):
    db, users = sample
    i = make_invoice(db, users[0], subtotal=None, vat_amount=None, symbol=None, document_type="bill")
    assert "INCOMPLETE-FINANCIAL" not in codes(assess_invoice_risks(db, i))


def test_09_risk_assessment_does_not_write_validation_or_change_status(sample):
    db, users = sample
    i = make_invoice(db, users[0], buyer_tax="0101243150")
    validators(db, i)
    db.commit()
    before = db.scalars(select(ValidationResult).where(ValidationResult.invoice_id == i.id)).all()
    prev = i.validation_status
    assess_invoice_risks(db, i)
    after = db.scalars(select(ValidationResult).where(ValidationResult.invoice_id == i.id)).all()
    assert len(after) == len(before)
    assert i.validation_status == prev


def test_10_role_scoped_endpoint_blocks_other_employee_invoice(sample):
    db, users = sample
    i = make_invoice(db, users[0])
    other = db.get(User, users[1])
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        invoice_risk_assessment(i.id, db=db, user=other)
    assert exc.value.status_code == 404


def test_11_accountant_can_read_risk_assessment_without_modifying_state(sample):
    db, users = sample
    i = make_invoice(db, users[0], buyer_tax="0101243150")
    accountant = User(full_name="Test Accountant", email="accountant@example.invalid", password_hash="test", role="accountant")
    db.add(accountant)
    db.commit()
    r = invoice_risk_assessment(i.id, db=db, user=accountant)
    assert r["invoice_id"] == i.id
    assert "SAME-TAX-CODE" in codes(r)


def test_12_current_validation_warning_behavior_unchanged(sample):
    db, users = sample
    i = make_invoice(db, users[0], buyer_tax="0101243150")
    validators(db, i)
    db.commit()
    detail = inv_ser(i, db, True)
    assert detail["validation_status"] == "valid"
    assert detail["warnings"] == []
    assert "SAME-TAX-CODE" in codes(assess_invoice_risks(db, i))


def test_13_employee_cannot_discover_other_user_duplicates(sample):
    db, users = sample
    make_invoice(db, users[0], digest="a" * 64)
    other = make_invoice(db, users[1], digest="a" * 64)
    result = assess_invoice_risks(db, other, role="employee")
    assert result["scope"] == "own_invoices"
    assert "DUPLICATE-FILE" not in codes(result)
    assert "DUPLICATE-INVOICE" not in codes(result)


def test_14_employee_detects_duplicate_within_own_invoices(sample):
    db, users = sample
    make_invoice(db, users[0], digest="a" * 64)
    i = make_invoice(db, users[0], digest="a" * 64)
    result = assess_invoice_risks(db, i, role="employee")
    assert "DUPLICATE-FILE" in codes(result)
    assert "DUPLICATE-INVOICE" in codes(result)
