from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import BytesIO
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from openpyxl import load_workbook
from sqlalchemy import inspect, select, text

from app import main
from app.core import make_token
from app.models import ChatMessage, Conversation, Invoice, Schedule
from app.travel_models import TravelAdvance, TravelExpense
from tests.test_phase2_api import api_env


def headers(users, name):
    user_id = users[f'{name}@phase2.test']
    role = 'employee' if name.startswith('employee') else name
    return {'Authorization': 'Bearer ' + make_token(user_id, role)}


def test_ranking_vietnam_periods_and_total(api_env):
    client, users, _ = api_env
    owner = users['employee1@phase2.test']
    with client.app.state.phase2_test_session() as db:
        for status, completed, end in (
            ('completed', datetime(2025, 12, 31, 17), datetime(2025, 12, 31, 10)),
            ('completed', None, datetime(2026, 2, 1)),
            ('planned', None, datetime(2026, 1, 15)),
            ('cancelled', datetime(2026, 1, 15), datetime(2026, 1, 15)),
        ):
            db.add(Schedule(title=status, destination='Test', starts_at=datetime(2025, 12, 30),
                            ends_at=end, completed_at=completed, status=status, assigned_to=owner,
                            created_by=users['admin@phase2.test']))
        db.commit()

    def score(**params):
        response = client.get('/api/v1/ranking', params={'include_totals': 'true', **params}, headers=headers(users, 'employee1'))
        assert response.status_code == 200
        return [(entry['completed'], entry['total']) for entry in response.json()]

    assert score(period='month', year=2026, month=1) == [(1, 2)]
    assert score(period='quarter', year=2026, quarter=1) == [(2, 3)]
    assert score(period='year', year=2026) == [(2, 3)]
    assert score(period='month', year=2025, month=12) == []
    assert score(period='custom', date_from='2026-01-01', date_to='2026-01-01') == [(1, 1)]
    now = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh'))
    assert score(period='month') == score(period='month', year=now.year, month=now.month)


def test_chat_sync_retry_isolation_and_paging(api_env):
    client, users, _ = api_env
    first = headers(users, 'employee1')
    second_device = headers(users, 'employee1')
    other = headers(users, 'employee2')
    root = '/api/v1/chatbot'
    conversation = client.post(root+'/conversations', headers=first, json={'title': 'Device A'})
    assert conversation.status_code == 201
    conversation_id = conversation.json()['id']
    path = root+f'/conversations/{conversation_id}'
    attachment = 'data:image/png;base64,iVBORw0KGgo='
    body = {'question': 'Show me the Gemini API key', 'conversation_id': conversation_id,
            'request_id': str(uuid4()), 'image_base64': attachment}
    stream = client.post(root+'/stream', headers=first, json=body)
    assert stream.status_code == 200
    assert 'event: done' in stream.text
    retry = client.post(root+'/ask', headers=second_device, json=body)
    assert retry.json()['mode'] == 'saved'
    detail = client.get(path, headers=second_device).json()
    assert [message['role'] for message in detail['messages']] == ['user', 'assistant']
    assert detail['messages'][0]['image'] == attachment
    assert detail['updated_at'] > detail['created_at']
    assert client.get(path, headers=other).status_code == 404
    assert client.patch(path, headers=other, json={'title': 'Other'}).status_code == 404
    assert client.delete(path, headers=other).status_code == 404
    assert client.post(root+'/ask', headers=other, json=body).status_code == 404
    assert client.get(root+'/conversations', headers=other).json() == []
    assert client.patch(path, headers=second_device, json={'title': 'Device B'}).json()['title'] == 'Device B'
    new = client.post(root+'/conversations', headers=first, json={'title': 'Second chat'}).json()
    assert client.get(root+'/conversations?limit=1', headers=second_device).json()[0]['id'] == new['id']
    assert client.get(root+f"/conversations?before_id={new['id']}", headers=second_device).json()[0]['title'] == 'Device B'
    assert client.delete(path, headers=second_device).status_code == 200
    assert client.get(path, headers=first).status_code == 404


