import asyncio
import json
import secrets
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
import fitz
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.core as core
import app.main as api_main
from app.models import AuditLog, ExtractionRun, Invoice, InvoiceApproval, InvoiceCorrection, InvoiceFile, InvoiceItem, InvoiceLookup, Notification, User, ValidationResult


def test_postgres_startup_does_not_create_schema(monkeypatch, tmp_path):
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    monkeypatch.setattr(api_main, "engine", test_engine)
    monkeypatch.setattr(api_main, "storage_dir", lambda: tmp_path)
    monkeypatch.setattr(core.settings, "app_env", "development")
    monkeypatch.setattr(
        core.settings,
        "database_url",
        "postgresql+psycopg://test-target-is-not-used",
    )

    async def run_lifespan():
        async with api_main.lifespan(api_main.app):
            pass

    asyncio.run(run_lifespan())
    assert inspect(test_engine).get_table_names() == []
    test_engine.dispose()


@pytest.fixture
def api_env(tmp_path, monkeypatch):
    test_engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    core.Base.metadata.create_all(test_engine)
    TestSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    monkeypatch.setattr(api_main, "engine", test_engine)
    monkeypatch.setattr(api_main, "storage_dir", lambda: tmp_path)

    def override_db():
        with TestSession() as db:
            yield db

    api_main.app.dependency_overrides[core.db_session] = override_db
    api_main.app.state.phase2_test_session = TestSession
    api_main.app.state.phase2_upload_path = tmp_path
    test_password = secrets.token_urlsafe(24)
    with TestSession() as db:
        users = {}
        for role, email in (
            ("admin", "admin@phase2.test"),
            ("accountant", "accountant@phase2.test"),
            ("employee", "employee1@phase2.test"),
            ("employee", "employee2@phase2.test"),
        ):
            user = User(
                full_name=f"Test {role}",
                email=email,
                role=role,
                status="active",
                password_hash=core.hash_password(test_password),
            )
            db.add(user)
            db.flush()
            users[email] = user.id

        for number, owner_id, seller, amount in (
            ("PAGE-001", users["employee1@phase2.test"], "Alpha Supplies", 100),
            ("PAGE-002", users["employee1@phase2.test"], "Beta Supplies", 200),
            ("PAGE-003", users["employee1@phase2.test"], "=HYPERLINK(\"https://example.invalid\",\"x\")", 300),
            ("OTHER-001", users["employee2@phase2.test"], "Other Employee Co", 400),
        ):
            (tmp_path / f"{number}.pdf").write_bytes(b"%PDF-1.4\nsynthetic test file\n%%EOF")
            file_record = InvoiceFile(
                uploaded_by=owner_id,
                original_filename=f"{number}.pdf",
                file_type="pdf",
                mime_type="application/pdf",
                file_size_bytes=10,
                storage_key=f"{number}.pdf",
                checksum_sha256=number,
            )
            db.add(file_record)
            db.flush()
            db.add(
                Invoice(
                    file_id=file_record.id,
                    invoice_number=number,
                    seller_name=seller,
                    total_amount=amount,
                    approval_status="draft",
                    validation_status="needs_review",
                    lookup_status="not_checked",
                    document_type="unknown",
                )
            )
        db.commit()

    try:
        with TestClient(api_main.app) as client:
            yield client, users, test_password
    finally:
        api_main.app.dependency_overrides.clear()
        del api_main.app.state.phase2_test_session
        del api_main.app.state.phase2_upload_path
        test_engine.dispose()


def _token(client, email, password):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_invoice_list_search_and_offset_pagination(api_env):
    client, users, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.get("/api/v1/invoices?limit=1&offset=0", headers=headers)
    second = client.get("/api/v1/invoices?limit=1&offset=1", headers=headers)
    filtered = client.get("/api/v1/invoices?search=Beta&limit=10", headers=headers)
    invalid_limit = client.get("/api/v1/invoices?limit=251", headers=headers)
    invalid_offset = client.get("/api/v1/invoices?offset=-1", headers=headers)

    assert first.status_code == second.status_code == filtered.status_code == 200
    assert len(first.json()) == len(second.json()) == 1
    assert first.json()[0]["id"] != second.json()[0]["id"]
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["invoice_number"] == "PAGE-002"
    assert invalid_limit.status_code == invalid_offset.status_code == 422


def test_invoice_list_filters_by_date_range(api_env):
    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    with client.app.state.phase2_test_session() as db:
        first = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        second = db.query(Invoice).filter_by(invoice_number="PAGE-002").one()
        first.invoice_date = datetime(2026, 1, 10, tzinfo=timezone.utc).date()
        second.invoice_date = datetime(2026, 2, 10, tzinfo=timezone.utc).date()
        db.commit()

    january = client.get("/api/v1/invoices?invoice_date_from=2026-01-01&invoice_date_to=2026-01-31", headers=headers)
    reversed_range = client.get("/api/v1/invoices?invoice_date_from=2026-02-01&invoice_date_to=2026-01-31", headers=headers)
    assert january.status_code == 200
    assert [row["invoice_number"] for row in january.json()] == ["PAGE-001"]
    assert reversed_range.status_code == 422


def test_invoice_edit_rejects_non_finite_financial_values(api_env):
    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    rows = client.get("/api/v1/invoices?limit=10", headers=headers).json()
    invoice_id = next(row["id"] for row in rows if row["invoice_number"] == "PAGE-001")
    before = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()

    for field in ("subtotal", "vat_rate", "vat_amount", "total_amount"):
        for value in (float("nan"), float("inf"), float("-inf")):
            response = client.put(
                f"/api/v1/invoices/{invoice_id}",
                content=json.dumps({field: value}, allow_nan=True).encode(),
                headers={**headers, "Content-Type": "application/json"},
            )
            assert response.status_code == 422

    after = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()
    for field in ("subtotal", "vat_rate", "vat_amount", "total_amount"):
        assert after[field] == before[field]


def test_invoice_edit_unsupported_vat_rate_marks_needs_review(api_env):
    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    with client.app.state.phase2_test_session() as db:
        invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        invoice.invoice_date = datetime.now(timezone.utc).date()
        invoice.seller_tax_code = "0312345678"
        invoice.buyer_tax_code = "0401234567"
        invoice.subtotal = 100
        invoice.vat_rate = 8
        invoice.vat_amount = 8
        invoice.total_amount = 108
        invoice_id = invoice.id
        db.commit()

    for rate, vat_amount, total in ((7, 7, 107), (20, 20, 120), (30, 30, 130)):
        response = client.put(
            f"/api/v1/invoices/{invoice_id}",
            json={"vat_rate": rate, "vat_amount": vat_amount, "total_amount": total,
                  "items": [{"description": "Synthetic line", "amount": 100}]},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["validation_status"] == "needs_review"
        assert {warning["rule"] for warning in response.json()["warnings"]} == {"VAT-RATE"}


def test_invoice_detail_and_original_file_are_owner_scoped(api_env):
    client, _, password = api_env
    employee_one = _token(client, "employee1@phase2.test", password)
    employee_two = _token(client, "employee2@phase2.test", password)
    account = _token(client, "accountant@phase2.test", password)
    own_headers = {"Authorization": f"Bearer {employee_one}"}
    other_headers = {"Authorization": f"Bearer {employee_two}"}
    account_headers = {"Authorization": f"Bearer {account}"}
    owned = client.get("/api/v1/invoices?limit=10", headers=own_headers).json()
    other_owned = client.get("/api/v1/invoices?limit=10", headers=other_headers).json()
    target_id = next(item["id"] for item in owned if item["invoice_number"] == "PAGE-001")
    other_id = next(item["id"] for item in other_owned if item["invoice_number"] == "OTHER-001")

    assert client.get(f"/api/v1/invoices/{target_id}", headers=own_headers).status_code == 200
    assert client.get(f"/api/v1/invoices/{other_id}", headers=own_headers).status_code == 404
    own_file = client.get(f"/api/v1/invoices/{target_id}/file", headers=own_headers)
    other_file = client.get(f"/api/v1/invoices/{other_id}/file", headers=own_headers)
    accountant_file = client.get(f"/api/v1/invoices/{other_id}/file", headers=account_headers)
    assert own_file.status_code == 200
    assert own_file.content.startswith(b"%PDF-1.4")
    assert other_file.status_code == 404
    assert accountant_file.status_code == 200


def test_employee_upload_and_role_file_validation(api_env):
    client, users, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    headers = {"Authorization": f"Bearer {employee}"}
    pdf = b"%PDF-1.4\nsynthetic body\n%%EOF"
    denied_accountant = client.post(
        "/api/v1/invoices/upload",
        headers={"Authorization": f"Bearer {accountant}"},
        files={"file": ("denied.pdf", pdf, "application/pdf")},
    )
    denied_admin = client.post(
        "/api/v1/invoices/upload",
        headers={"Authorization": f"Bearer {admin}"},
        files={"file": ("denied.pdf", pdf, "application/pdf")},
    )
    denied_batch_accountant = client.post(
        "/api/v1/invoices/upload/batch",
        headers={"Authorization": f"Bearer {_token(client, 'accountant@phase2.test', password)}"},
        files=[("files", ("denied.pdf", pdf, "application/pdf"))],
    )
    denied_batch_anonymous = client.post(
        "/api/v1/invoices/upload/batch",
        files=[("files", ("denied.pdf", pdf, "application/pdf"))],
    )
    unsupported = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": ("unsupported.exe", b"not an invoice", "application/octet-stream")},
    )
    invalid_pdf = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": ("invalid.pdf", b"not a PDF", "application/pdf")},
    )
    assert denied_accountant.status_code == denied_admin.status_code == 403
    assert denied_batch_accountant.status_code == 403
    assert denied_batch_anonymous.status_code == 401
    assert unsupported.status_code == invalid_pdf.status_code == 400

    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic invoice upload test")
    valid_pdf = document.tobytes()
    document.close()
    uploaded = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": ("synthetic-upload.pdf", valid_pdf, "application/pdf")},
    )
    assert uploaded.status_code == 201
    assert uploaded.json()["uploaded_by"] == users["employee1@phase2.test"]
    assert uploaded.json()["approval_status"] == "draft"
    with client.app.state.phase2_test_session() as db:
        invoice_id = uploaded.json()["id"]
        completion = db.query(Notification).filter_by(user_id=users["employee1@phase2.test"], invoice_id=invoice_id).one()
        assert "đã xử lý" in completion.message
        assert db.query(AuditLog).filter_by(actor_id=users["employee1@phase2.test"], entity_id=invoice_id, action="invoice.uploaded").count() == 1


