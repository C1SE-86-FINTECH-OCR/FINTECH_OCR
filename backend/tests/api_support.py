"""Shared isolated API fixtures retained independently of retired legacy suites."""
import os,secrets
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session,sessionmaker
from sqlalchemy.pool import StaticPool
import app.core as core
import app.main as api_main
from app.models import Invoice,InvoiceFile,User

@pytest.fixture
def api_env(tmp_path, monkeypatch):
    pg_url = os.environ.get('FINTECH_OCR_ISOLATED_PG_URL')
    if pg_url:
        url = make_url(pg_url)
        if (url.get_backend_name() != 'postgresql' or url.host not in ('127.0.0.1', 'localhost')
                or url.database != 'fintech_travel_upgrade_test'):
            raise RuntimeError('Use a disposable local PostgreSQL database named fintech_travel_upgrade_test')
        schema = 'test_' + secrets.token_hex(8)
        test_engine = create_engine(url, connect_args={'options': f'-c search_path={schema} -c timezone=UTC'})
        with test_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
    else:
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
