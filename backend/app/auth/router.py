from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import timedelta
from .. import models
from ..database import get_db
from ..config import settings
from . import service
from .utils import create_access_token, decode_token

router = APIRouter(prefix="/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class EmailLoginRequest(BaseModel):
    email: str
    password: str


class PhoneRequest(BaseModel):
    phone: str


class OTPVerifyRequest(BaseModel):
    phone: str
    code: str


class RegisterRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    full_name: str = "کاربر جدید"


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    is_superadmin: bool
    full_name: str


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="توکن نامعتبر است")
    user = service.get_user_by_id(db, int(payload.get("sub", 0)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="کاربر یافت نشد")
    return user


def get_superadmin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="دسترسی مجاز نیست")
    return current_user


@router.post("/token")
async def login_form(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="ایمیل یا رمز عبور اشتباه است")
    token = create_access_token({"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login/email", response_model=TokenResponse)
async def login_email(req: EmailLoginRequest, db: Session = Depends(get_db)):
    user = service.authenticate_user(db, req.email, req.password)
    if not user:
        raise HTTPException(status_code=400, detail="ایمیل یا رمز عبور اشتباه است")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="حساب کاربری غیرفعال است")
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_superadmin=user.is_superadmin,
        full_name=user.full_name,
    )


@router.post("/register")
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    if req.email:
        if service.get_user_by_email(db, req.email):
            raise HTTPException(status_code=400, detail="این ایمیل قبلاً ثبت شده است")
    if req.phone:
        if service.get_user_by_phone(db, req.phone):
            raise HTTPException(status_code=400, detail="این شماره قبلاً ثبت شده است")
    user = service.create_user(
        db, email=req.email, phone=req.phone,
        password=req.password, full_name=req.full_name
    )
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_superadmin=user.is_superadmin,
        full_name=user.full_name,
    )


@router.post("/send-otp")
async def send_otp(req: PhoneRequest, db: Session = Depends(get_db)):
    code = service.create_otp(db, req.phone)
    # In production send via SMS; for now return in response for dev
    return {"message": "کد OTP ارسال شد", "dev_code": code}


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(req: OTPVerifyRequest, db: Session = Depends(get_db)):
    if not service.verify_otp(db, req.phone, req.code):
        raise HTTPException(status_code=400, detail="کد OTP نامعتبر یا منقضی شده است")
    user = service.get_or_create_phone_user(db, req.phone)
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        is_superadmin=user.is_superadmin,
        full_name=user.full_name,
    )


@router.get("/me")
async def get_me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "phone": current_user.phone,
        "full_name": current_user.full_name,
        "is_superadmin": current_user.is_superadmin,
        "is_active": current_user.is_active,
        "bot_active": current_user.bot_active,
        "created_at": current_user.created_at,
    }
