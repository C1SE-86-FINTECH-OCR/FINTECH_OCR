"""Additive travel ledger and notification link; preserve every existing row."""
from sqlalchemy import inspect,text
from app.travel import TravelCase,TravelExpense,TravelTransaction,TravelEvidence,TravelHistory,TravelSLA

TABLES=(TravelCase,TravelExpense,TravelTransaction,TravelEvidence,TravelHistory,TravelSLA)

def preflight_connection(c):
    inspector=inspect(c);tables=set(inspector.get_table_names())
    legacy={'travel_advances','travel_payments','travel_payment_evidence','travel_advance_events'}&tables
    if 'travel_expenses' in tables:
        columns={col['name'] for col in inspector.get_columns('travel_expenses')}
        if 'advance_id' in columns and 'case_id' not in columns:legacy.add('travel_expenses')
        elif 'case_id' not in columns:raise RuntimeError('Unknown travel_expenses schema; no automatic changes are safe')
        else:
            missing={column.name for column in TravelExpense.__table__.columns}-columns
            if missing:raise RuntimeError('Incomplete target travel_expenses schema; reconciliation required for columns: '+', '.join(sorted(missing)))
    populated=[name for name in sorted(legacy) if c.execute(text('SELECT EXISTS (SELECT 1 FROM "'+name+'")')).scalar()]
    if populated:
        raise RuntimeError('LEGACY_TRAVEL_RECONCILIATION_REQUIRED: '+', '.join(populated)+
            '. Migration stopped before changes: legacy workflow has no independently recorded receipt confirmation; '
            'actor, refund evidence, rejected/cancelled states and expense scope require an approved lossless mapping. '
            'No history is inferred, overwritten or deleted.')
    return legacy
def upgrade(engine):
    with engine.begin() as c:
        upgrade_connection(c)

def upgrade_connection(c):
    legacy=preflight_connection(c)
    if 'travel_expenses' in legacy:
        if c.dialect.name=='postgresql':
            c.execute(text('CREATE SCHEMA IF NOT EXISTS travel_legacy_main'))
            c.execute(text('ALTER TABLE travel_expenses SET SCHEMA travel_legacy_main'))
        else:
            c.execute(text('ALTER TABLE travel_expenses RENAME TO travel_expenses_legacy_main'))
    # Preserve empty legacy tables for audit; only the feature/thien models run.
    from app.approval_sla import SLAPolicy,SLACycle,SLANotice
    for model in (SLAPolicy,SLACycle,SLANotice):model.__table__.create(c,checkfirst=True)
    for model in TABLES:model.__table__.create(c,checkfirst=True)
    if 'travel_case_id' not in {col['name'] for col in inspect(c).get_columns('notifications')}:
        c.execute(text('ALTER TABLE notifications ADD COLUMN travel_case_id INTEGER REFERENCES travel_cases(id)'))
    c.execute(text('CREATE INDEX IF NOT EXISTS ix_notifications_travel_case_id ON notifications(travel_case_id)'))

if __name__=='__main__':
    from app.core import engine
    upgrade(engine)
