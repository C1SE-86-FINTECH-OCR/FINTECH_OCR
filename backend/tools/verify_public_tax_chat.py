"""Live public-business Tax/Chat check, restricted to isolated PostgreSQL DBs.

No image, private history or financial figures are accepted by this verifier.
Credentials stay in memory; output contains statuses, never secret values.
"""
import argparse,json,os,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def run():
    from dotenv import dotenv_values
    from sqlalchemy.engine import make_url
    import httpx
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection-env',required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--tax-code',required=True)
    parser.add_argument('--public-casso',action='store_true')
    args=parser.parse_args()
    if not args.database.startswith('fintech_integration_'):raise RuntimeError('Isolated integration DB required')
    if not re.fullmatch(r'\d{10}(?:\d{3})?',args.tax_code):raise RuntimeError('Valid public business identifier required')
    config=dotenv_values(args.connection_env,interpolate=False)
    url=make_url(config['DATABASE_URL'])
    if url.host not in ('localhost','127.0.0.1'):raise RuntimeError('Local test server required')
    for key,value in config.items():
        if key.startswith('GEMINI_') and value is not None:os.environ[key]=value
    os.environ.update(APP_ENV='testing',DATABASE_URL=url.set(database=args.database).render_as_string(hide_password=False),OCR_LOCAL_PREVIEW_ENABLED='false',OCR_PIPELINE='current')
    if args.public_casso:
        page=httpx.get('https://www.vietqr.io/tra-cuu-mst',timeout=15);page.raise_for_status()
        app_id=re.search(r'trial-app_[A-Za-z0-9]+',page.text);secret=re.search(r'sec_[A-Za-z0-9]+',page.text)
        if app_id and secret:os.environ.update(CASSO_APP_ID=app_id.group(),CASSO_APP_SECRET=secret.group())
    from app import main,gemini_chat
    from app.core import SessionLocal,make_token,settings
    from app.models import User
    from sqlalchemy import select
    from fastapi.testclient import TestClient
    from uuid import uuid4
    if not (settings.gemini_enabled and settings.gemini_allow_external_transfer and settings.gemini_free_tier_confirmed and settings.gemini_billing_disabled_confirmed and settings.gemini_data_processing_approved and settings.gemini_approval_reference):raise RuntimeError('Existing Gemini approval/configuration incomplete')
    with SessionLocal() as db:
        employee=db.scalar(select(User).where(User.role=='employee',User.status=='active'))
        if employee is None:raise RuntimeError('Existing isolated Employee fixture required')
        uid=employee.id
    client=TestClient(main.app);headers={'Authorization':'Bearer '+make_token(uid,'employee')}
    started=time.monotonic()
    response=client.post('/api/v1/chatbot/stream',headers=headers,json={'question':'Tra cứu MST '+args.tax_code,'request_id':str(uuid4())})
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    done=events[-1] if events else {};tax=done.get('tax_verification') or {}
    result={'database':args.database,'http':response.status_code,'kind':done.get('kind'),'llm_status':done.get('llm_status'),'tax_status':tax.get('status'),'model':gemini_chat.active_model_name(),'name_present':bool(tax.get('registered_name')),'tax_department_present':bool(tax.get('tax_department')),'operating_status_present':bool(tax.get('operating_status')),'source':tax.get('source'),'supplementary_source':tax.get('supplementary_source'),'invoice_authenticity_verified':tax.get('invoice_authenticity_verified'),'elapsed_seconds':round(time.monotonic()-started,2),'public_data_only':True}
    if done.get('conversation_id'):
        history=client.get('/api/v1/chatbot/conversations/'+str(done['conversation_id']),headers=headers)
        result.update(history_http=history.status_code,saved_messages=len(history.json().get('messages',[])))
    if tax.get('message_id'):
        refreshed=client.post('/api/v1/chatbot/tax-verifications/'+str(tax['message_id'])+'/refresh',headers=headers)
        result.update(refresh_http=refreshed.status_code,refresh_appended=refreshed.json().get('message_id')!=tax['message_id'])
    print(json.dumps(result))
    return 0 if result['http']==200 and result['llm_status']=='completed' and result['tax_status']=='found' else 1

if __name__=='__main__':
    try:sys.exit(run())
    except Exception as error:
        print(json.dumps({'completed':False,'error_type':type(error).__name__}));sys.exit(1)
