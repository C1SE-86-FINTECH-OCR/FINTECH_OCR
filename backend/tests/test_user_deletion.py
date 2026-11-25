import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from app.main import delete_user
from app.models import Base, User, DirectMessage, Notification, AuditLog, InvoiceFile


@pytest.fixture
def accounts():
    engine=create_engine('sqlite://')
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin=User(full_name='Admin',email='admin@test.local',password_hash='unused',role='admin')
        db.add(admin)
        db.flush()
        target=User(full_name='Employee',email='employee@test.local',password_hash='unused',role='employee',created_by=admin.id)
        db.add(target)
        db.commit()
        yield db, admin, target


def test_delete_without_uploads_cleans_personal_data_and_preserves_audit(accounts):
    db,admin,target=accounts
    target_id=target.id
    db.add_all([DirectMessage(sender_id=admin.id,recipient_id=target.id,body='Hello'),
                Notification(user_id=target.id,title='Hello',message='Hello'),
                AuditLog(actor_id=target.id,action='login',entity_type='user',entity_id=target.id)])
    db.commit()
    assert delete_user(target_id,db,admin).status_code==204
    assert db.get(User,target_id) is None
    assert db.scalar(select(DirectMessage)) is None
    assert db.scalar(select(Notification)) is None
    history=db.scalar(select(AuditLog).where(AuditLog.action=='login'))
    assert history.actor_id is None
    assert db.scalar(select(AuditLog).where(AuditLog.action=='user.deleted')).actor_id==admin.id
    assert db.get(User,admin.id) is not None


def test_uploaded_file_blocks_deletion_even_without_extracted_invoice(accounts):
    db,admin,target=accounts
    db.add(InvoiceFile(uploaded_by=target.id,original_filename='invoice.pdf',file_type='pdf',
                       mime_type='application/pdf',file_size_bytes=1,storage_key='test',checksum_sha256='test'))
    db.commit()
    with pytest.raises(HTTPException) as error:
        delete_user(target.id,db,admin)
    assert error.value.status_code==409
    assert 'quan trọng' in error.value.detail
    assert 'không thể xóa' in error.value.detail
    assert db.get(User,target.id) is not None


def test_cannot_delete_current_admin(accounts):
    db,admin,_=accounts
    with pytest.raises(HTTPException):
        delete_user(admin.id,db,admin)
