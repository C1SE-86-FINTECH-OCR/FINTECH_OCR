"""Additive only; never drops or modifies existing tables."""
from app.finance import ExpenseAssignment,FinanceHistory,Budget
def upgrade(engine):
 with engine.begin() as connection:
  upgrade_connection(connection)

def upgrade_connection(connection):
 for table in (ExpenseAssignment.__table__,FinanceHistory.__table__,Budget.__table__):table.create(connection,checkfirst=True)
if __name__=='__main__':
 from app.core import engine
 upgrade(engine)