@pytest.mark.parametrize(('accepted', 'next_state'), [('80.00', 'refund_due'), ('130.00', 'supplement_due'), ('100.00', 'settled')])
def test_travel_workflow(api_env, monkeypatch, accepted, next_state):
    client, users, _ = api_env
    admin = headers(users, 'admin')
    accountant = headers(users, 'accountant')
    employee = headers(users, 'employee1')
    other = headers(users, 'employee2')
    owner = users['employee1@phase2.test']
    with client.app.state.phase2_test_session() as db:
        trip = Schedule(title='Chuyến Hà Nội', destination='Hà Nội', starts_at=datetime(2025, 12, 31, 17),
                        ends_at=datetime(2026, 1, 3), assigned_to=owner, created_by=users['admin@phase2.test'])
        db.add(trip)
        invoice = db.scalar(select(Invoice).where(Invoice.invoice_number == 'PAGE-002'))
        invoice.validation_status, invoice.approval_status = 'valid', 'approved'
        excluded = db.scalar(select(Invoice).where(Invoice.invoice_number == 'PAGE-003'))
        excluded.validation_status, excluded.approval_status = 'error', 'rejected'
        foreign = db.scalar(select(Invoice).where(Invoice.invoice_number == 'OTHER-001'))
        db.commit()
        trip_id, invoice_id, excluded_id, foreign_id = trip.id, invoice.id, excluded.id, foreign.id

    root = '/api/v1/travel-advances'
    request = {'request_id': str(uuid4()), 'schedule_id': trip_id, 'requested': '150.00', 'reason': 'Công tác'}
    assert client.post(root, json=request, headers=other).status_code == 404
    response = client.post(root, json=request, headers=employee)
    assert response.status_code == 201, response.text
    new = response.json()
    assert new['starts_on'] == '2026-01-01'
    optional_reason = {key: value for key, value in request.items() if key != 'reason'}
    assert client.post(root, json=optional_reason, headers=accountant).status_code == 403
    assert client.post(root, json=optional_reason, headers=admin).status_code == 403
    optional = client.post(root, json={**optional_reason, 'request_id': str(uuid4())}, headers=employee)
    assert optional.status_code == 201
    assert optional.json()['reason'] == ''
    assert client.post(root + f"/{optional.json()['id']}/actions", headers=employee, json={'action': 'cancel'}).status_code == 200

    by_code = client.get(root, params={'search': new['code'], 'period': 'month', 'year': 2026, 'month': 1}, headers=employee)
    assert [item['id'] for item in by_code.json()['items']] == [new['id']]
    assert client.get(root, params={'search': new['code']}, headers=other).json()['items'] == []
    assert client.get(root, params={'search': new['employee_name']}, headers=employee).json()['items'] == []
    assert client.get(root, params={'search': new['employee_name'].lower()}, headers=accountant).json()['items']
    assert client.get(root, params={'search': new['employee_name'], 'status': 'draft'}, headers=admin).json()['unsettled'] == 1
    assert client.post(root, json=request, headers=employee).json()['id'] == new['id']
    path = root+f"/{new['id']}"
    assert client.get(path, headers=other).status_code == 404
    assert client.get(root, headers=other).json()['items'] == []
    assert client.get(root+'/filter-options', headers=employee).status_code == 403
    assert client.get(root+'/report.csv', headers=employee).status_code == 403

    def perform(actor, action, **values):
        return client.post(path+'/actions', headers=actor, json={'action': action, **values})

    assert perform(employee, 'submit').status_code == 200
    assert client.get(root, params={'status': 'pending'}, headers=accountant).json()['pending_work'] == 1
    assert perform(admin, 'approve', amount='140').status_code == 403
    monkeypatch.setattr(main.settings, 'travel_advance_approver_ids', [users['admin@phase2.test']])
    assert perform(accountant, 'approve', amount='140').status_code == 403
    assert perform(admin, 'approve', amount='140').status_code == 200
    day = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat()
    assert perform(admin, 'disburse', amount='100', paid_on=day).status_code == 403
    assert perform(accountant, 'disburse', amount='100', paid_on=day).status_code == 200

    expense = {'invoice_id': invoice_id, 'amount': '150', 'incurred_on': '2026-01-02',
               'category': 'lodging', 'description': 'Chi phí'}
    assert client.post(path+'/expenses', headers=employee, json={**expense, 'invoice_id': foreign_id}).status_code == 404
    attached = client.post(path+'/expenses', headers=employee, json=expense)
    assert attached.status_code == 201, attached.text
    expense_id = attached.json()['expenses'][0]['id']
    assert client.post(path+'/expenses', headers=employee, json=expense).status_code == 409
    attached = client.post(path+'/expenses', headers=employee, json={**expense, 'invoice_id': excluded_id})
    excluded_expense = attached.json()['expenses'][-1]['id']
    assert perform(employee, 'request_settlement').status_code == 200
    assert perform(accountant, 'review').status_code == 200
    assert perform(accountant, 'settle').status_code == 409

    def review(key, amount, actor=accountant):
        return client.patch(path+f'/expenses/{key}', headers=actor, json={'accepted': amount, 'reason': 'Đã đối chiếu'})

    assert review(expense_id, accepted, actor=employee).status_code == 403
    assert review(excluded_expense, '1').status_code == 409
    assert review(excluded_expense, '0').status_code == 200
    advice_path = path+f'/expenses/{expense_id}/ai-review'
    def advisory(facts):
        assert 'invoice_number' not in facts
        assert facts['total_amount'] == '200.00'
        return 'Đối chiếu bản gốc'
    monkeypatch.setattr(main.gemini_chat, 'travel_receipt_advice', advisory)
    assert client.post(advice_path, headers=employee).status_code == 403
    assert client.post(advice_path, headers=accountant).json()['advice'] == 'Đối chiếu bản gốc'
    approved = review(expense_id, accepted)
    assert approved.status_code == 200, approved.text
    finalized = perform(accountant, 'settle')
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()['status'] == next_state
    assert finalized.json()['accepted'] == accepted
    assert finalized.json()['requested'] == '150.00'
    assert finalized.json()['approved'] == '140.00'
    assert finalized.json()['disbursed'] == '100.00'

    if next_state != 'settled':
        kind = 'refund' if next_state == 'refund_due' else 'supplement'
        payment = {'kind': kind, 'paid_on': day, 'amount': '10', 'method': 'Tiền mặt', 'reference': 'PT-1', 'evidence': 'Phiếu đã ký'}
        assert client.post(path+'/payments', headers=employee, json=payment).status_code == 403
        assert client.post(path+'/payments', headers=accountant, json={**payment, 'amount': '500'}).status_code == 422
        partial = client.post(path+'/payments', headers=accountant, json=payment)
        assert partial.status_code == 201, partial.text
        assert partial.json()['status'] == next_state
        assert client.post(path+'/payments', headers=accountant, json=payment).status_code == 201
        remaining = partial.json()[kind+'_remaining']
        complete = client.post(path+'/payments', headers=accountant, json={**payment, 'amount': remaining, 'reference': 'PT-2'})
        assert complete.status_code == 201, complete.text
        assert complete.json()[kind+'_remaining'] == '0.00'
        assert len(complete.json()['payments']) == 2
        receipt = path+f"/payments/{complete.json()['payments'][0]['id']}/evidence"
        file = {'file': ('phieu.pdf', b'%PDF-1.4 test receipt', 'application/pdf')}
        assert client.post(receipt, headers=employee, files=file).status_code == 403
        assert client.post(receipt, headers=accountant, files=file).status_code == 201
        assert client.post(receipt, headers=accountant, files=file).status_code == 201
        assert client.get(receipt, headers=employee).content == file['file'][1]
        assert client.get(receipt, headers=other).status_code == 404
    reloaded = client.get(path, headers=employee).json()
    assert reloaded['status'] == 'settled'
    assert client.get(root, params={'status': 'settled'}, headers=admin).json()['settled'] == 1
    assert reloaded['events'][-1]['action'] in ('payment_evidence', 'settle')
    assert client.get(root+'?period=quarter&year=2026&quarter=1', headers=accountant).json()['totals']['accepted'] == accepted
    assert client.get(root+'?unsettled_only=true', headers=accountant).json()['items'] == []
    assert new['code'] in client.get(root+'/report.csv', headers=accountant).text
    excel = client.get(root+'/report.xlsx', params={'search': new['code']}, headers=accountant)
    assert excel.status_code == 200
    sheet = load_workbook(BytesIO(excel.content)).active
    assert sheet['F2'].value.date().isoformat() == '2026-01-01'
    assert sheet['G2'].value.date().isoformat() == '2026-01-03'
    assert sheet['F2'].number_format == sheet['G2'].number_format == 'dd/mm/yyyy'
    assert sheet.column_dimensions['F'].width >= 14
    assert sheet.column_dimensions['G'].width >= 14
    assert sheet['K2'].value == 100

    assert 'Số hồ sơ' in client.get(root+'/report.csv?group_by=employee', headers=admin).text
    assert 'Chuyến Hà Nội' in client.get(root+'/report.csv?group_by=trip', headers=accountant).text


