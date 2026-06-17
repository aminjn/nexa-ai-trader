from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from .. import models
from .utils import verify_password, get_password_hash, generate_otp, create_access_token


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def get_user_by_phone(db: Session, phone: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.phone == phone).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> Optional[models.User]:
    user = get_user_by_email(db, email)
    if not user or not user.hashed_password:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_user(db: Session, email: Optional[str] = None, phone: Optional[str] = None,
                password: Optional[str] = None, full_name: str = "کاربر جدید",
                is_superadmin: bool = False) -> models.User:
    user = models.User(
        email=email,
        phone=phone,
        hashed_password=get_password_hash(password) if password else None,
        full_name=full_name,
        is_superadmin=is_superadmin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_otp(db: Session, phone: str) -> str:
    code = generate_otp()
    # Invalidate old OTPs
    db.query(models.OTPCode).filter(
        models.OTPCode.phone == phone,
        models.OTPCode.used == False
    ).update({"used": True})

    otp = models.OTPCode(
        phone=phone,
        code=code,
        expires_at=datetime.utcnow() + timedelta(minutes=5),
    )
    db.add(otp)
    db.commit()
    return code


def verify_otp(db: Session, phone: str, code: str) -> bool:
    otp = db.query(models.OTPCode).filter(
        models.OTPCode.phone == phone,
        models.OTPCode.code == code,
        models.OTPCode.used == False,
        models.OTPCode.expires_at > datetime.utcnow(),
    ).first()
    if not otp:
        return False
    otp.used = True
    db.commit()
    return True


def get_or_create_phone_user(db: Session, phone: str) -> models.User:
    user = get_user_by_phone(db, phone)
    if not user:
        user = create_user(db, phone=phone, full_name=f"کاربر {phone[-4:]}")
    return user
