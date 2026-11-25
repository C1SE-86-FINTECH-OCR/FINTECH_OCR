"""Create direct employee/accountant messaging without changing existing data."""
from app.core import engine
from app.models import DirectMessage

if __name__ == '__main__':
    with engine.begin() as connection:
        DirectMessage.__table__.create(connection, checkfirst=True)
    print('Direct messages table is ready.')
