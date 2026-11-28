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
        assert 'travel_evidence' in inspect(connection).get_table_names()
    detail = client.get(f'/api/v1/chatbot/conversations/{conv_id}', headers=headers(users, 'employee1')).json()
    assert detail['messages'][0]['content'] == 'Still available'
    assert detail['updated_at'].startswith('2025-10-01T12:00:00')




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
