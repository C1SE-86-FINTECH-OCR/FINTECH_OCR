"""Read-only PostgreSQL and pgvector verification."""
import os, sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, select, func, text
BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core import Base
import app.models  # noqa: F401

def main():
    url=os.environ.get('PG_MIGRATION_URL','')
    if not url.startswith('postgresql+psycopg://'): raise SystemExit('[STOP] Cần PG_MIGRATION_URL')
    engine=create_engine(url)
    try:
        with engine.connect() as conn:
            print('[POSTGRESQL]',conn.scalar(text('SHOW server_version')))
            print('[PGVECTOR]',conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'")) or 'CHƯA BẬT')
            names=set(inspect(conn).get_table_names())
            tables=Base.metadata.sorted_tables
            print('[TABLES]',len(names & {t.name for t in tables}),'/',len(tables))
            for table in tables:
                if table.name in names: print(' ',table.name, conn.scalar(select(func.count()).select_from(table)))
    finally: engine.dispose()

if __name__=='__main__': main()
