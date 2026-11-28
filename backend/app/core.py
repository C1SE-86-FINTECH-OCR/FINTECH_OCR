from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator
from typing import Literal
import os
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, SecretStr, model_validator
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
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
    ocr_pipeline: Literal['current', 'hybrid_v6', 'hybrid_v7', 'hybrid_v8', 'hybrid_v8_final'] = 'current'
    ocr_hybrid_fallback: bool = True
    # Invoice extraction only. The independent Gemini chatbot is unaffected.
    ocr_invoice_gemini_enabled: bool = False
    ocr_hybrid_max_pages: int = Field(default=12, ge=1, le=12)
    # Separate, opt-in development route; never grants G13 acceptance.
    ocr_local_preview_enabled: bool = False
    ocr_local_preview_pipeline: Literal['current', 'hybrid_v8_final'] = 'current'
    ocr_local_preview_host: Literal['127.0.0.1', '::1'] = '127.0.0.1'
    # Selecting Gemini does not authorize transferring invoice text. Both
    # switches, credentials, model and an approval reference are required.
    gemini_enabled: bool = False
    # Search entitlement is independent of text-generation Free Tier.
    gemini_search_grounding_enabled: bool = False
    gemini_search_free_tier_confirmed: bool = False
    gemini_allow_external_transfer: bool = False
    # Free-only policy. These attestations never enable billing or authorize
    # arbitrary uploaded invoices; every eligible file also needs approval.
    gemini_free_tier_confirmed: bool = False
    gemini_billing_disabled_confirmed: bool = False
    gemini_free_tier_reference: str | None = Field(default=None, repr=False)
    gemini_free_tier_manifest: str | None = None
    # Administrator policy only; uploads never grant new sharing permission.
    gemini_auto_policy_enabled: bool = False
    gemini_auto_policy_user_ids: str = ''
    gemini_auto_policy_mode: Literal['manifest', 'approved_scope'] = 'manifest'
    gemini_auto_policy_path: str | None = None
    gemini_policy_audit_dir: str = str(BACKEND_DIR.parent.parent / 'Gemini_FreeTier' / 'policy_decisions')
    # Legacy paid settings remain readable for configuration compatibility.
    # Paid confirmation is rejected by the current free-only Gemini policy.
    gemini_paid_tier_confirmed: bool = False
    gemini_paid_tier_reference: str | None = Field(default=None, repr=False)
    gemini_data_processing_approved: bool = False
    gemini_api_key: SecretStr | None = Field(default=None, repr=False)
    gemini_model: str | None = None
    gemini_approval_reference: str | None = None
    gemini_max_output_tokens: int = Field(default=8192, ge=256, le=32768)
    gemini_rate_limit_cooldown_seconds: int = Field(default=60, ge=1, le=86400)
    gemini_max_attempts: int = Field(default=3, ge=1, le=3)
    gemini_retry_initial_seconds: float = Field(default=2, ge=1, le=10)
    gemini_retry_budget_seconds: float = Field(default=60, ge=30, le=60)
    # Conservative local ceilings for the currently approved Free Tier.
    # Actual project-wide quota (including TPM) remains enforced by Google.
    gemini_requests_per_minute: int = Field(default=5, ge=1, le=5)
    gemini_requests_per_day: int = Field(default=20, ge=1, le=20)

    @model_validator(mode='after')
    def experimental_ocr_requires_testing(self):
        if self.ocr_local_preview_enabled:
            if self.app_env != 'development' or self.ocr_pipeline != 'current':
                raise ValueError('Local preview requires APP_ENV=development and the normal OCR_PIPELINE=current')
            url = make_url(self.database_url)
            uploads = Path(self.upload_dir)
            if not uploads.is_absolute():
                uploads = BACKEND_DIR / uploads
            if (url.get_backend_name() != 'postgresql' or url.database != 'fintech_ocr_rbac_test'
                    or url.host not in ('localhost', '127.0.0.1', '::1')
                    or uploads.resolve() != (BACKEND_DIR / 'uploads_rbac_test').resolve()
                    or not uploads.is_dir() or not self.ocr_hybrid_fallback):
                raise ValueError('Local preview requires the existing local PostgreSQL test database, test uploads and OCR fallback')
        if self.ocr_pipeline in ('hybrid_v6','hybrid_v7','hybrid_v8','hybrid_v8_final') and self.app_env != 'testing':
            raise ValueError('Hybrid OCR is experimental: set APP_ENV=testing')
        return self

    @property
    def effective_ocr_pipeline(self):
        return self.ocr_local_preview_pipeline if self.ocr_local_preview_enabled else self.ocr_pipeline
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
