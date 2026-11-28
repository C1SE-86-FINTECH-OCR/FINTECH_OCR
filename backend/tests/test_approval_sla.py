"""Isolated fixtures only: no external services and no main-database writes."""
import unittest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core import Base, db_session, current_user
from app.models import User, InvoiceFile, Invoice, InvoiceApproval, Notification
from app.approval_sla import (TZ, SLACycle, SLANotice, SLAPolicy, deadline, working_seconds,
    serialize, start_cycle, finish_cycle, synchronize, router)

def at(value): return datetime.fromisoformat(value).replace(tzinfo=TZ)

class CalendarTests(unittest.TestCase):
    def test_weekday_weekend_holiday_timezone(self):
        self.assertEqual(deadline(at('2026-11-26T15:30'),3,[]).astimezone(TZ),at('2026-12-01T15:30'))
        self.assertEqual(deadline(at('2026-11-27T15:30'),3,['2026-11-30']).astimezone(TZ),at('2026-12-03T15:30'))
        self.assertEqual(deadline(at('2026-11-28T15:30'),3,[]).astimezone(TZ),at('2026-12-02T15:30'))
        self.assertEqual(working_seconds(at('2026-11-27T15:30'),at('2026-11-30T15:30'),[]),86400)

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db=Session(self.engine)
        self.users=[]
        for index,role in enumerate(('employee','accountant','admin','employee'),1):
            user=User(id=index,full_name='Isolated SLA test',email=f'{index}@example.invalid',role=role,password_hash='not-a-login-fixture',status='active')
            self.db.add(user);self.users.append(user)
        self.db.flush()
        f=InvoiceFile(uploaded_by=1,original_filename='isolated.xml',file_type='xml',mime_type='application/xml',file_size_bytes=0,storage_key='not-created',checksum_sha256='0'*64)
        self.db.add(f);self.db.flush()
        self.inv=Invoice(file_id=f.id,approval_status='pending')
        self.db.add(self.inv);self.db.flush()
        event=InvoiceApproval(invoice_id=self.inv.id,action_by=1,action='submitted',created_at=at('2026-11-23T10:00'))
        self.db.add(event);self.db.flush();self.cycle=start_cycle(self.db,event)
        self.db.commit()
    def tearDown(self): self.db.close();self.engine.dispose()
    def test_status_zero_remaining_and_stopped_counter(self):
        self.assertEqual(serialize(self.cycle,at('2026-11-23T10:00'))['status'],'in_time')
        self.assertEqual(serialize(self.cycle,at('2026-11-25T10:00'))['status'],'due_soon')
        self.assertEqual(serialize(self.cycle,at('2026-11-26T10:01'))['status'],'overdue')
        finish_cycle(self.db,self.inv.id,'approved',at('2026-11-25T10:00'))
        self.assertEqual(serialize(self.cycle,at('2027-01-01T10:00')),serialize(self.cycle,at('2028-01-01T10:00')))
        self.assertTrue(serialize(self.cycle)['on_time'])
    def test_resubmit_and_policy_snapshot(self):
        finish_cycle(self.db,self.inv.id,'rejected',at('2026-11-24T10:00'))
        old_due=self.cycle.due_at
        self.db.add(SLAPolicy(days=5,holidays=['2026-12-01'],actor_id=3));self.db.flush()
        event=InvoiceApproval(invoice_id=self.inv.id,action_by=1,action='submitted',created_at=at('2026-11-27T10:00'))
        self.db.add(event);self.db.flush();new=start_cycle(self.db,event)
        self.assertEqual(new.days,5);self.assertEqual(self.cycle.days,3);self.assertEqual(self.cycle.due_at,old_due)
        self.assertNotEqual(new.id,self.cycle.id)
        self.assertEqual(start_cycle(self.db,event).id,new.id)
    def test_notification_idempotency_and_restart(self):
        synchronize(self.db,at('2026-11-26T10:01'));self.db.commit()
        first=self.db.scalars(select(SLANotice)).all()
        self.assertEqual(len(first),2) # overdue: accountant and admin
        self.assertEqual(len(self.db.scalars(select(Notification)).all()),2)
        self.db.close();self.db=Session(self.engine)
        synchronize(self.db,at('2026-11-26T11:01'));self.db.commit()
        self.assertEqual(len(self.db.scalars(select(SLANotice)).all()),2)
    def test_due_soon_only_accountant_and_no_inferred_legacy_deadline(self):
        synchronize(self.db,at('2026-11-25T10:00'));self.db.flush()
        self.assertEqual([n.user_id for n in self.db.scalars(select(SLANotice)).all()],[2])
        self.assertEqual(serialize(self.cycle,invoice_status='draft')['status'],'unknown')
        self.assertIsNone(serialize(self.cycle,invoice_status='approved')['remaining_working_seconds'])
        self.db.query(InvoiceApproval).delete();self.db.query(SLANotice).delete();self.db.query(SLACycle).delete()
        synchronize(self.db,at('2026-11-26T11:00'))
        self.assertEqual(self.db.scalars(select(SLACycle)).all(),[])
    def test_rbac_policy_history_and_scope(self):
        app=FastAPI();app.include_router(router)
        def session(): yield self.db
        app.dependency_overrides[db_session]=session
        client=TestClient(app)
        for user in self.users:
            app.dependency_overrides[current_user]=lambda:user
            self.assertEqual(client.get('/api/v1/approval-sla/policy').status_code,200 if user.role=='admin' else 403)
            result=client.get('/api/v1/approval-sla/summary').json()
            self.assertEqual(result['pending'],0 if user.id==4 else 1)
        app.dependency_overrides[current_user]=lambda:self.users[2]
        old_due=self.cycle.due_at
        self.assertEqual(client.put('/api/v1/approval-sla/policy',json={'days':4,'holidays':['2026-12-01'],'version':None}).status_code,200)
        self.assertEqual(client.put('/api/v1/approval-sla/policy',json={'days':5,'version':None}).status_code,409)
        self.assertEqual(self.cycle.due_at,old_due)
        self.assertEqual(len(client.get('/api/v1/approval-sla/policy').json()['history']),1)
        self.assertEqual(client.put('/api/v1/approval-sla/policy',json={'days':0}).status_code,422)
        self.assertEqual(client.put('/api/v1/approval-sla/policy',json={'days':3,'holidays':['not-a-date']}).status_code,422)

if __name__=='__main__':unittest.main()
