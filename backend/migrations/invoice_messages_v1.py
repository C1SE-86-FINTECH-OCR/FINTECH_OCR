"""Create the invoice message table for an existing database."""
from app.core import engine
from app.models import InvoiceMessage


if __name__ == '__main__':
    with engine.begin() as connection:
        InvoiceMessage.__table__.create(connection, checkfirst=True)
    print('Invoice messages table is ready.')
