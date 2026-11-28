"""Task 1 API regressions with isolated DB/provider fixtures, not live tax verdicts."""
from uuid import uuid4
from decimal import Decimal
from io import BytesIO
import json
import httpx
import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from app import main,tax_verification
from app.core import make_token
from app.models import Invoice,InvoiceFile,ChatMessage
from tests.api_support import api_env

def test_secretstr_redaction_preserves_real_configuration_contract(monkeypatch):
    from pydantic import SecretStr
    from app.core import settings
    fixture='isolated-redaction-fixture-not-a-real-api-key'
    monkeypatch.setattr(settings,'gemini_api_key',SecretStr(fixture))
    assert fixture not in main.redact_chat_secrets('Public question '+fixture)
    assert main.redact_chat_secrets('Public question')=='Public question'

def headers(users,name):
    return {'Authorization':'Bearer '+make_token(users[name+'@phase2.test'],'employee' if name.startswith('employee') else name)}

def test_finance_roles_export_budget_and_chat(api_env):
    client,users,_=api_env
    for role in ('employee1','accountant','admin'):
        h=headers(users,role)
        analysis=client.get('/api/v1/finance/analysis',headers=h)
        assert analysis.status_code==200
        workbook=client.get('/api/v1/finance/analytics/export',headers=h)
        assert workbook.status_code==200
        assert load_workbook(BytesIO(workbook.content)).sheetnames
    budget={'starts_on':'2020-01-01','ends_on':'2020-12-31','amount':'10000000','currency':'VND','category':'travel'}
    assert client.post('/api/v1/finance/budgets',headers=headers(users,'employee1'),json=budget).status_code==403
    created=client.post('/api/v1/finance/budgets',headers=headers(users,'accountant'),json=budget)
    assert created.status_code==200
    assert client.get('/api/v1/finance/budgets',headers=headers(users,'admin')).status_code==200
    stream=client.post('/api/v1/chatbot/stream',headers=headers(users,'employee1'),json={'question':'Xuất Excel chi tiêu theo danh mục','request_id':str(uuid4())})
    assert stream.status_code==200 and 'event: done' in stream.text
    assert 'financial-analysis' in stream.text
    foreign=client.get('/api/v1/finance/analysis?employee_id='+str(users['employee2@phase2.test']),headers=headers(users,'employee1'))
    assert foreign.status_code in (200,403)
    if foreign.status_code==200:assert foreign.json()['scope']=='own'

@pytest.mark.parametrize('provider_status',['found','not_found','unavailable'])
def test_tax_stream_retry_history_and_scope(api_env,monkeypatch,provider_status):
    client,users,_=api_env
    registry={'tax_code':'3500806643','status':provider_status,'source':'Isolated provider fixture','checked_at':'2026-01-01T00:00:00Z','comparisons':[],'document_kind':'unknown','comparison_status':'insufficient_data','comparison_note':'Fixture only','name_observation_complete':False,'electronic_invoice':{'status':'not_verified','url':'https://hoadondientu.gdt.gov.vn/'}}
    monkeypatch.setattr(main,'verification_context',lambda fields,refresh=False:dict(registry))
    h=headers(users,'employee1');body={'question':'Tra cứu MST 3500806643','request_id':str(uuid4())}
    response=client.post('/api/v1/chatbot/stream',headers=h,json=body)
    assert response.status_code==200 and 'event: done' in response.text
    event=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')][-1]
    assert event['tax_verification']['status']==provider_status
    replay=client.post('/api/v1/chatbot/ask',headers=h,json={**body,'conversation_id':event['conversation_id']})
    assert replay.status_code==200 and replay.json()['mode']=='saved'
    detail=client.get('/api/v1/chatbot/conversations/'+str(event['conversation_id']),headers=h)
    assert detail.status_code==200 and len(detail.json()['messages'])==2
    message_id=event['tax_verification']['message_id']
    assert client.post('/api/v1/chatbot/tax-verifications/'+str(message_id)+'/refresh',headers=headers(users,'employee2')).status_code==404
    refreshed=client.post('/api/v1/chatbot/tax-verifications/'+str(message_id)+'/refresh',headers=h)
    assert refreshed.status_code==200 and refreshed.json()['message_id']!=message_id
    assert client.get('/api/v1/chatbot/conversations/'+str(event['conversation_id']),headers=headers(users,'employee2')).status_code==404

def test_public_provider_http_mapping_without_network(monkeypatch):
    payload={'code':'00','data':{'id':'3500806643','name':'Public business fixture','address':'Fixture address'}}
    monkeypatch.setattr(tax_verification.httpx,'get',lambda *a,**k:httpx.Response(200,json=payload,request=httpx.Request('GET','https://api.vietqr.io/v2/business/3500806643')))
    result=tax_verification.verify_tax_code('3500806643',refresh=True)
    assert result['status']=='found' and result['registered_name']==payload['data']['name']
