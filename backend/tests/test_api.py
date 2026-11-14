import os
import secrets
os.environ['DATABASE_URL']='sqlite:///./test_fintech.db'
os.environ['UPLOAD_DIR']='test_uploads'
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.core import Base,engine,SessionLocal,hash_password
from app.models import User
from app.main import app

def test_auth_and_rbac():
    test_password=secrets.token_urlsafe(24)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for email,role in [('emp@test.local','employee'),('adm@test.local','admin')]:
            user=db.query(User).filter_by(email=email).first()
            if not user:
                user=User(email=email,full_name='Test Person',role=role,password_hash=hash_password(test_password))
                db.add(user)
            else:
                user.password_hash=hash_password(test_password)
        db.commit()
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        res=c.post('/api/v1/auth/login',json={'email':'emp@test.local','password':test_password})
        assert res.status_code==200,res.text
        h={'Authorization':'Bearer '+res.json()['access_token']}
        assert c.get('/api/v1/auth/me',headers=h).json()['role']=='employee'
        assert c.get('/api/v1/users',headers=h).status_code==403
        assert c.get('/api/v1/invoices',headers=h).status_code==200
        assert c.post('/api/v1/auth/logout',headers=h).status_code==200
        assert c.get('/api/v1/auth/me',headers=h).status_code==401
