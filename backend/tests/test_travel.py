"""Workflow fixtures are isolated and never inserted into the main database."""
import unittest
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select,func
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from app.core import Base,db_session,current_user
from app.main import app
from app.models import User,Schedule,Invoice,InvoiceFile,Notification
from app.travel import TravelCase,TravelExpense,TravelTransaction,TravelSLA,TravelHistory,now,sweep
from app.approval_sla import SLAPolicy

class TravelTests(unittest.TestCase):
    def setUp(self):
        self.engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        Base.metadata.create_all(self.engine);self.db=Session(self.engine,expire_on_commit=False)
        self.users={}
        for n,role in enumerate(('employee','accountant','admin','employee'),1):
            u=User(id=n,full_name='Isolated workflow test',email=f'travel{n}@example.invalid',role=role,password_hash='not-an-auth-fixture',status='active')
            self.db.add(u);self.users[n]=u
        self.db.commit();self.active=self.users[1]
        def session():yield self.db
        app.dependency_overrides[db_session]=session;app.dependency_overrides[current_user]=lambda:self.active
        self.client=TestClient(app)
        start=now()-timedelta(days=10);end=start+timedelta(days=1)
        self.active=self.users[3]
        result=self.client.post('/api/v1/schedules',json={'title':'Isolated business trip','destination':'Test location','assigned_to':1,'starts_at':start.isoformat(),'ends_at':end.isoformat()})
        self.assertEqual(result.status_code,201,result.text);self.schedule_id=result.json()['id'];self.active=self.users[1]
    def tearDown(self):app.dependency_overrides.clear();self.db.close();self.engine.dispose()
    def request(self,method,path,body=None,role=1,expected=200):
        self.active=self.users[role];r=self.client.request(method,'/api/v1'+path,json=body)
        self.assertEqual(r.status_code,expected,r.text)
        return r.json() if r.content else None
    def act(self,c,action,role=1,expected=200,**kw):return self.request('POST',f"/travel/cases/{c['id']}/actions",{'action':action,'version':c['version'],**kw},role,expected)
    def create(self):return self.request('POST','/travel/cases',{'schedule_id':self.schedule_id,'requested':'10000000','purpose':'Isolated test travel'},expected=201)
    def received(self):
        c=self.create();c=self.act(c,'submit_advance');c=self.act(c,'approve_advance',3,amount='10000000')
        body={'kind':'disbursement','amount':'10000000','paid_on':str(now().date()),'method':'Test fixture only','reference':uuid4().hex,'request_key':uuid4().hex}
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions",body,2)
        return self.request('POST',f"/travel/cases/{c['id']}/transactions/{c['transactions'][0]['id']}/receive",role=1)
    def expense(self,c,amount):
        return self.request('POST',f"/travel/cases/{c['id']}/expenses",{'description':'Isolated manual expense','category':'travel','occurred_on':str(now().date()),'quantity':'1','unit_price':amount,'amount':amount,'purpose':'Test expense','no_invoice_reason':'Unit-test fixture only'})
    def official(self,amount):
        c=self.expense(self.received(),amount);c=self.act(c,'submit_settlement')
        self.act(c,'forward_settlement',2,expected=409)
        e=c['expenses'][0]
        c=self.request('POST',f"/travel/cases/{c['id']}/expenses/{e['id']}/review",{'accepted':amount},2)
        c=self.act(c,'forward_settlement',2);return self.act(c,'approve_settlement',3)
    def test_three_financial_outcomes_and_closure(self):
        for amount,refund,supplement in [('7500000','2500000.00','0.00'),('10000000','0.00','0.00'),('12000000','0.00','2000000.00')]:
            if amount!='7500000':
                # Each independent workflow uses a new isolated database.
                self.tearDown();self.setUp()
            c=self.official(amount);self.assertEqual(c['totals']['refund_required'],refund);self.assertEqual(c['totals']['supplement_required'],supplement)
            if Decimal(refund)+Decimal(supplement):
                self.act(c,'close',2,expected=409)
                c=self.request('POST',f"/travel/cases/{c['id']}/transactions",{'kind':'refund' if Decimal(refund)>0 else 'supplement','amount':refund if Decimal(refund)>0 else supplement,'paid_on':str(now().date()),'method':'Test fixture only','reference':uuid4().hex,'request_key':uuid4().hex},2)
            c=self.act(c,'close',2);self.assertEqual(c['status'],'closed');self.assertEqual(c['totals']['remaining'],'0.00')
            self.request('POST',f"/travel/cases/{c['id']}/expenses",{'description':'Not allowed'},expected=409)
    def test_rbac_schedule_and_self_approval(self):
        c=self.create()
        self.request('GET',f"/travel/cases/{c['id']}",role=4,expected=404)
        self.assertEqual(self.request('GET','/travel/summary',role=4)['cases'],[])
        # Calendar retains main's roles; Travel ownership is independently enforced.
        self.request('GET',f"/travel/cases/{c['id']}",role=2)
        self.request('GET',f"/travel/cases/{c['id']}",role=3)
        self.act(c,'approve_advance',3,expected=409,amount='10000000')
        c=self.act(c,'submit_advance');self.act(c,'approve_advance',1,expected=403,amount='10000000')
        c=self.act(c,'approve_advance',3,amount='9000000',reason='Lower approved funding')
        self.request('PATCH',f'/schedules/{self.schedule_id}',{'title':'Blocked'},1,409)
        self.request('PATCH',f'/schedules/{self.schedule_id}',{'status':'completed'},1)
    def test_disbursement_cap_idempotency_and_receipt(self):
        c=self.create();c=self.act(c,'submit_advance');c=self.act(c,'approve_advance',3,amount='10000000')
        self.request('POST',f"/travel/cases/{c['id']}/transactions/999/receive",expected=404)
        body={'kind':'disbursement','amount':'10000001','paid_on':str(now().date()),'method':'Unit fixture','reference':'isolated-transfer','request_key':uuid4().hex}
        self.request('POST',f"/travel/cases/{c['id']}/transactions",body,2,409)
        body['amount']='10000000';c=self.request('POST',f"/travel/cases/{c['id']}/transactions",body,2)
        retry=self.request('POST',f"/travel/cases/{c['id']}/transactions",body,2);self.assertEqual(len(retry['transactions']),1)
        duplicate={**body,'request_key':uuid4().hex};self.request('POST',f"/travel/cases/{c['id']}/transactions",duplicate,2,409)
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions/{c['transactions'][0]['id']}/receive")
        self.assertEqual(c['totals']['received'],'10000000.00')
        self.request('POST',f"/travel/cases/{c['id']}/transactions/{c['transactions'][0]['id']}/receive",expected=409)
    def test_return_resubmit_sla_policy_freeze_and_notifications(self):
        c=self.expense(self.received(),'7500000');c=self.act(c,'submit_settlement');old=c['sla']['due_at']
        c=self.act(c,'return_settlement',2,reason='Need receipt');self.assertEqual(c['sla']['status'],'returned')
        self.db.add(SLAPolicy(days=5,holidays=['2026-12-01'],actor_id=3));self.db.commit()
        c=self.act(c,'submit_settlement');self.assertEqual(len(c['sla_history']),2);self.assertEqual(c['sla_history'][0]['due_at'],old);self.assertEqual(c['sla']['working_days'],5)
        cycle=self.db.get(TravelSLA,c['sla']['id']);cycle.due_at=now()-timedelta(days=1);self.db.commit()
        sweep(self.db);self.db.commit();count=self.db.scalar(select(func.count(Notification.id)))
        sweep(self.db);self.db.commit();self.assertEqual(self.db.scalar(select(func.count(Notification.id))),count)
        self.db.close();self.db=Session(self.engine,expire_on_commit=False)
        result=self.request('GET',f"/travel/cases/{c['id']}");self.assertEqual(result['sla']['status'],'overdue')
    def test_invoice_link_duplicate_and_budget_no_double_count(self):
        from app import finance
        from app.finance import Budget
        c=self.received()
        f=InvoiceFile(uploaded_by=1,original_filename='isolated.xml',file_type='xml',mime_type='application/xml',storage_key='not-created',file_size_bytes=0,checksum_sha256='f'*64)
        self.db.add(f);self.db.flush();i=Invoice(file_id=f.id,invoice_number='isolated-test',seller_name='Isolated test supplier',currency='VND',document_type='einvoice',total_amount=Decimal('5000000'),invoice_date=now().date(),approval_status='approved',validation_status='needs_review')
        self.db.add(i);self.db.commit()
        c=self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id,'category':'travel'})
        self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id},expected=409)
        c=self.expense(c,'2500000');c=self.act(c,'submit_settlement')
        for e in c['expenses']:c=self.request('POST',f"/travel/cases/{c['id']}/expenses/{e['id']}/review",{'accepted':e['amount']},2)
        c=self.act(c,'forward_settlement',2);c=self.act(c,'approve_settlement',3)
        b=Budget(starts_on=now().date(),ends_on=now().date(),amount=Decimal('10000000'),currency='VND',team='',category='',thresholds=[80,90,100],version=1)
        self.db.add(b);self.db.commit()
        usage=finance.budget_usage(self.db,b,self.users[3]);self.assertEqual(usage['approved'],'7500000.00')
        self.assertEqual(len(finance.expense_rows(self.db,self.users[3])),1)
        self.assertEqual(self.db.get(Invoice,i.id).total_amount,Decimal('5000000'))
        self.assertEqual(self.request('GET','/travel/summary',role=1)['accepted'],'7500000.00')
    def test_invalid_arithmetic_and_tier_skip(self):
        c=self.received()
        self.request('POST',f"/travel/cases/{c['id']}/expenses",{'description':'Invalid fixture','amount':'10','quantity':'3','unit_price':'4','purpose':'test','occurred_on':str(now().date()),'no_invoice_reason':'fixture'},expected=422)
        self.act(c,'approve_settlement',3,expected=409)
    def test_travel_chat_preserves_existing_tax_and_validation_routing(self):
        from app.chat_tools import route
        self.assertEqual(route('Toi da nhan bao nhieu tien tam ung?',{}),'travel')
        self.assertEqual(route('Tra cuu MST hoa don tam ung',{}),'tax')
        self.assertEqual(route('Kiem tra VAT chi phi cong tac',{}),'financial')
    def test_expense_retry_and_evidence_scope(self):
        c=self.received();key=uuid4().hex
        body={'request_key':key,'description':'Retry-safe test expense','amount':'0','quantity':'0','unit_price':'10','purpose':'Test only','occurred_on':str(now().date()),'no_invoice_reason':'Fixture only'}
        c=self.request('POST',f"/travel/cases/{c['id']}/expenses",body)
        retry=self.request('POST',f"/travel/cases/{c['id']}/expenses",body)
        self.assertEqual(len(retry['expenses']),1);self.assertEqual(retry['totals']['declared'],'0.00')
        self.request('POST',f"/travel/cases/{c['id']}/expenses",{**body,'amount':'1'},expected=409)
        self.active=self.users[1]
        uploaded=self.client.post(f"/api/v1/travel/cases/{c['id']}/evidence",files={'file':('fixture.pdf',b'%PDF-1.4\nIsolated test fixture','application/pdf')})
        self.assertEqual(uploaded.status_code,200)
        e=uploaded.json()['evidence'][0]
        self.request('GET','/travel/evidence/'+str(e['id']),role=4,expected=404)
        self.active=self.users[1];download=self.client.get('/api/v1/travel/evidence/'+str(e['id']))
        self.assertEqual(download.status_code,200);self.assertEqual(download.headers['cache-control'],'no-store')
    def proof(self,c,role=1,target='',expected=200):
        self.active=self.users[role]
        content=b'%PDF-1.4\nIsolated test fixture '+uuid4().hex.encode()
        response=self.client.post(f"/api/v1/travel/cases/{c['id']}/evidence?{target}",files={'file':('fixture.pdf',content,'application/pdf')})
        self.assertEqual(response.status_code,expected,response.text)
        if expected==200:self.assertEqual(response.json()['evidence'][-1]['file_size_bytes'],len(content))
        return response.json()
    def test_integer_vnd_api_accepts_plain_grouped_and_rejects_fractional(self):
        from app.travel import AdvanceInput,TransactionInput,Action,ReviewInput
        from pydantic import ValidationError
        for raw in ('10000000','10.000.000',10000000,'10000000.00'):
            self.assertEqual(AdvanceInput(schedule_id=self.schedule_id,requested=raw,purpose='Test').requested,Decimal('10000000'))
        for raw in ('0.01','0,01',Decimal('0.01'),True,{},'NaN','10.000.000,01'):
            with self.subTest(raw=raw),self.assertRaises(ValidationError):AdvanceInput(schedule_id=self.schedule_id,requested=raw,purpose='Test')
        self.request('POST','/travel/cases',{'schedule_id':self.schedule_id,'requested':'0.01','purpose':'Rejected fractional fixture'},expected=422)
        c=self.request('POST','/travel/cases',{'schedule_id':self.schedule_id,'requested':'10.000.000','purpose':'Whole VND fixture'},expected=201)
        self.assertEqual(c['totals']['requested'],'10000000.00')
        c=self.act(c,'submit_advance')
        self.act(c,'approve_advance',3,amount='0.01',expected=422)
        c=self.act(c,'approve_advance',3,amount='10.000.000')
        body={'kind':'disbursement','amount':'0.01','paid_on':str(now().date()),'method':'Fixture','reference':uuid4().hex,'request_key':uuid4().hex}
        self.request('POST',f"/travel/cases/{c['id']}/transactions",body,2,422)
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions",{**body,'amount':'10.000.000'},2)
        self.assertEqual(c['totals']['issued'],'10000000.00')
    def test_evidence_and_refund_declaration_phase_guards(self):
        c=self.create();self.proof(c,expected=403)
        c=self.act(c,'submit_advance');self.proof(c,expected=403)
        c=self.act(c,'approve_advance',3,amount='10000000');self.proof(c,expected=403)
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions",{'kind':'disbursement','amount':'10000000','paid_on':str(now().date()),'method':'Fixture','reference':uuid4().hex,'request_key':uuid4().hex},2)
        self.proof(c,expected=403)
        self.proof(c,role=2,target='transaction_id='+str(c['transactions'][0]['id']))
        self.proof(c,role=3,expected=403)
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions/{c['transactions'][0]['id']}/receive")
        self.proof(c)
        c=self.expense(c,'7500000');c=self.act(c,'submit_settlement');self.proof(c,expected=403)
        declaration={'kind':'return_declaration','amount':'1','paid_on':str(now().date()),'method':'Fixture','reference':uuid4().hex,'request_key':uuid4().hex}
        self.request('POST',f"/travel/cases/{c['id']}/transactions",declaration,expected=403)
        c=self.act(c,'return_settlement',2,reason='Need more evidence');c=self.proof(c)
        c=self.act(c,'submit_settlement')
        c=self.request('POST',f"/travel/cases/{c['id']}/expenses/{c['expenses'][0]['id']}/review",{'accepted':'7500000'},2)
        c=self.act(c,'forward_settlement',2);self.proof(c,expected=403)
        c=self.act(c,'approve_settlement',3)
        self.proof(c,expected=403)
        self.request('POST',f"/travel/cases/{c['id']}/transactions",{**declaration,'amount':'3000000'},expected=409)
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions",{**declaration,'amount':'2500000'})
        claim=next(t for t in c['transactions'] if t['kind']=='return_declaration')
        self.proof(c,target='transaction_id='+str(claim['id']))
        self.proof(c,target='expense_id='+str(c['expenses'][0]['id']),expected=403)
        self.request('POST',f"/travel/cases/{c['id']}/transactions",{**declaration,'reference':uuid4().hex,'request_key':uuid4().hex},expected=409)
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions",{**declaration,'kind':'refund','amount':'2500000','reference':uuid4().hex,'request_key':uuid4().hex},2)
        self.proof(c,target='transaction_id='+str(claim['id']),expected=403)
        c=self.act(c,'close',2)
        for role in (1,2,3):self.proof(c,role=role,expected=409)
    def test_history_names_roles_and_old_fractional_values_are_preserved(self):
        c=self.received()
        event=next(h for h in c['history'] if h['action']=='transaction_recorded')
        self.assertEqual(event['actor_name'],self.users[2].full_name)
        self.assertEqual(event['actor_role'],'accountant');self.assertEqual(event['actor_role_source'],'event')
        self.users[2].role='admin';self.db.commit()
        self.assertEqual(next(h for h in self.request('GET',f"/travel/cases/{c['id']}")['history'] if h['id']==event['id'])['actor_role'],'accountant')
        legacy=self.db.get(TravelCase,c['id']);legacy.requested=Decimal('0.01');legacy.approved=Decimal('0.01');self.db.commit()
        result=self.request('GET',f"/travel/cases/{c['id']}")
        self.assertEqual(result['totals']['requested'],'0.01');self.assertEqual(result['totals']['approved'],'0.01')
        self.assertEqual(self.db.get(TravelCase,c['id']).requested,Decimal('0.01'))
    def test_unsettled_counts_actual_issued_even_without_employee_receipt(self):
        c=self.create();c=self.act(c,'submit_advance');c=self.act(c,'approve_advance',3,amount='10000000')
        c=self.request('POST',f"/travel/cases/{c['id']}/transactions",{'kind':'disbursement','amount':'10000000','paid_on':str(now().date()),'method':'Fixture','reference':uuid4().hex,'request_key':uuid4().hex},2)
        self.assertEqual(c['totals']['received'],'0.00')
        summary=self.request('GET','/travel/summary')
        self.assertEqual(summary['unsettled_advance'],'10000000.00')
        self.assertEqual(summary['issued'],'10000000.00')
        self.assertEqual(summary['received'],'0.00')
        self.assertEqual(self.request('GET','/travel/summary',role=4)['issued'],'0.00')
    def test_invoice_link_distinguishes_missing_total_currency_and_pending_ocr(self):
        from app.models import ExtractionRun
        c=self.received()
        f=InvoiceFile(uploaded_by=1,original_filename='fixture.jpg',file_type='jpg',mime_type='image/jpeg',storage_key='not-created',file_size_bytes=1,checksum_sha256=uuid4().hex)
        self.db.add(f);self.db.flush()
        i=Invoice(file_id=f.id,document_type='einvoice',currency='VND',total_amount=None,invoice_date=now().date(),validation_status='needs_review')
        self.db.add(i);self.db.commit()
        r=self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id},expected=409)
        self.assertIn('tổng thanh toán',r['detail'])
        i.currency='';i.total_amount=Decimal('0');self.db.commit()
        r=self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id},expected=409)
        self.assertIn('đơn vị tiền tệ',r['detail'])
        i.currency='USD';self.db.commit()
        self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id},expected=409)
        i.currency='VND';run=ExtractionRun(invoice_id=i.id,method='fixture',status='processing');self.db.add(run);self.db.commit()
        r=self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id},expected=409)
        self.assertIn('chưa hoàn tất',r['detail'])
        run.status='completed';self.db.commit()
        c=self.request('POST',f"/travel/cases/{c['id']}/expenses",{'invoice_id':i.id})
        self.assertEqual(c['expenses'][0]['amount'],'0.00')

if __name__=='__main__':unittest.main()
