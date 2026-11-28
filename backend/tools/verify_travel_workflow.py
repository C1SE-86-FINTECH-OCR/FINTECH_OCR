"""Exercise the real API against an isolated restored database; rollback all fixtures."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

def verify(target):
    if target.url.database=='fintech_ocr':raise RuntimeError('Never run workflow fixtures against main')
    from app import main
    from app.core import db_session,current_user
    from app.models import User
    from app.travel import TravelTransaction
    with target.connect() as connection:
        transaction=connection.begin()
        db=Session(bind=connection,join_transaction_mode='create_savepoint',expire_on_commit=False)
        users={role:db.scalar(select(User).where(User.role==role,User.status=='active').order_by(User.id)) for role in ('employee','accountant','admin')}
        if any(u is None for u in users.values()):raise RuntimeError('Need existing active users in the restored database')
        actor=[users['employee']]
        def session():yield db
        main.app.dependency_overrides[db_session]=session;main.app.dependency_overrides[current_user]=lambda:actor[0]
        @contextmanager
        def local_session():yield db
        original_session=main.SessionLocal;main.SessionLocal=local_session
        try:
            client=TestClient(main.app)
            def request(method,path,role='employee',body=None,expected=200):
                actor[0]=users[role]
                response=client.request(method,'/api/v1'+path,json=body)
                if response.status_code!=expected:raise RuntimeError(f'Isolated API {method} {path} failed: HTTP {response.status_code}')
                return response
            starts=datetime(1999,1,4,2,tzinfo=timezone.utc)
            schedule=request('POST','/schedules','admin',body={'title':'Isolated rollback verification '+uuid4().hex,'destination':'Isolated test only','assigned_to':users['employee'].id,'starts_at':starts.isoformat(),'ends_at':(starts+timedelta(days=1)).isoformat()},expected=201).json()
            c=request('POST','/travel/cases',body={'schedule_id':schedule['id'],'requested':'10000000','purpose':'Isolated workflow verification only'},expected=201).json()
            def action(c,name,role='employee',**kw):return request('POST',f"/travel/cases/{c['id']}/actions",role,{'action':name,'version':c['version'],**kw}).json()
            c=action(c,'submit_advance');c=action(c,'approve_advance','admin',amount='8000000',reason='Test lower approved amount')
            paid={'kind':'disbursement','amount':'8000000','paid_on':'1999-01-03','method':'Isolated fixture','reference':uuid4().hex,'request_key':uuid4().hex}
            c=request('POST',f"/travel/cases/{c['id']}/transactions",'accountant',paid).json()
            duplicate=request('POST',f"/travel/cases/{c['id']}/transactions",'accountant',paid).json()
            if len(duplicate['transactions'])!=1:raise RuntimeError('Disbursement counted twice')
            c=request('POST',f"/travel/cases/{c['id']}/transactions/{c['transactions'][0]['id']}/receive").json()
            c=request('POST',f"/travel/cases/{c['id']}/expenses",body={'description':'Isolated manual expense','category':'travel','occurred_on':'1999-01-05','amount':'7500000','purpose':'Test only','no_invoice_reason':'Fixture without real financial evidence'}).json()
            c=action(c,'submit_settlement')
            c=request('POST',f"/travel/cases/{c['id']}/expenses/{c['expenses'][0]['id']}/review",'accountant',{'accepted':'7000000','reason':'Test rejected part'}).json()
            c=action(c,'forward_settlement','accountant');c=action(c,'approve_settlement','admin')
            if c['totals']['refund_required']!='1000000.00':raise RuntimeError('Incorrect settlement difference')
            c=request('POST',f"/travel/cases/{c['id']}/transactions",'accountant',{'kind':'refund','amount':'1000000','paid_on':'1999-01-06','method':'Isolated fixture','reference':uuid4().hex,'request_key':uuid4().hex}).json()
            c=action(c,'close','accountant')
            if c['totals']['remaining']!='0.00' or c['status']!='closed':raise RuntimeError('Incorrect closure')
            export=request('GET','/travel/export')
            if not export.content.startswith(b'PK'):raise RuntimeError('Excel artifact missing')
            chat=request('POST','/chatbot/stream',body={'question':f"Quyet toan ho so #{c['id']}: toi can hoan ung bao nhieu?"})
            if 'event: done' not in chat.text or '"kind": "travel"' not in chat.text:raise RuntimeError('Travel chat streaming tool did not execute')
            if '1000000' not in chat.text and '1.000.000' not in chat.text:raise RuntimeError('Chat missing actual ledger amounts')
            result={'workflow_api':True,'postgres_decimal':True,'disbursement_idempotency':True,'excel':True,'chat_streaming':True,'changes_rolled_back':True}
        finally:
            main.SessionLocal=original_session;main.app.dependency_overrides.clear();db.close();transaction.rollback()
    return result
