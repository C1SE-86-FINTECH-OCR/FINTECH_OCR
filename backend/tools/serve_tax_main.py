"""Run the existing application configuration, with read-only schema preflight."""
import argparse
import os
import re
import sys
from pathlib import Path

backend=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(backend))
os.chdir(backend)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-casso',action='store_true',help='Explicit use of the authorized official Public Starter Key')
    args=parser.parse_args()
    from app.core import settings,engine,Base
    from app import models,finance,approval_sla,travel
    from sqlalchemy import inspect,text
    if engine.url.get_backend_name()!='postgresql':
        raise RuntimeError('This launcher requires the configured PostgreSQL database')
    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'))
            inspector=inspect(connection)
            tables=set(inspector.get_table_names())
            missing=[]
            for name,table in Base.metadata.tables.items():
                if name not in tables:
                    missing.append(name);continue
                columns={column['name'] for column in inspector.get_columns(name)}
                missing.extend(name+'.'+column.name for column in table.columns if column.name not in columns)
            if missing:
                raise RuntimeError('Schema migration required: '+', '.join(missing))
    if args.public_casso:
        from dotenv import dotenv_values
        config=dotenv_values(backend/'.env',interpolate=False)
        if not ((os.getenv('CASSO_APP_ID') or config.get('CASSO_APP_ID')) and
                (os.getenv('CASSO_APP_SECRET') or config.get('CASSO_APP_SECRET'))):
            import httpx
            response=httpx.get('https://www.vietqr.io/tra-cuu-mst',timeout=15)
            response.raise_for_status()
            app_id=re.search(r'trial-app_[A-Za-z0-9]+',response.text)
            secret=re.search(r'sec_[A-Za-z0-9]+',response.text)
            if app_id and secret:
                os.environ.update(CASSO_APP_ID=app_id.group(),CASSO_APP_SECRET=secret.group())
    from app.main import app
    import uvicorn
    print('Configured database: '+str(engine.url.database)+'; OCR: '+settings.effective_ocr_pipeline,flush=True)
    uvicorn.run(app,host='127.0.0.1',port=8000)

if __name__=='__main__':
    main()
