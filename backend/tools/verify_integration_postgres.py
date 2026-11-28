"""Isolated PostgreSQL integration checks. Never migrate the source database.

Use --connection-env only to obtain local server credentials. All writes target
new fintech_integration_* databases; no secret or connection URL is printed.
Legacy DDL is read from the supplied main commit without importing its runtime.
"""
import argparse,json,os,subprocess,sys,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def main():
    from dotenv import dotenv_values
    from sqlalchemy import create_engine,inspect,text,select
    from sqlalchemy.engine import make_url
    import psycopg
    from psycopg import sql
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--connection-env',required=True)
    parser.add_argument('--legacy-ref',default='e7a0860')
    args=parser.parse_args()
    source=make_url(dotenv_values(args.connection_env,interpolate=False)['DATABASE_URL'])
    if source.get_backend_name()!='postgresql' or source.host not in ('localhost','127.0.0.1'):raise RuntimeError('Local PostgreSQL required')
    tag=uuid.uuid4().hex[:10];names={key:'fintech_integration_'+key+'_'+tag for key in ('new','empty','history')}
    with psycopg.connect(source.set(drivername='postgresql',database='postgres').render_as_string(hide_password=False),autocommit=True) as admin:
        for name in names.values():admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    os.environ.update(DATABASE_URL=source.set(database=names['new']).render_as_string(hide_password=False),APP_ENV='testing',GEMINI_ENABLED='false',GEMINI_ALLOW_EXTERNAL_TRANSFER='false',OCR_INVOICE_GEMINI_ENABLED='false',OCR_LOCAL_PREVIEW_ENABLED='false')
    from app import main as api,travel
    from app.core import Base,hash_password
    from app.models import User,Schedule
    from datetime import datetime,date,timezone
    from sqlalchemy.orm import Session,DeclarativeBase
    from migrations.upgrade_existing import upgrade
    from verify_travel_workflow import verify
    engines={key:create_engine(source.set(database=name)) for key,name in names.items()}
    target=engines['new'];Base.metadata.create_all(target)
    with target.begin() as c:upgrade(c);upgrade(c)
    with Session(target) as db:
        for role in ('employee','accountant','admin'):
            db.add(User(full_name='Isolated integration '+role,email=role+'@integration.invalid',role=role,status='active',password_hash=hash_password(uuid.uuid4().hex)))
        db.commit()
    workflow=verify(target)
    # Existing target history, including fractional legacy VND, is untouched.
    from decimal import Decimal
    with Session(target) as db:
        owner=db.scalar(select(User).where(User.role=='employee'))
        trip=Schedule(title='Target history fixture',destination='Test',starts_at=datetime(2020,2,1,tzinfo=timezone.utc),ends_at=datetime(2020,2,2,tzinfo=timezone.utc),assigned_to=owner.id,created_by=owner.id,status='planned')
        db.add(trip);db.flush()
        case=travel.TravelCase(schedule_id=trip.id,owner_id=owner.id,schedule_snapshot={},requested=Decimal('0.01'),approved=Decimal('0.01'),purpose='Isolated historical preservation',status='disbursed')
        db.add(case);db.commit();case_id=case.id
    with target.begin() as c:
        before=dict(c.execute(select(travel.TravelCase.__table__).where(travel.TravelCase.id==case_id)).mappings().one())
        upgrade(c);upgrade(c)
        after=dict(c.execute(select(travel.TravelCase.__table__).where(travel.TravelCase.id==case_id)).mappings().one())
        assert before==after and after['requested']==Decimal('0.01')
    # Generate the exact legacy main Travel models in independent test metadata.
    class LegacyBase(DeclarativeBase):pass
    old=subprocess.check_output(['git','show',args.legacy_ref+':backend/app/travel_models.py'],text=True,encoding='utf-8')
    old=old.replace('from .core import Base','').replace('from .models import now','')
    namespace={'Base':LegacyBase,'now':travel.now,'__name__':'isolated_legacy_schema'}
    exec(compile(old,'<legacy-main-model-fixture>','exec'),namespace)
    target_names={model.__tablename__ for model in (travel.TravelCase,travel.TravelExpense,travel.TravelTransaction,travel.TravelEvidence,travel.TravelHistory,travel.TravelSLA)}
    for table in Base.metadata.sorted_tables:
        if table.name not in target_names:table.to_metadata(LegacyBase.metadata)
    for key in ('empty','history'):LegacyBase.metadata.create_all(engines[key])
    with engines['empty'].begin() as c:upgrade(c);upgrade(c)
    with engines['empty'].connect() as c:
        assert 'case_id' in {col['name'] for col in inspect(c).get_columns('travel_expenses')}
        assert 'advance_id' in {col['name'] for col in inspect(c).get_columns('travel_expenses',schema='travel_legacy_main')}
    # A history event is sufficient to demonstrate fail-closed preservation.
    with Session(engines['history']) as db:
        db.add(User(id=1,full_name='Isolated legacy',email='legacy@integration.invalid',password_hash='not-authentication-data',role='employee',status='active'));db.flush()
        db.add(Schedule(id=1,title='Legacy fixture',destination='Test',starts_at=datetime(2020,1,1,tzinfo=timezone.utc),ends_at=datetime(2020,1,2,tzinfo=timezone.utc),assigned_to=1,created_by=1,status='planned'));db.flush()
        db.add(namespace['TravelAdvance'](id=1,request_id='legacy-fixture',employee_id=1,schedule_id=1,employee_name='Isolated legacy',trip_title='Fixture',starts_on=date(2020,1,1),ends_on=date(2020,1,2),reason='Test',requested=10000000,approved=10000000,disbursed=10000000,status='disbursed'));db.commit()
    blocked=False
    try:
        with engines['history'].begin() as c:upgrade(c)
    except RuntimeError as exc:
        if 'LEGACY_TRAVEL_RECONCILIATION_REQUIRED' not in str(exc):raise
        blocked=True
    with engines['history'].connect() as c:
        assert c.execute(text('SELECT requested FROM travel_advances WHERE id=1')).scalar()==10000000
        assert 'advance_id' in {col['name'] for col in inspect(c).get_columns('travel_expenses')}
        assert 'travel_cases' not in inspect(c).get_table_names()
    print(json.dumps({'databases':names,'new_database_migration':True,'existing_target_history_unchanged':True,'empty_legacy_migration':True,'nonempty_legacy_safely_blocked':blocked,'workflow':workflow,'source_database_migrated':False}))

if __name__=='__main__':main()
