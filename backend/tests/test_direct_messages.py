import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app import main
from app.models import User, DirectMessage


def test_employee_without_invoices_can_receive_and_reply_privately(monkeypatch):
    engine = create_engine('sqlite://')
    User.__table__.create(engine)
    DirectMessage.__table__.create(engine)
    monkeypatch.setattr(main, 'notify', lambda *args, **kwargs: None)
    with Session(engine) as db:
        users = [User(full_name=str(i), email=f'{i}@test.local', password_hash='unused',
                      role=role, status='active')
                 for i, role in enumerate(['accountant', 'employee', 'employee', 'admin'])]
        db.add_all(users)
        db.commit()
        accountant, employee, other, admin = users
        assert employee.id in {p['id'] for p in main.direct_messages(db, accountant)['peers']}
        main.send_direct_message(main.InvoiceMessageInput(body='Hello', recipient_id=employee.id), db, accountant)
        main.send_direct_message(main.InvoiceMessageInput(body='Reply', recipient_id=accountant.id), db, employee)
        assert len(main.direct_messages(db, employee)['messages']) == 2
        assert main.direct_messages(db, other)['messages'] == []
        with pytest.raises(HTTPException):
            main.send_direct_message(main.InvoiceMessageInput(body='No', recipient_id=other.id), db, employee)
        assert main.direct_messages(db, admin)['messages'] == []
        for peer in (employee, accountant):
            assert peer.id in {p['id'] for p in main.direct_messages(db, admin)['peers']}
            assert admin.id in {p['id'] for p in main.direct_messages(db, peer)['peers']}
            main.send_direct_message(main.InvoiceMessageInput(body='From admin', recipient_id=peer.id), db, admin)
            main.send_direct_message(main.InvoiceMessageInput(body='Reply', recipient_id=admin.id), db, peer)
        assert len(main.direct_messages(db, admin)['messages']) == 4
        assert len(main.direct_messages(db, accountant)['messages']) == 4
        assert main.direct_messages(db, other)['messages'] == []
        with pytest.raises(HTTPException):
            main.send_direct_message(main.InvoiceMessageInput(body='Self', recipient_id=admin.id), db, admin)
        employee.status = 'inactive'
        db.commit()
        with pytest.raises(HTTPException):
            main.send_direct_message(main.InvoiceMessageInput(body='No', recipient_id=employee.id), db, accountant)