def test_xml_upload_persists_extracted_items_and_returns_invoice_details(api_env):
    client, users, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <HDon><DLHDon><TTChung><SHDon>XML-LINE-001</SHDon><NLap>2026-11-07</NLap></TTChung>
    <NDHDon><NBan><Ten>XML Test Seller</Ten><MST>0101234567</MST></NBan>
    <NMua><Ten>XML Test Buyer</Ten><MST>0107654321</MST></NMua>
    <DSHHDVu><HHDVu><THHDVu>Test service</THHDVu><ThTien>1000</ThTien></HHDVu></DSHHDVu>
    <TToan><TgTCThue>1000</TgTCThue><TgTThue>80</TgTThue><TgTTTBSo>1080</TgTTTBSo></TToan>
    </NDHDon></DLHDon></HDon>'''
    response = client.post(
        "/api/v1/invoices/upload", headers=headers,
        files={"file": ("xml-line-items.xml", xml, "application/xml")},
    )

    assert response.status_code == 201
    invoice_id = response.json()["id"]
    returned_item = response.json()["items"][0]
    assert returned_item == {
        "id": returned_item["id"], "line_no": 1, "description": "Test service",
        "unit": None, "quantity": None, "unit_price": None, "amount": 1000.0,
    }
    assert not any(warning["rule"] == "ITEM-SUM" for warning in response.json()["warnings"])
    with client.app.state.phase2_test_session() as db:
        stored = db.query(InvoiceItem).filter_by(invoice_id=invoice_id).one()
        assert stored.description == "Test service" and float(stored.amount) == 1000
        assert stored.line_no == 1 and stored.unit is None and stored.quantity is None
        extraction = db.query(ExtractionRun).filter_by(invoice_id=invoice_id).one()
        assert extraction.extracted_json["items"][0]["description"] == "Test service"
        assert db.query(AuditLog).filter_by(
            actor_id=users["employee1@phase2.test"], entity_id=invoice_id,
            action="invoice.uploaded",
        ).count() == 1


@pytest.mark.parametrize("item_count", [1, 3, 5])
def test_raster_ocr_items_are_returned_persisted_and_validated(api_env, monkeypatch, item_count):
    from PIL import Image

    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    subtotal = item_count * 200000
    vat = item_count * 16000
    total = subtotal + vat
    lines = [
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG",
        f"Invoice No: OCR-LINE-{item_count:03d}",
        "Ngày lập: 09/11/2026",
        "Đơn vị bán hàng: Synthetic Supplier",
        "Mã số thuế: 0101234567",
        "Tên đơn vị: Synthetic Buyer",
        "Mã số thuế: 0107654321",
        "STT | Tên hàng hóa, dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
    ]
    lines.extend(
        f"{number} | Synthetic service {number} | service | 2 | 100.000 | 200.000"
        for number in range(1, item_count + 1)
    )
    lines.extend((
        f"Cộng tiền hàng: {subtotal:,}".replace(",", "."),
        "Thuế suất GTGT: 8%",
        f"Tiền thuế GTGT: {vat:,}".replace(",", "."),
        f"Tổng tiền thanh toán: {total:,}".replace(",", "."),
    ))
    monkeypatch.setattr(api_main, "text_from_file", lambda _data, _ext: ("\n".join(lines), "image-ocr"))
    image = BytesIO()
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")

    response = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": (f"ocr-lines-{item_count}.png", image.getvalue(), "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["validation_status"] == "valid"
    assert body["approval_status"] == "draft"
    assert body["lookup_status"] == "not_checked"
    assert body["subtotal"] == subtotal
    assert body["vat_amount"] == vat
    assert body["total_amount"] == total
    assert len(body["items"]) == item_count
    assert [item["line_no"] for item in body["items"]] == list(range(1, item_count + 1))
    assert not any(warning["rule"] == "ITEM-SUM" for warning in body["warnings"])

    detail = client.get(f"/api/v1/invoices/{body['id']}", headers=headers)
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == item_count
    with client.app.state.phase2_test_session() as db:
        stored = db.query(InvoiceItem).filter_by(invoice_id=body["id"]).order_by(InvoiceItem.line_no).all()
        extraction = db.query(ExtractionRun).filter_by(invoice_id=body["id"]).one()
        item_sum = db.query(ValidationResult).filter_by(
            invoice_id=body["id"], rule_code="ITEM-SUM", passed=True
        ).one()
        assert len(stored) == item_count
        assert [float(row.amount) for row in stored] == [200000.0] * item_count
        assert len(extraction.extracted_json["items"]) == item_count
        assert item_sum.passed is True


def test_raster_ocr_upload_keeps_missing_quantity_and_price_null(api_env, monkeypatch):
    from PIL import Image

    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    raw = "\n".join((
        "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", "Invoice No: OCR-NULL-001", "Ngày lập: 09/11/2026",
        "Đơn vị bán hàng: Synthetic Supplier", "Mã số thuế: 0101234567",
        "Tên đơn vị: Synthetic Buyer", "Mã số thuế: 0107654321",
        "STT | Tên hàng hóa/dịch vụ | ĐVT | Số lượng | Đơn giá | Thành tiền",
        "1 | Consulting | hour |  |  | 200.000", "Cộng tiền hàng: 200.000",
        "Thuế suất GTGT: 8%", "Tiền thuế GTGT: 16.000", "Tổng tiền thanh toán: 216.000",
    ))
    monkeypatch.setattr(api_main, "text_from_file", lambda _data, _ext: (raw, "image-ocr"))
    image = BytesIO()
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")

    response = client.post(
        "/api/v1/invoices/upload", headers=headers,
        files={"file": ("ocr-null-fields.png", image.getvalue(), "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["items"][0]["quantity"] is None
    assert response.json()["items"][0]["unit_price"] is None
    with client.app.state.phase2_test_session() as db:
        stored = db.query(InvoiceItem).filter_by(invoice_id=response.json()["id"]).one()
        assert stored.quantity is None and stored.unit_price is None
        assert float(stored.amount) == 200000


def test_uat_9f_xml_upload_extracts_fields_and_preserves_original_file(api_env):
    client, users, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    source_path = Path(__file__).resolve().parents[2] / "UAT_9F_XML_UPLOAD.xml"
    source_bytes = source_path.read_bytes()

    uploaded = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": (source_path.name, source_bytes, "application/xml")},
    )

    assert uploaded.status_code == 201
    body = uploaded.json()
    invoice_id = body["id"]
    assert body["invoice_number"] == "UAT9F-XML-001"
    assert body["invoice_date"] == "2026-11-08"
    assert body["seller_name"] == "UAT 9F Test Supplier"
    assert body["seller_tax_code"] == "0101234567"
    assert body["buyer_name"] == "FINTECH OCR Test Buyer"
    assert body["buyer_tax_code"] == "0107654321"
    assert body["subtotal"] == 200000
    assert body["vat_amount"] == 16000
    assert body["total_amount"] == 216000
    assert body["document_type"] == "einvoice"
    assert len(body["items"]) == 1
    assert body["items"][0] == {
        "id": body["items"][0]["id"], "line_no": 1,
        "description": "Test service UAT 9F XML", "unit": None,
        "quantity": None, "unit_price": None, "amount": 200000,
    }
    assert not any(warning["rule"] == "ITEM-SUM" for warning in body["warnings"])

    with client.app.state.phase2_test_session() as db:
        invoice = db.get(Invoice, invoice_id)
        extraction = db.query(ExtractionRun).filter_by(invoice_id=invoice_id).one()
        line = db.query(InvoiceItem).filter_by(invoice_id=invoice_id).one()
        assert invoice.validation_status == "valid"
        assert extraction.status == "completed"
        assert extraction.extracted_json["items"][0]["description"] == "Test service UAT 9F XML"
        assert line.quantity is None and line.unit_price is None
        assert line.amount == 200000
        stored_bytes = (client.app.state.phase2_upload_path / invoice.source_file.storage_key).read_bytes()
        assert stored_bytes == source_bytes
        assert db.query(AuditLog).filter_by(
            actor_id=users["employee1@phase2.test"], entity_id=invoice_id,
            action="invoice.uploaded",
        ).count() == 1


def test_malformed_xml_failure_is_logged_and_kept_as_failed_extraction(api_env, caplog):
    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    malformed = b"\r\n<?xml version='1.0'?><HDon><DLHDon>"

    response = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": ("malformed.xml", malformed, "application/xml")},
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == "unknown"
    assert response.json()["validation_status"] == "error"
    assert "Invoice extraction failed" in caplog.text
    with client.app.state.phase2_test_session() as db:
        run = db.query(ExtractionRun).filter_by(invoice_id=response.json()["id"]).one()
        assert run.status == "failed"
        assert "no element found" in run.error_message
        assert run.extracted_json == {}


def test_image_upload_keeps_original_and_records_tesseract_unavailable(api_env, monkeypatch):
    from PIL import Image

    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {token}"}
    image = BytesIO()
    Image.new("RGB", (8, 8), "white").save(image, format="PNG")
    original_bytes = image.getvalue()

    def unavailable(_data, _ext):
        raise RuntimeError("Tesseract OCR engine is unavailable")

    monkeypatch.setattr(api_main, "text_from_file", unavailable)
    response = client.post(
        "/api/v1/invoices/upload",
        headers=headers,
        files={"file": ("ocr-unavailable.png", original_bytes, "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["validation_status"] == "error"
    assert body["document_type"] == "unknown"
    with client.app.state.phase2_test_session() as db:
        invoice = db.get(Invoice, body["id"])
        run = db.query(ExtractionRun).filter_by(invoice_id=body["id"]).one()
        assert run.status == "failed"
        assert "Tesseract OCR engine is unavailable" in run.error_message
        stored_bytes = (client.app.state.phase2_upload_path / invoice.source_file.storage_key).read_bytes()
        assert stored_bytes == original_bytes


def test_optional_phase2_columns_are_written_when_present(api_env):
    client, users, password = api_env
    TestSession = client.app.state.phase2_test_session
    test_engine = TestSession.kw["bind"]
    with test_engine.begin() as connection:
        connection.exec_driver_sql("ALTER TABLE invoices ADD COLUMN submitted_at DATETIME")
        connection.exec_driver_sql("ALTER TABLE invoices ADD COLUMN source_type VARCHAR(10)")
        connection.exec_driver_sql("ALTER TABLE invoice_files ADD COLUMN storage_url TEXT")
        connection.exec_driver_sql("ALTER TABLE invoice_lookups ADD COLUMN query_snapshot JSON")
        connection.exec_driver_sql("ALTER TABLE invoice_lookups ADD COLUMN notes TEXT")
        connection.exec_driver_sql("ALTER TABLE notifications ADD COLUMN type VARCHAR(40)")
        connection.exec_driver_sql("ALTER TABLE notifications ADD COLUMN read_at DATETIME")
    api_main._SCHEMA_COLUMN_CACHE.pop(test_engine, None)

    employee = _token(client, "employee1@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    xml = b"""<HDon><DLHDon><TTChung><SHDon>OPT-20261107</SHDon><KHHDon>1C26OPT</KHHDon><NLap>2026-11-07</NLap></TTChung><NDHDon><NBan><Ten>Optional Column Seller</Ten><MST>0123456789</MST></NBan><NMua><Ten>Optional Column Buyer</Ten><MST>9876543210</MST></NMua></NDHDon><TToan><TgTCThue>1000</TgTCThue><TgTThue>100</TgTThue><TgTTTBSo>1100</TgTTTBSo></TToan></DLHDon></HDon>"""
    uploaded = client.post(
        "/api/v1/invoices/upload",
        headers={"Authorization": f"Bearer {employee}"},
        files={"file": ("optional-columns.xml", xml, "application/xml")},
    )
    assert uploaded.status_code == 201
    invoice_id = uploaded.json()["id"]
    corrected = client.put(
        f"/api/v1/invoices/{invoice_id}",
        headers={"Authorization": f"Bearer {employee}"},
        json={
            "invoice_number": "OPT-20261107",
            "invoice_symbol": "1C26OPT",
            "invoice_date": "2026-11-07",
            "seller_name": "Optional Column Seller",
            "seller_tax_code": "0123456789",
            "buyer_name": "Optional Column Buyer",
            "buyer_tax_code": "9876543210",
            "subtotal": 1000,
            "vat_rate": 10,
            "vat_amount": 100,
            "total_amount": 1100,
            "items": [{"description": "test item", "amount": 1000}],
        },
    )
    assert corrected.status_code == 200
    looked_up = client.post(
        f"/api/v1/invoices/{invoice_id}/lookup",
        headers={"Authorization": f"Bearer {accountant}"},
        json={"result": "verified", "note": "manual test lookup"},
    )
    assert looked_up.status_code == 200
    lookup_history = client.get(
        f"/api/v1/invoices/{invoice_id}/lookups",
        headers={"Authorization": f"Bearer {employee}"},
    )
    assert lookup_history.status_code == 200
    assert len(lookup_history.json()) == 1
    assert lookup_history.json()[0]["note"] == "manual test lookup"
    assert lookup_history.json()[0]["query_snapshot"]["invoice_number"] == "OPT-20261107"
    submitted = client.post(
        f"/api/v1/invoices/{invoice_id}/submit",
        headers={"Authorization": f"Bearer {employee}"},
    )
    assert submitted.status_code == 200

    notifications = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {employee}"})
    assert notifications.status_code == 200
    upload_notification = next(item for item in notifications.json() if item["invoice_id"] == invoice_id)
    assert upload_notification["is_read"] is False
    assert upload_notification["type"] == "extraction_finished"
    read = client.patch(
        f"/api/v1/notifications/{upload_notification['id']}/read",
        headers={"Authorization": f"Bearer {employee}"},
    )
    assert read.status_code == 200
    first_read_state = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {employee}"})
    first_read_at = next(item["read_at"] for item in first_read_state.json() if item["id"] == upload_notification["id"])
    read_again = client.patch(
        f"/api/v1/notifications/{upload_notification['id']}/read",
        headers={"Authorization": f"Bearer {employee}"},
    )
    assert read_again.status_code == 200
    refreshed = client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {employee}"})
    refreshed_note = next(item for item in refreshed.json() if item["id"] == upload_notification["id"])
    assert refreshed_note["read_at"] is not None
    assert refreshed_note["read_at"] == first_read_at

    with TestSession() as db:
        stored_invoice = db.execute(
            text("SELECT source_type, submitted_at FROM invoices WHERE id=:id"), {"id": invoice_id}
        ).one()
        stored_file = db.execute(
            text("SELECT storage_url FROM invoice_files WHERE id=:id"), {"id": uploaded.json()["file_id"]}
        ).scalar_one()
        lookup_row = db.execute(
            text("SELECT query_snapshot, notes FROM invoice_lookups WHERE invoice_id=:id"),
            {"id": invoice_id},
        ).one()
        notification_row = db.execute(
            text("SELECT type, read_at FROM notifications WHERE id=:id"),
            {"id": upload_notification["id"]},
        ).one()
    snapshot = lookup_row.query_snapshot
    if isinstance(snapshot, str):
        snapshot = json.loads(snapshot)
    assert stored_invoice.source_type == "xml" and stored_invoice.submitted_at is not None
    assert stored_file == f"/api/v1/invoices/{invoice_id}/file"
    assert snapshot["invoice_number"] == "OPT-20261107"
    assert snapshot["seller_tax_code"] == "0123456789"
    assert snapshot["invoice_date"] == "2026-11-07"
    assert snapshot["total_amount"] == "1100.00"
    assert lookup_row.notes == "manual test lookup"
    assert notification_row.type == "extraction_finished" and notification_row.read_at is not None


def test_employee_batch_upload_returns_per_file_results(api_env):
    client, users, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {employee}"}
    before = client.get("/api/v1/invoices?limit=250", headers=headers).json()
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic batch invoice")
    pdf = document.tobytes()
    document.close()

    response = client.post(
        "/api/v1/invoices/upload/batch",
        headers=headers,
        files=[
            ("files", ("batch-one.pdf", pdf, "application/pdf")),
            ("files", ("batch-invalid.exe", b"not an invoice", "application/octet-stream")),
            ("files", ("batch-two.pdf", pdf, "application/pdf")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["total"], body["created"], body["rejected"]) == (3, 2, 1)
    assert [result["status"] for result in body["results"]] == ["created", "rejected", "created"]
    assert body["results"][1]["http_status"] == 400
    assert all(result["invoice"]["uploaded_by"] == users["employee1@phase2.test"] for result in (body["results"][0], body["results"][2]))
    after = client.get("/api/v1/invoices?limit=250", headers=headers).json()
    assert len(after) == len(before) + 2
    assert len(list(client.app.state.phase2_upload_path.glob("*.pdf"))) == 6


def test_employee_can_edit_line_items_and_subtotal_is_validated(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {employee}"}
    with client.app.state.phase2_test_session() as db:
        invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        invoice.invoice_date = datetime(2026, 1, 10, tzinfo=timezone.utc).date()
        invoice.seller_tax_code = "0312345678"
        invoice.buyer_tax_code = "0401234567"
        invoice.subtotal = 100
        invoice.vat_rate = 0
        invoice.vat_amount = 0
        invoice.total_amount = 100
        invoice_id = invoice.id
        db.commit()

    valid = client.put(
        f"/api/v1/invoices/{invoice_id}",
        headers=headers,
        json={"items": [
            {"description": "Consulting", "unit": "hour", "quantity": 2, "unit_price": 20, "amount": 40},
            {"description": "Support", "unit": "service", "quantity": 1, "unit_price": 60, "amount": 60},
        ]},
    )
    assert valid.status_code == 200
    assert valid.json()["validation_status"] == "valid"
    assert [(item["line_no"], item["unit"], item["amount"]) for item in valid.json()["items"]] == [(1, "hour", 40), (2, "service", 60)]

    invalid_sum = client.put(
        f"/api/v1/invoices/{invoice_id}",
        headers=headers,
        json={"items": [
            {"description": "Consulting", "unit": "hour", "quantity": 2, "unit_price": 20, "amount": 40},
            {"description": "Support", "unit": "service", "quantity": 1, "unit_price": 60, "amount": 65},
        ]},
    )
    assert invalid_sum.status_code == 200
    assert invalid_sum.json()["validation_status"] == "needs_review"
    assert any(warning["rule"] == "ITEM-SUM" for warning in invalid_sum.json()["warnings"])
    with client.app.state.phase2_test_session() as db:
        assert db.query(InvoiceCorrection).filter(InvoiceCorrection.invoice_id == invoice_id, InvoiceCorrection.field_name == "items[2].amount").count() == 1


def test_invoice_edit_line_item_validation_rejects_bad_input_without_mutation(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {employee}"}
    with client.app.state.phase2_test_session() as db:
        invoice_id = db.query(Invoice.id).filter_by(invoice_number="PAGE-001").scalar()
    for item in (
        {"description": "   ", "amount": 1},
        {"description": "Item", "amount": -1},
        {"description": "Item", "amount": float("inf")},
    ):
        response = client.put(
            f"/api/v1/invoices/{invoice_id}",
            headers={**headers, "Content-Type": "application/json"},
            content=json.dumps({"items": [item]}, allow_nan=True).encode(),
        )
        assert response.status_code == 422
    with client.app.state.phase2_test_session() as db:
        assert db.query(InvoiceCorrection).filter(InvoiceCorrection.invoice_id == invoice_id, InvoiceCorrection.field_name.like("items[%")).count() == 0


def test_upload_size_limit_uses_configured_value_without_creating_records(api_env, monkeypatch):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    monkeypatch.setattr(core.settings, "max_upload_mb", 1)
    too_large = client.post(
        "/api/v1/invoices/upload",
        headers={"Authorization": f"Bearer {employee}"},
        files={"file": ("too-large.pdf", b"%PDF-1.4" + b"x" * (1024 * 1024), "application/pdf")},
    )
    assert too_large.status_code == 400
    assert too_large.json()["detail"] == "File rỗng hoặc vượt giới hạn 1 MB"
    with client.app.state.phase2_test_session() as db:
        assert db.query(InvoiceFile).count() == 4
        assert db.query(Invoice).count() == 4


def test_upload_commit_failure_removes_only_new_file(api_env, monkeypatch):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    upload_path = client.app.state.phase2_upload_path
    files_before = set(upload_path.iterdir())
    with client.app.state.phase2_test_session() as db:
        invoices_before = db.query(Invoice).count()
        file_records_before = db.query(InvoiceFile).count()

    def fail_commit(self):
        raise RuntimeError("synthetic database commit failure")

    monkeypatch.setattr(Session, "commit", fail_commit)
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic invoice for failed transaction")
    valid_pdf = document.tobytes()
    document.close()
    with pytest.raises(RuntimeError, match="synthetic database commit failure"):
        client.post(
            "/api/v1/invoices/upload",
            headers={"Authorization": f"Bearer {employee}"},
            files={"file": ("failed-transaction.pdf", valid_pdf, "application/pdf")},
        )

    with client.app.state.phase2_test_session() as db:
        assert db.query(Invoice).count() == invoices_before
        assert db.query(InvoiceFile).count() == file_records_before
    assert set(upload_path.iterdir()) == files_before


def test_upload_uncertain_commit_keeps_file_when_record_exists(api_env, monkeypatch):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    upload_path = client.app.state.phase2_upload_path
    original_commit = Session.commit

    def commit_then_lose_acknowledgment(self):
        original_commit(self)
        raise RuntimeError("synthetic lost commit acknowledgment")

    monkeypatch.setattr(Session, "commit", commit_then_lose_acknowledgment)
    document = fitz.open()
    document.new_page().insert_text((72, 72), "Synthetic invoice with uncertain commit")
    valid_pdf = document.tobytes()
    document.close()
    with pytest.raises(RuntimeError, match="synthetic lost commit acknowledgment"):
        client.post(
            "/api/v1/invoices/upload",
            headers={"Authorization": f"Bearer {employee}"},
            files={"file": ("uncertain-commit.pdf", valid_pdf, "application/pdf")},
        )

    with client.app.state.phase2_test_session() as db:
        invoice_count = db.query(Invoice).count()
        file_records = db.query(InvoiceFile).all()
        assert invoice_count == 5
        assert len(file_records) == 5
        new_file = next(record for record in file_records if record.original_filename == "uncertain-commit.pdf")
        assert (upload_path / new_file.storage_key).is_file()


def test_invoice_write_workflow_enforces_roles_owner_and_state(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    other_employee = _token(client, "employee2@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    owner_headers = {"Authorization": f"Bearer {employee}"}
    other_headers = {"Authorization": f"Bearer {other_employee}"}
    accountant_headers = {"Authorization": f"Bearer {accountant}"}
    admin_headers = {"Authorization": f"Bearer {admin}"}
    own_rows = client.get("/api/v1/invoices?limit=20", headers=owner_headers).json()
    other_rows = client.get("/api/v1/invoices?limit=20", headers=other_headers).json()
    own_id = next(row["id"] for row in own_rows if row["invoice_number"] == "PAGE-001")
    other_id = next(row["id"] for row in other_rows if row["invoice_number"] == "OTHER-001")

    assert client.put(f"/api/v1/invoices/{own_id}", json={"seller_name": "Forbidden"}, headers=accountant_headers).status_code == 403
    assert client.put(f"/api/v1/invoices/{own_id}", json={"seller_name": "Forbidden"}, headers=admin_headers).status_code == 403
    assert client.put(f"/api/v1/invoices/{other_id}", json={"seller_name": "Tampered"}, headers=owner_headers).status_code == 404
    changed = client.put(f"/api/v1/invoices/{own_id}", json={"seller_name": "Updated Supplier"}, headers=owner_headers)
    assert changed.status_code == 200
    assert changed.json()["seller_name"] == "Updated Supplier"
    submitted = client.post(f"/api/v1/invoices/{own_id}/submit", headers=owner_headers)
    assert submitted.status_code == 200
    assert submitted.json()["submitted_at"]
    accountant_notes = client.get("/api/v1/notifications", headers=accountant_headers).json()
    admin_notes = client.get("/api/v1/notifications", headers=admin_headers).json()
    assert any(note["title"] == "Hóa đơn chờ phê duyệt" and "được gửi bởi Test employee" in note["message"] for note in accountant_notes)
    assert any(note["title"] == "Hóa đơn chờ phê duyệt" and "được gửi bởi Test employee" in note["message"] for note in admin_notes)
    assert client.put(f"/api/v1/invoices/{own_id}", json={"seller_name": "Pending edit"}, headers=owner_headers).status_code == 400
    assert client.post(f"/api/v1/invoices/{own_id}/submit", headers=owner_headers).status_code == 400

    assert client.post(f"/api/v1/invoices/{own_id}/approval", json={"action": "approved"}, headers=owner_headers).status_code == 403
    assert client.post(f"/api/v1/invoices/{own_id}/approval", json={"action": "invalid"}, headers=accountant_headers).status_code == 400
    missing_reason = client.post(f"/api/v1/invoices/{own_id}/approval", json={"action": "rejected"}, headers=accountant_headers)
    assert missing_reason.status_code == 400
    rejected = client.post(f"/api/v1/invoices/{own_id}/approval", json={"action": "rejected", "reason": "Synthetic correction required"}, headers=accountant_headers)
    assert rejected.status_code == 200
    assert rejected.json()["approval_status"] == "rejected"
    corrected = client.put(f"/api/v1/invoices/{own_id}", json={"seller_name": "Resubmitted Supplier"}, headers=owner_headers)
    assert corrected.status_code == 200
    assert corrected.json()["approval_status"] == "draft"
    assert client.post(f"/api/v1/invoices/{own_id}/submit", headers=owner_headers).status_code == 200
    for reviewer_headers in (accountant_headers, admin_headers):
        reviewer_notifications = client.get("/api/v1/notifications", headers=reviewer_headers).json()
        assert sum(note["invoice_id"] == own_id for note in reviewer_notifications) == 2
    approved = client.post(f"/api/v1/invoices/{own_id}/approval", json={"action": "approved"}, headers=admin_headers)
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "approved"

    with client.app.state.phase2_test_session() as db:
        actions = db.query(InvoiceApproval.action).filter_by(invoice_id=own_id).order_by(InvoiceApproval.id).all()
        corrections = db.query(InvoiceCorrection).filter_by(invoice_id=own_id).all()
        audit_actions = {row.action for row in db.query(AuditLog).filter_by(entity_id=own_id).all()}
        owner_id = db.query(User.id).filter_by(email="employee1@phase2.test").scalar()
        owner_notifications = db.query(Notification).filter_by(user_id=owner_id, invoice_id=own_id).all()
    assert [row[0] for row in actions] == ["submitted", "rejected", "submitted", "approved"]
    assert len(corrections) == 2
    assert {"invoice.corrected", "invoice.submitted", "invoice.rejected", "invoice.approved"} <= audit_actions
    assert len(owner_notifications) == 2
    assert all(note.title == "Kết quả phê duyệt" for note in owner_notifications)
    owner_messages = {note.message for note in owner_notifications}
    assert f"Hóa đơn #{own_id} bị từ chối – Lý do: Synthetic correction required" in owner_messages
    assert f"Hóa đơn #{own_id} đã được phê duyệt" in owner_messages


def test_invoice_processing_error_cannot_be_submitted(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {employee}"}
    with client.app.state.phase2_test_session() as db:
        invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        invoice.validation_status = "error"
        invoice_id = invoice.id
        db.commit()

    response = client.post(f"/api/v1/invoices/{invoice_id}/submit", headers=headers)
    assert response.status_code == 400

    with client.app.state.phase2_test_session() as db:
        assert db.get(Invoice, invoice_id).approval_status == "draft"
        assert db.query(InvoiceApproval).filter_by(invoice_id=invoice_id).count() == 0
        assert db.query(AuditLog).filter_by(entity_type="invoice", entity_id=invoice_id).count() == 0
        assert db.query(Notification).filter_by(invoice_id=invoice_id).count() == 0


def test_invoice_lookup_is_role_scoped_and_only_for_einvoice(api_env):
    client, users, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    employee_headers = {"Authorization": f"Bearer {employee}"}
    accountant_headers = {"Authorization": f"Bearer {accountant}"}
    admin_headers = {"Authorization": f"Bearer {admin}"}
    with client.app.state.phase2_test_session() as db:
        e_invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        e_invoice.document_type = "einvoice"
        e_invoice.invoice_symbol = "1C26TAA"
        e_invoice.seller_tax_code = "0312345678"
        e_invoice.invoice_date = datetime(2026, 1, 10, tzinfo=timezone.utc).date()
        e_invoice.total_amount = 100
        e_invoice.validation_status = "needs_review"
        e_invoice.approval_status = "approved"
        bill = db.query(Invoice).filter_by(invoice_number="PAGE-002").one()
        bill.document_type = "bill"
        bill.lookup_status = "not_applicable"
        db.commit()
        e_invoice_id = e_invoice.id
        bill_id = bill.id
        unknown_id = db.query(Invoice).filter_by(invoice_number="PAGE-003").one().id

    assert client.post(f"/api/v1/invoices/{e_invoice_id}/lookup", json={"result": "verified"}, headers=employee_headers).status_code == 403
    assert client.post(f"/api/v1/invoices/{unknown_id}/lookup", json={"result": "verified"}, headers=accountant_headers).status_code == 400
    assert client.post(f"/api/v1/invoices/{bill_id}/lookup", json={"result": "verified"}, headers=accountant_headers).status_code == 400
    assert client.post(f"/api/v1/invoices/{e_invoice_id}/lookup", json={"result": "invalid"}, headers=accountant_headers).status_code == 400
    with client.app.state.phase2_test_session() as db:
        invoice = db.get(Invoice, e_invoice_id)
        invoice.invoice_symbol = None
        db.commit()
    missing_fields = client.post(f"/api/v1/invoices/{e_invoice_id}/lookup", json={"result": "verified"}, headers=accountant_headers)
    assert missing_fields.status_code == 400
    assert "invoice_symbol" in missing_fields.json()["detail"]
    with client.app.state.phase2_test_session() as db:
        invoice = db.get(Invoice, e_invoice_id)
        invoice.invoice_symbol = "1C26TAA"
        db.commit()
    recorded = client.post(f"/api/v1/invoices/{e_invoice_id}/lookup", json={"result": "verified", "note": "Synthetic manual check"}, headers=accountant_headers)
    assert recorded.status_code == 200
    assert recorded.json()["lookup_status"] == "verified"
    repeated = client.post(f"/api/v1/invoices/{e_invoice_id}/lookup", json={"result": "mismatch", "note": "Synthetic second manual check"}, headers=admin_headers)
    assert repeated.status_code == 200
    assert repeated.json()["lookup_status"] == "mismatch"
    assert repeated.json()["validation_status"] == "needs_review"
    assert repeated.json()["approval_status"] == "approved"
    with client.app.state.phase2_test_session() as db:
        lookups = db.query(InvoiceLookup).filter_by(invoice_id=e_invoice_id).order_by(InvoiceLookup.id).all()
        accountant_id = db.query(User.id).filter_by(email="accountant@phase2.test").scalar()
        admin_id = db.query(User.id).filter_by(email="admin@phase2.test").scalar()
        assert len(lookups) == 2
        assert lookups[0].checked_by == accountant_id and lookups[0].note == "Synthetic manual check"
        assert lookups[1].checked_by == admin_id and lookups[1].note == "Synthetic second manual check"
        assert db.query(InvoiceLookup).filter_by(invoice_id=bill_id).count() == 0
        assert db.get(Invoice, bill_id).lookup_status == "not_applicable"
        assert db.query(AuditLog).filter_by(entity_id=e_invoice_id, action="invoice.lookup_recorded").count() == 2
    history = client.get(f"/api/v1/invoices/{e_invoice_id}/lookups", headers=accountant_headers)
    assert history.status_code == 200
    assert [entry["result"] for entry in history.json()] == ["mismatch", "verified"]
    assert history.json()[0]["checked_by_name"] == "Test admin"


def test_invoice_correction_history_is_owner_scoped_chronological_and_paginated(api_env):
    client, users, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    other_employee = _token(client, "employee2@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    with client.app.state.phase2_test_session() as db:
        invoice_id = db.query(Invoice.id).filter_by(invoice_number="PAGE-001").scalar()
        first = InvoiceCorrection(
            invoice_id=invoice_id,
            field_name="seller_name",
            old_value="Old Supplier",
            new_value="Middle Supplier",
            corrected_by=users["employee1@phase2.test"],
            corrected_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        second = InvoiceCorrection(
            invoice_id=invoice_id,
            field_name="seller_name",
            old_value="Middle Supplier",
            new_value="New Supplier",
            corrected_by=users["employee1@phase2.test"],
            corrected_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        db.add_all([first, second])
        db.commit()
        expected_ids = [first.id, second.id]

    path = f"/api/v1/invoices/{invoice_id}/corrections"
    assert client.get(path).status_code == 401
    owner = client.get(path, headers={"Authorization": f"Bearer {employee}"})
    assert owner.status_code == 200
    assert [row["id"] for row in owner.json()] == expected_ids
    assert [row["old_value"] for row in owner.json()] == ["Old Supplier", "Middle Supplier"]
    assert [row["new_value"] for row in owner.json()] == ["Middle Supplier", "New Supplier"]
    page = client.get(path+"?limit=1&offset=1", headers={"Authorization": f"Bearer {employee}"})
    assert page.status_code == 200 and [row["id"] for row in page.json()] == [second.id]
    assert client.get(path, headers={"Authorization": f"Bearer {other_employee}"}).status_code == 404
    assert client.get(path, headers={"Authorization": f"Bearer {accountant}"}).status_code == 200
    assert client.get(path, headers={"Authorization": f"Bearer {admin}"}).status_code == 200


def test_invoice_lookup_history_is_owner_scoped_ordered_and_paginated(api_env):
    client, users, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    other_employee = _token(client, "employee2@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    with client.app.state.phase2_test_session() as db:
        invoice_id = db.query(Invoice.id).filter_by(invoice_number="PAGE-001").scalar()
        old = InvoiceLookup(
            invoice_id=invoice_id,
            checked_by=users["accountant@phase2.test"],
            result="mismatch",
            note="older check",
            checked_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        recent = InvoiceLookup(
            invoice_id=invoice_id,
            checked_by=users["admin@phase2.test"],
            result="verified",
            note="latest check",
            checked_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        db.add_all([old, recent])
        db.commit()
        expected_ids = [recent.id, old.id]

    path = f"/api/v1/invoices/{invoice_id}/lookups"
    assert client.get(path).status_code == 401
    owner = client.get(path, headers={"Authorization": f"Bearer {employee}"})
    assert owner.status_code == 200
    assert [row["id"] for row in owner.json()] == expected_ids
    assert [row["result"] for row in owner.json()] == ["verified", "mismatch"]
    assert [row["note"] for row in owner.json()] == ["latest check", "older check"]
    assert owner.json()[0]["query_snapshot"] is None
    assert [row["id"] for row in client.get(path+"?limit=1", headers={"Authorization": f"Bearer {employee}"}).json()] == [recent.id]
    assert [row["id"] for row in client.get(path+"?limit=1&offset=1", headers={"Authorization": f"Bearer {employee}"}).json()] == [old.id]
    assert client.get(path, headers={"Authorization": f"Bearer {other_employee}"}).status_code == 404
    assert client.get(path, headers={"Authorization": f"Bearer {accountant}"}).status_code == 200
    assert client.get(path, headers={"Authorization": f"Bearer {admin}"}).status_code == 200


def test_ranking_rejects_unknown_period(api_env):
    client, _, password = api_env
    token = _token(client, "employee1@phase2.test", password)
    response = client.get(
        "/api/v1/ranking?period=decade",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


def test_dashboard_totals_are_scoped_by_role(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    employee_summary = client.get(
        "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {employee}"}
    )
    accountant_summary = client.get(
        "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {accountant}"}
    )
    admin_summary = client.get(
        "/api/v1/dashboard/summary", headers={"Authorization": f"Bearer {admin}"}
    )
    assert employee_summary.status_code == accountant_summary.status_code == admin_summary.status_code == 200
    assert employee_summary.json()["total_invoices"] == 3
    assert employee_summary.json()["total_amount"] == 600
    assert accountant_summary.json()["total_invoices"] == 4
    assert accountant_summary.json()["total_amount"] == 1000
    assert admin_summary.json()["total_invoices"] == 4
    assert admin_summary.json()["total_amount"] == 1000
    for response in (employee_summary, accountant_summary, admin_summary):
        data = response.json()
        assert sum(month["invoice_count"] for month in data["monthly"]) == data["total_invoices"]
        assert sum(month["amount"] for month in data["monthly"]) == data["total_amount"]


def test_dashboard_months_are_chronological_and_created_at_uses_business_timezone(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    with client.app.state.phase2_test_session() as db:
        old = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        dated = db.query(Invoice).filter_by(invoice_number="PAGE-002").one()
        timestamped = db.query(Invoice).filter_by(invoice_number="PAGE-003").one()
        old.invoice_date = datetime(2017, 10, 16).date()
        dated.invoice_date = datetime(2026, 11, 8).date()
        timestamped.invoice_date = None
        timestamped.created_at = datetime(2026, 10, 31, 17, 30, tzinfo=timezone.utc)
        db.commit()

    response = client.get(
        "/api/v1/dashboard/summary",
        headers={"Authorization": f"Bearer {employee}"},
    )
    assert response.status_code == 200
    summary = response.json()
    assert [month["month"] for month in summary["monthly"]] == ["2017-10", "2026-11"]
    assert summary["monthly"] == [
        {"month": "2017-10", "vat_amount": 0, "total_amount": 100, "amount": 100, "invoice_count": 1},
        {"month": "2026-11", "vat_amount": 0, "total_amount": 500, "amount": 500, "invoice_count": 2},
    ]
    assert summary["total_amount"] == 600


def test_dashboard_exposes_validation_supplier_and_monthly_tax_totals(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {employee}"}
    with client.app.state.phase2_test_session() as db:
        invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        invoice.invoice_date = datetime(2026, 1, 10, tzinfo=timezone.utc).date()
        invoice.seller_name = "January Supplier"
        invoice.validation_status = "valid"
        invoice.total_amount = 108
        invoice.vat_amount = 8
        db.commit()

    january = client.get("/api/v1/dashboard/summary?invoice_date_from=2026-01-01&invoice_date_to=2026-01-31", headers=headers)
    reversed_range = client.get("/api/v1/dashboard/summary?invoice_date_from=2026-02-01&invoice_date_to=2026-01-31", headers=headers)
    assert january.status_code == 200
    data = january.json()
    assert (data["total_invoices"], data["valid"], data["needs_review"], data["error"]) == (1, 1, 0, 0)
    assert data["monthly"] == [{"month": "2026-01", "vat_amount": 8, "total_amount": 108, "amount": 108, "invoice_count": 1}]
    assert data["suppliers"] == [{"supplier": "January Supplier", "invoice_count": 1, "total_amount": 108}]
    assert reversed_range.status_code == 422


def test_database_chat_answers_are_role_scoped(api_env):
    client, _, password = api_env
    employee = _token(client, "employee1@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    employee_answer = client.post(
        "/api/v1/chatbot/ask",
        json={"question": "What is my total amount?"},
        headers={"Authorization": f"Bearer {employee}"},
    )
    accountant_answer = client.post(
        "/api/v1/chatbot/ask",
        json={"question": "What is my total amount?"},
        headers={"Authorization": f"Bearer {accountant}"},
    )
    assert employee_answer.status_code == accountant_answer.status_code == 200
    assert employee_answer.json()["count_visible_invoices"] == 3
    assert accountant_answer.json()["count_visible_invoices"] == 4
    assert employee_answer.json()["mode"] == "database-demo"


def test_user_management_profile_password_and_disabled_account(api_env):
    client, users, test_password = api_env
    admin = _token(client, "admin@phase2.test", test_password)
    employee = _token(client, "employee1@phase2.test", test_password)
    initial_password = secrets.token_urlsafe(24)
    changed_password_value = secrets.token_urlsafe(24)
    wrong_password_value = secrets.token_urlsafe(24)
    headers = {"Authorization": f"Bearer {admin}"}
    employee_headers = {"Authorization": f"Bearer {employee}"}
    assert client.get("/api/v1/users", headers=employee_headers).status_code == 403
    assert client.get("/api/v1/directory/employees", headers=employee_headers).status_code == 403
    assert client.get("/api/v1/users", headers=headers).status_code == 200
    assert client.get("/api/v1/directory/employees", headers=headers).status_code == 200
    create_body = {
        "full_name": "Temporary Phase Two User",
        "email": "temporary-user@example.com",
        "password": initial_password,
        "role": "employee",
    }
    denied = client.post(
        "/api/v1/users", json=create_body, headers={"Authorization": f"Bearer {employee}"}
    )
    created = client.post("/api/v1/users", json=create_body, headers=headers)
    assert denied.status_code == 403
    assert created.status_code == 201, created.text
    assert "password_hash" not in created.json()
    duplicate = client.post("/api/v1/users", json=create_body, headers=headers)
    assert duplicate.status_code == 409

    new_user_id = created.json()["id"]
    user_login = client.post(
        "/api/v1/auth/login",
        json={"email": create_body["email"], "password": create_body["password"]},
    )
    assert user_login.status_code == 200
    user_token = user_login.json()["access_token"]
    user_headers = {"Authorization": f"Bearer {user_token}"}
    assert client.get("/api/v1/profile", headers=user_headers).status_code == 200
    wrong_password = client.put(
        "/api/v1/profile/password",
        json={"current_password": wrong_password_value, "new_password": changed_password_value},
        headers=user_headers,
    )
    changed_password = client.put(
        "/api/v1/profile/password",
        json={"current_password": create_body["password"], "new_password": changed_password_value},
        headers=user_headers,
    )
    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": create_body["email"], "password": create_body["password"]},
    )
    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": create_body["email"], "password": changed_password_value},
    )
    assert wrong_password.status_code == 400
    assert changed_password.status_code == 200
    assert old_login.status_code == 401
    assert new_login.status_code == 200

    updated_profile = client.patch(
        "/api/v1/profile",
        json={"full_name": "Updated Phase Two User"},
        headers=user_headers,
    )
    disabled = client.patch(
        f"/api/v1/users/{new_user_id}",
        json={"status": "disabled"},
        headers=headers,
    )
    inactive_token = client.get("/api/v1/auth/me", headers=user_headers)
    invalid_token = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert updated_profile.status_code == 200
    assert disabled.status_code == 200
    assert inactive_token.status_code == 401
    assert invalid_token.status_code == 401


def test_admin_user_patch_rejects_null_non_nullable_fields(api_env):
    client, users, password = api_env
    admin = _token(client, "admin@phase2.test", password)
    headers = {"Authorization": f"Bearer {admin}"}
    target_id = users["employee1@phase2.test"]
    original = client.get("/api/v1/users", headers=headers).json()
    original_name = next(user["full_name"] for user in original if user["id"] == target_id)
    for invalid_patch in (
        {"full_name": None},
        {"role": None},
        {"status": None},
        {"full_name": ""},
        {"full_name": "x" * 151},
    ):
        response = client.patch(
            f"/api/v1/users/{target_id}", json=invalid_patch, headers=headers
        )
        assert response.status_code == 422
    after = client.get("/api/v1/users", headers=headers).json()
    assert next(user["full_name"] for user in after if user["id"] == target_id) == original_name


def test_excel_export_keeps_untrusted_invoice_text_as_text(api_env):
    client, _, password = api_env
    token = _token(client, "accountant@phase2.test", password)
    employee = _token(client, "employee1@phase2.test", password)
    denied = client.get(
        "/api/v1/reports/export", headers={"Authorization": f"Bearer {employee}"}
    )
    assert denied.status_code == 403
    response = client.get(
        "/api/v1/reports/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content), data_only=False)
    sheet = workbook["Invoices"]
    exported = next(row for row in sheet.iter_rows(min_row=2) if row[1].value == "PAGE-003")
    assert exported[3].data_type == "s"
    assert exported[3].value.startswith("'=")


def test_excel_export_applies_date_supplier_and_status_filters(api_env):
    client, _, password = api_env
    accountant = _token(client, "accountant@phase2.test", password)
    headers = {"Authorization": f"Bearer {accountant}"}
    with client.app.state.phase2_test_session() as db:
        invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        invoice.invoice_date = datetime(2026, 1, 10, tzinfo=timezone.utc).date()
        invoice.seller_name = "Filtered Supplier"
        invoice.approval_status = "approved"
        db.commit()

    response = client.get(
        "/api/v1/reports/export?search=Filtered%20Supplier&approval_status=approved&invoice_date_from=2026-01-01&invoice_date_to=2026-01-31",
        headers=headers,
    )
    assert response.status_code == 200
    sheet = load_workbook(BytesIO(response.content), data_only=True)["Invoices"]
    rows = list(sheet.iter_rows(min_row=2, values_only=True))
    assert len(rows) == 1
    assert rows[0][1] == "PAGE-001"
    assert rows[0][2] is None
    assert rows[0][3] == "Filtered Supplier"


def test_report_summary_export_filters_and_line_items_do_not_duplicate_invoice_totals(api_env):
    client, _, password = api_env
    accountant = _token(client, "accountant@phase2.test", password)
    employee = _token(client, "employee1@phase2.test", password)
    headers = {"Authorization": f"Bearer {accountant}"}
    with client.app.state.phase2_test_session() as db:
        invoice = db.query(Invoice).filter_by(invoice_number="PAGE-001").one()
        invoice.invoice_date = datetime(2026, 2, 12).date()
        invoice.approval_status = "approved"
        invoice.validation_status = "valid"
        invoice.document_type = "einvoice"
        invoice.total_amount = 150
        db.add_all([
            InvoiceItem(invoice_id=invoice.id, line_no=1, description="First service", quantity=1, unit_price=100, amount=100),
            InvoiceItem(invoice_id=invoice.id, line_no=2, description='=HYPERLINK("https://example.invalid","x")', quantity=None, unit_price=None, amount=50),
        ])
        db.commit()

    params = "approval_status=approved&validation_status=valid&document_type=einvoice&invoice_date_from=2026-02-01&invoice_date_to=2026-02-28"
    summary = client.get(f"/api/v1/reports/summary?{params}", headers=headers)
    assert summary.status_code == 200
    assert summary.json() == {"invoice_count": 1, "total_amount": 150, "currency": "VND"}
    denied = client.get(f"/api/v1/reports/summary?{params}", headers={"Authorization": f"Bearer {employee}"})
    assert denied.status_code == 403

    response = client.get(f"/api/v1/reports/export?{params}", headers=headers)
    assert response.status_code == 200
    workbook = load_workbook(BytesIO(response.content), data_only=True)
    invoice_rows = list(workbook["Invoices"].iter_rows(min_row=2, values_only=True))
    item_rows = list(workbook["Line items"].iter_rows(min_row=2, values_only=True))
    assert len(invoice_rows) == 1
    assert invoice_rows[0][1] == "PAGE-001"
    assert invoice_rows[0][11] == 150
    assert len(item_rows) == 2
    assert item_rows[0][3] == "First service"
    assert item_rows[1][3].startswith("'=")
    assert item_rows[1][5] is None and item_rows[1][6] is None


def test_report_summary_empty_data_and_invalid_date_range(api_env):
    client, _, password = api_env
    accountant = _token(client, "accountant@phase2.test", password)
    admin = _token(client, "admin@phase2.test", password)
    headers = {"Authorization": f"Bearer {accountant}"}
    empty = client.get("/api/v1/reports/summary?search=NO-SUCH-INVOICE", headers=headers)
    assert empty.status_code == 200
    assert empty.json() == {"invoice_count": 0, "total_amount": 0, "currency": "VND"}
    reversed_range = client.get(
        "/api/v1/reports/export?invoice_date_from=2026-03-01&invoice_date_to=2026-02-01",
        headers=headers,
    )
    assert reversed_range.status_code == 422
    empty_export = client.get(
        "/api/v1/reports/export?search=NO-SUCH-INVOICE", headers=headers
    )
    assert empty_export.status_code == 200
    workbook = load_workbook(BytesIO(empty_export.content), data_only=True)
    assert workbook["Invoices"].max_row == 1
    assert workbook["Line items"].max_row == 1
    admin_export = client.get(
        "/api/v1/reports/export?search=NO-SUCH-INVOICE",
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert admin_export.status_code == 200


def test_schedule_permissions_notifications_and_ranking(api_env):
    client, users, password = api_env
    admin = _token(client, "admin@phase2.test", password)
    accountant = _token(client, "accountant@phase2.test", password)
    employee_one = _token(client, "employee1@phase2.test", password)
    employee_two = _token(client, "employee2@phase2.test", password)
    now = datetime.now(timezone.utc)
    body = {
        "title": "Synthetic test trip",
        "destination": "Test City",
        "starts_at": (now + timedelta(days=2)).isoformat(),
        "ends_at": (now + timedelta(days=3)).isoformat(),
        "assigned_to": users["employee1@phase2.test"],
    }

    denied = client.post(
        "/api/v1/schedules",
        json=body,
        headers={"Authorization": f"Bearer {employee_one}"},
    )
    created = client.post(
        "/api/v1/schedules",
        json=body,
        headers={"Authorization": f"Bearer {accountant}"},
    )
    assert denied.status_code == 403
    assert created.status_code == 201
    def normalized_utc(value):
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    assert normalized_utc(created.json()["starts_at"]) == normalized_utc(body["starts_at"])
    assert normalized_utc(created.json()["ends_at"]) == normalized_utc(body["ends_at"])
    assert created.json()["start_date"] == body["starts_at"][:10]
    assert created.json()["end_date"] == body["ends_at"][:10]
    invalid_schedule = client.post(
        "/api/v1/schedules",
        json={**body, "ends_at": body["starts_at"]},
        headers={"Authorization": f"Bearer {accountant}"},
    )
    assert invalid_schedule.status_code == 400
    schedule_id = created.json()["id"]
    employee_one_schedules = client.get(
        "/api/v1/schedules", headers={"Authorization": f"Bearer {employee_one}"}
    ).json()
    employee_two_schedules = client.get(
        "/api/v1/schedules", headers={"Authorization": f"Bearer {employee_two}"}
    ).json()
    assert any(item["id"] == schedule_id for item in employee_one_schedules)
    assert all(item["id"] != schedule_id for item in employee_two_schedules)

    completed = client.patch(
        f"/api/v1/schedules/{schedule_id}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    ranking = client.get(
        "/api/v1/ranking?period=all", headers={"Authorization": f"Bearer {employee_one}"}
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert any(item["user_id"] == users["employee1@phase2.test"] and item["completed"] == 1 for item in ranking.json())

    employee_notes = client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {employee_one}"}
    ).json()
    repeated_completion = client.patch(
        f"/api/v1/schedules/{schedule_id}",
        json={"status": "completed"},
        headers={"Authorization": f"Bearer {admin}"},
    )
    assert repeated_completion.status_code == 200
    employee_notes = client.get(
        "/api/v1/notifications", headers={"Authorization": f"Bearer {employee_one}"}
    ).json()
    note = next(item for item in employee_notes if item["schedule_id"] == schedule_id)
    assert sum(item["schedule_id"] == schedule_id for item in employee_notes) == 1
    assert note["title"] == "Lịch công tác mới"
    assert note["message"] == "Synthetic test trip – Test City"
    read = client.patch(
        f"/api/v1/notifications/{note['id']}/read",
        headers={"Authorization": f"Bearer {employee_one}"},
    )
    cross_owner_read = client.patch(
        f"/api/v1/notifications/{note['id']}/read",
        headers={"Authorization": f"Bearer {employee_two}"},
    )
    assert read.status_code == 200
    assert cross_owner_read.status_code == 404


def test_notifications_are_recipient_scoped_and_mark_all_is_idempotent(api_env):
    client, users, password = api_env
    recipient_ids = {}
    with client.app.state.phase2_test_session() as db:
        for email in (
            "admin@phase2.test",
            "accountant@phase2.test",
            "employee1@phase2.test",
            "employee2@phase2.test",
        ):
            user_id = users[email]
            recipient_ids[email] = []
            for index in range(2):
                notification = Notification(
                    user_id=user_id,
                    title="Test notification",
                    message=f"Recipient-only message {index}",
                    is_read=False,
                )
                db.add(notification)
                db.flush()
                recipient_ids[email].append(notification.id)
        db.commit()

    role_headers = {
        email: {"Authorization": f"Bearer {_token(client, email, password)}"}
        for email in recipient_ids
    }
    for email, headers in role_headers.items():
        response = client.get("/api/v1/notifications", headers=headers)
        assert response.status_code == 200
        ids = {item["id"] for item in response.json() if item["title"] == "Test notification"}
        assert ids == set(recipient_ids[email])
        assert all(item["type"] == "legacy" for item in response.json() if item["title"] == "Test notification")
        assert client.get("/api/v1/notifications", headers=headers).json() == response.json()

    accountant_headers = role_headers["accountant@phase2.test"]
    first = client.patch("/api/v1/notifications/read-all", headers=accountant_headers)
    second = client.patch("/api/v1/notifications/read-all", headers=accountant_headers)
    assert first.status_code == second.status_code == 200
    with client.app.state.phase2_test_session() as db:
        states = {
            email: [db.get(Notification, notification_id).is_read for notification_id in ids]
            for email, ids in recipient_ids.items()
        }
    assert states["accountant@phase2.test"] == [True, True]
    assert all(state == [False, False] for email, state in states.items() if email != "accountant@phase2.test")


def test_notification_unread_count_is_exact_and_recipient_scoped_beyond_list_limit(api_env):
    client, users, password = api_env
    with client.app.state.phase2_test_session() as db:
        for index in range(105):
            db.add(Notification(user_id=users["employee1@phase2.test"], title=f"Employee {index}", message="Unread"))
        db.add(Notification(user_id=users["accountant@phase2.test"], title="Accountant only", message="Unread"))
        db.commit()

    tokens = {
        email: _token(client, email, password)
        for email in ("employee1@phase2.test", "accountant@phase2.test", "admin@phase2.test")
    }
    headers = {email: {"Authorization": f"Bearer {token}"} for email, token in tokens.items()}
    listed = client.get("/api/v1/notifications", headers=headers["employee1@phase2.test"])
    assert listed.status_code == 200 and len(listed.json()) == 100
    assert client.get("/api/v1/notifications/unread-count", headers=headers["employee1@phase2.test"]).json() == {"count": 105}
    assert client.get("/api/v1/notifications/unread-count", headers=headers["accountant@phase2.test"]).json() == {"count": 1}
    assert client.get("/api/v1/notifications/unread-count", headers=headers["admin@phase2.test"]).json() == {"count": 0}
    assert client.get("/api/v1/notifications/unread-count").status_code == 401


def test_schedule_cannot_be_assigned_to_disabled_employee(api_env):
    client, users, password = api_env
    accountant = _token(client, "accountant@phase2.test", password)
    with client.app.state.phase2_test_session() as db:
        disabled = db.get(User, users["employee2@phase2.test"])
        disabled.status = "disabled"
        db.commit()
    now = datetime.now(timezone.utc)
    response = client.post(
        "/api/v1/schedules",
        headers={"Authorization": f"Bearer {accountant}"},
        json={
            "title": "Synthetic trip",
            "destination": "Test City",
            "starts_at": (now + timedelta(days=1)).isoformat(),
            "ends_at": (now + timedelta(days=2)).isoformat(),
            "assigned_to": users["employee2@phase2.test"],
        },
    )
    assert response.status_code == 400
    with client.app.state.phase2_test_session() as db:
        assert db.query(Notification).filter_by(user_id=users["employee2@phase2.test"], title="Lịch công tác mới").count() == 0
