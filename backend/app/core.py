from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
import os
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session

BACKEND_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / '.env', env_file_encoding='utf-8', extra='ignore')
    database_url: str = 'sqlite:///' + (BACKEND_DIR / 'fintech_ocr.db').as_posix()
    jwt_secret: str = 'dev-only-replace-this-with-random-long-secret-32-characters'
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:8081'
    upload_dir: str = 'uploads'
    max_upload_mb: int = 20
    access_token_minutes: int = 480
    app_env: str = 'development'
    gemini_api_key: str = ''
    gemini_model: str = 'gemini-3.1-flash-lite'
settings=Settings()
if settings.app_env == 'production' and settings.jwt_secret.startswith('dev-only'):
    raise RuntimeError('Set a secure JWT_SECRET before production')
connect_args={'check_same_thread':False} if settings.database_url.startswith('sqlite') else {}
engine=create_engine(settings.database_url,connect_args=connect_args,pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autocommit=False,autoflush=False)
class Base(DeclarativeBase): pass

def db_session() -> Generator[Session,None,None]:
    with SessionLocal() as db:
        yield db

hasher=PasswordHasher()
def hash_password(password:str)->str: return hasher.hash(password)
def verify_password(password:str,encoded:str)->bool:
    try:return hasher.verify(encoded,password)
    except (VerifyMismatchError,InvalidHashError): return False

def make_token(user_id:int,role:str)->str:
    from uuid import uuid4
    now=datetime.now(timezone.utc)
    payload={'sub':str(user_id),'role':role,'jti':str(uuid4()),'iat':now,'exp':now+timedelta(minutes=settings.access_token_minutes)}
    return jwt.encode(payload,settings.jwt_secret,algorithm='HS256')

bearer=HTTPBearer(auto_error=False)
def current_user(credentials:HTTPAuthorizationCredentials|None=Depends(bearer),db:Session=Depends(db_session)):
    from .models import User, RevokedToken
    if not credentials:
        raise HTTPException(status_code=401,detail='Bạn cần đăng nhập')
    try:
        data=jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=['HS256'])
        user_id=int(data['sub'])
    except (jwt.InvalidTokenError,ValueError,KeyError):
        raise HTTPException(status_code=401,detail='Phiên đăng nhập không hợp lệ')
    if db.get(RevokedToken,data.get('jti')) is not None:
        raise HTTPException(status_code=401,detail='Phiên đã đăng xuất')
    user=db.get(User,user_id)
    if not user or user.status!='active':
        raise HTTPException(status_code=401,detail='Tài khoản không hoạt động')
    return user

def require_roles(*allowed):
    def dep(user=Depends(current_user)):
        if user.role not in allowed:raise HTTPException(status_code=403,detail='Bạn không có quyền sử dụng chức năng này')
        return user
    return dep

def storage_dir()->Path:
    p=Path(settings.upload_dir)
    if not p.is_absolute():p=BACKEND_DIR / p
    p=p.resolve();p.mkdir(parents=True,exist_ok=True);return p
