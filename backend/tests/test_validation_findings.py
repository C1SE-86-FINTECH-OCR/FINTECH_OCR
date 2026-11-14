"""Regression tests for stale Validation findings. Uses an in-memory database only.

No connection to the project's real SQLite database is made by these tests.
"""

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core import Base
from app.main import inv_ser, validators
from app.models import Invoice, InvoiceFile, User, ValidationResult
import app.main as api


@pytest.fixture
def invoice_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            user = User(full_name="Test Employee", email="test.validation@local", password_hash="test")
            db.add(user)
            db.flush()
            file = InvoiceFile(
                uploaded_by=user.id,
                original_filename="test.png",
                file_type="png",
                mime_type="image/png",
                file_size_bytes=1,
                storage_key="test.png",
                checksum_sha256="0" * 64,
            )
            db.add(file)
            db.flush()
            invoice = Invoice(file_id=file.id, invoice_number="0000003")
            db.add(invoice)
            db.commit()
            yield db, invoice
    finally:
        engine.dispose()


def _run(db, invoice, monkeypatch, results):
    monkeypatch.setattr(api, "validate", lambda _invoice, _items=None: results)
    validators(db, invoice)
    db.commit()


def test_only_current_round_warnings_are_returned(invoice_db, monkeypatch):
    db, invoice = invoice_db
    _run(db, invoice, monkeypatch, [("VAT", False, "VAT sai"), ("TOTAL", False, "Tổng sai")])
    assert {w["rule"] for w in inv_ser(invoice, db, True)["warnings"]} == {"VAT", "TOTAL"}

    _run(db, invoice, monkeypatch, [("VAT", True, "OK"), ("TOTAL", True, "OK")])
    details = inv_ser(invoice, db, True)
    assert details["validation_status"] == "valid"
    assert details["warnings"] == []

    # Past validation results are preserved, not deleted from the database.
    rows = db.scalars(select(ValidationResult).where(ValidationResult.invoice_id == invoice.id)).all()
    assert len(rows) == 4
    assert {(r.validation_round, r.rule_code, r.passed) for r in rows} == {
        (1, "VAT", False), (1, "TOTAL", False), (2, "VAT", True), (2, "TOTAL", True)
    }


def test_new_failed_round_does_not_repeat_old_errors(invoice_db, monkeypatch):
    db, invoice = invoice_db
    _run(db, invoice, monkeypatch, [("VAT", False, "VAT cũ")])
    _run(db, invoice, monkeypatch, [("VAT", True, "OK")])
    _run(db, invoice, monkeypatch, [("TOTAL", False, "Sai tổng mới")])
    assert inv_ser(invoice, db, True)["warnings"] == [
        {"rule": "TOTAL", "message": "Sai tổng mới", "passed": False}
    ]


def test_round_number_independent_of_rule_count_and_legacy_rows(invoice_db, monkeypatch):
    db, invoice = invoice_db
    # Emulate historical records from old main.py, which reused round numbers.
    for code in ("A", "B", "C", "D", "E", "F"):
        db.add(ValidationResult(invoice_id=invoice.id, validation_round=1, rule_code=code,
                                passed=False, message="Lỗi cũ", severity="warning"))
    db.commit()
    _run(db, invoice, monkeypatch, [("A", True, "OK")])
    latest = db.scalar(select(func.max(ValidationResult.validation_round)).where(
        ValidationResult.invoice_id == invoice.id))
    assert latest == 2
    assert inv_ser(invoice, db, True)["warnings"] == []
    assert db.scalar(select(func.count(ValidationResult.id)).where(
        ValidationResult.invoice_id == invoice.id)) == 7


def test_invoice_without_validation_runs_has_no_warnings(invoice_db):
    db, invoice = invoice_db
    assert inv_ser(invoice, db, True)["warnings"] == []