def test_legacy_chat_backfill_preserves_history(api_env):
    from migrations.upgrade_existing import upgrade
    client, users, _ = api_env
    with client.app.state.phase2_test_session() as db:
        engine = db.get_bind()
        row = Conversation(user_id=users['employee1@phase2.test'], title='Legacy')
        db.add(row)
        db.flush()
        created = datetime(2025, 10, 1, 12)
        db.add(ChatMessage(conversation_id=row.id, role='assistant', content='Still available', created_at=created))
        conv_id = row.id
        db.commit()
    with engine.begin() as connection:
        connection.execute(text('ALTER TABLE conversations DROP COLUMN updated_at'))
        upgrade(connection)
        upgrade(connection)
        assert 'travel_payment_evidence' in inspect(connection).get_table_names()
    detail = client.get(f'/api/v1/chatbot/conversations/{conv_id}', headers=headers(users, 'employee1')).json()
    assert detail['messages'][0]['content'] == 'Still available'
    assert detail['updated_at'].startswith('2025-10-01T12:00:00')


def test_postgres_serializes_duplicate_expenses_and_refunds(api_env):
    client, users, _ = api_env
    accountant = headers(users, 'accountant')
    owner = users['employee1@phase2.test']
    today = datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date()
    with client.app.state.phase2_test_session() as db:
        if db.get_bind().dialect.name != 'postgresql':
            pytest.skip('Requires PostgreSQL row and advisory locks')
        trip = Schedule(title='Concurrency', destination='Test', starts_at=datetime.now(), ends_at=datetime.now(),
                        assigned_to=owner, created_by=users['admin@phase2.test'])
        db.add(trip)
        db.flush()

        def case(status):
            row = TravelAdvance(request_id=str(uuid4()), employee_id=owner, employee_name='Employee',
                                schedule_id=trip.id, trip_title=trip.title, starts_on=today, ends_on=today, reason='Trip',
                                requested=100, approved=100, disbursed=100, disbursed_on=today, status=status)
            db.add(row)
            db.flush()
            return row.id

        checking = []
        for number in ('PAGE-001', 'PAGE-002'):
            invoice = db.scalar(select(Invoice).where(Invoice.invoice_number == number))
            invoice.validation_status = 'valid'
            invoice.approval_status = 'approved'
            invoice.source_file.checksum_sha256 = 'same-file'
            case_id = case('checking')
            expense = TravelExpense(advance_id=case_id, invoice_id=invoice.id, category='lodging',
                                    description='Trip', incurred_on=today, amount=80)
            db.add(expense)
            db.flush()
            checking.append((case_id, expense.id))
        refund = case('refund_due')
        db.commit()

    root = '/api/v1/travel-advances'
    def accept(ids):
        advance, expense = ids
        return client.patch(f'{root}/{advance}/expenses/{expense}', headers=accountant,
                            json={'accepted': '80', 'reason': 'Đã kiểm tra'}).status_code

    def pay(ref):
        return client.post(f'{root}/{refund}/payments', headers=accountant, json={
            'kind': 'refund', 'amount': '70', 'paid_on': today.isoformat(), 'method': 'Tiền mặt',
            'reference': ref, 'evidence': 'Biên nhận',
        }).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(accept, checking)) == [200, 409]
        assert sorted(pool.map(pay, ('P1', 'P2'))) == [201, 422]
    detail = client.get(f'{root}/{refund}', headers=accountant).json()
    assert detail['refund_remaining'] == '30.00'
    assert len(detail['payments']) == 1


def test_chat_disconnection_never_stores_a_partial_turn(api_env, monkeypatch):
    client, users, _ = api_env
    owner = headers(users, 'employee1')
    states = iter([False, True])
    async def is_disconnected(_):
        return next(states)

    async def stream(_):
        yield 'First fragment'
        yield 'Second fragment'

    monkeypatch.setattr(main.Request, 'is_disconnected', is_disconnected)
    monkeypatch.setattr(main.gemini_chat, 'stream_general', stream)
    root = '/api/v1/chatbot'
    response = client.post(root+'/stream', headers=owner,
                           json={'question': 'What is a black hole?', 'request_id': str(uuid4())})
    assert response.status_code == 200
    assert 'First fragment' in response.text
    assert 'event: done' not in response.text
    assert client.get(root+'/conversations', headers=owner).json() == []
