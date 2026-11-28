"""Additive SLA storage; no existing invoice, user or approval data is modified."""
from app.approval_sla import SLAPolicy, SLACycle, SLANotice

def upgrade(engine):
    with engine.begin() as connection:
        for model in (SLAPolicy, SLACycle, SLANotice):
            model.__table__.create(connection, checkfirst=True)

if __name__ == '__main__':
    from app.core import engine
    upgrade(engine)
