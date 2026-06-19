"""پروفایل کاربر و احراز هویت (KYC) با هوش مصنوعی."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, get_superadmin
from ..ai.identity import verify_identity, AUTO_VERIFY_THRESHOLD
from ..notifications import notify_admin, notify_user

router = APIRouter(prefix="/profile", tags=["profile"])


def _profile_out(u: models.User) -> dict:
    return {
        "id": u.id,
        "full_name": u.full_name,
        "email": u.email,
        "phone": u.phone,
        "national_id": u.national_id or "",
        "birth_date": u.birth_date or "",
        "avatar": u.avatar or "",
        "is_superadmin": u.is_superadmin,
        "kyc_status": u.kyc_status or "none",
        "kyc_match_score": round(u.kyc_match_score or 0, 1),
        "kyc_note": u.kyc_note or "",
        "kyc_submitted_at": u.kyc_submitted_at.isoformat() if u.kyc_submitted_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


@router.get("/")
async def get_profile(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return _profile_out(current_user)


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    birth_date: Optional[str] = None
    national_id: Optional[str] = None
    avatar: Optional[str] = None


@router.put("/")
async def update_profile(req: ProfileUpdate, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    if req.full_name is not None:
        current_user.full_name = req.full_name.strip() or current_user.full_name
    if req.birth_date is not None:
        current_user.birth_date = req.birth_date.strip()
    # کد ملی بعد از تأیید هویت قابل تغییر نیست
    if req.national_id is not None and (current_user.kyc_status != "verified"):
        current_user.national_id = req.national_id.strip()
    if req.avatar is not None:
        current_user.avatar = req.avatar
    db.commit()
    return _profile_out(current_user)


class KycSubmit(BaseModel):
    card_image: str               # data-uri base64 (کارت ملی)
    video: str = ""               # data-uri base64 ویدئوی احراز هویت (الزامی)
    frames: list = []             # فریم‌های استخراج‌شده از ویدئو (data-uri)
    challenge: str = ""           # عبارتی که کاربر باید گفته باشد
    national_id: Optional[str] = ""
    birth_date: Optional[str] = ""


@router.post("/kyc")
async def submit_kyc(req: KycSubmit, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    """ارسال مدارک احراز هویت ویدئویی؛ هوش مصنوعی تطابق چهره و زنده‌بودن را می‌سنجد."""
    if current_user.kyc_status == "verified":
        raise HTTPException(status_code=400, detail="هویت شما قبلاً تأیید شده است")
    if not req.card_image:
        raise HTTPException(status_code=400, detail="تصویر کارت ملی الزامی است")
    if not req.video or not req.frames:
        raise HTTPException(status_code=400, detail="ویدئوی احراز هویت الزامی است (عکس پذیرفته نمی‌شود)")

    current_user.kyc_card_image = req.card_image
    current_user.kyc_video = req.video
    current_user.kyc_selfie_image = (req.frames[0] if req.frames else "")  # فریم نماینده
    current_user.kyc_challenge = req.challenge
    current_user.kyc_submitted_at = datetime.utcnow()
    if req.national_id:
        current_user.national_id = req.national_id.strip()
    if req.birth_date:
        current_user.birth_date = req.birth_date.strip()

    # تحلیل با هوش مصنوعی (مدل‌های گپ) روی فریم‌های ویدئو
    result = await verify_identity(req.card_image, req.frames, db=db)
    current_user.kyc_match_score = result.get("confidence", 0)
    reason = result.get("reason", "")

    ok = (result.get("match") and result.get("is_id_card") and result.get("is_real_selfie")
          and result.get("confidence", 0) >= AUTO_VERIFY_THRESHOLD)
    if ok:
        current_user.kyc_status = "verified"
        current_user.kyc_note = f"تأیید خودکار هوش مصنوعی (اطمینان {result.get('confidence')}٪). {reason}"
        db.commit()
        notify_admin(db, "kyc", "احراز هویت تأیید شد",
                     f"{current_user.full_name} با تأیید خودکار هوش مصنوعی احراز هویت شد.",
                     ref_user_id=current_user.id, link="/admin")
        notify_user(db, current_user.id, "kyc", "احراز هویت تأیید شد",
                    "هویت شما با موفقیت تأیید شد ✅")
    else:
        # نیاز به بررسی دستی سوپر ادمین
        current_user.kyc_status = "pending"
        current_user.kyc_note = f"در انتظار بررسی دستی (اطمینان هوش مصنوعی {result.get('confidence')}٪). {reason}"
        db.commit()
        notify_admin(db, "kyc", "درخواست احراز هویت جدید",
                     f"{current_user.full_name} مدارک احراز هویت ارسال کرد (اطمینان AI: {result.get('confidence')}٪).",
                     ref_user_id=current_user.id, link="/admin")
    return {"kyc_status": current_user.kyc_status, "match_score": current_user.kyc_match_score,
            "note": current_user.kyc_note, "auto": ok}


# ───────────────────────── سوپر ادمین ─────────────────────────

@router.get("/admin/kyc")
async def admin_kyc_list(status: str = "pending", db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_superadmin)):
    q = db.query(models.User)
    if status:
        q = q.filter(models.User.kyc_status == status)
    users = q.order_by(models.User.kyc_submitted_at.desc().nullslast()).all()
    return [{
        "id": u.id, "full_name": u.full_name, "phone": u.phone or u.email,
        "national_id": u.national_id, "birth_date": u.birth_date,
        "kyc_status": u.kyc_status, "kyc_match_score": round(u.kyc_match_score or 0, 1),
        "kyc_note": u.kyc_note,
        "kyc_submitted_at": u.kyc_submitted_at.isoformat() if u.kyc_submitted_at else None,
    } for u in users]


@router.get("/admin/kyc/{user_id}/images")
async def admin_kyc_images(user_id: int, db: Session = Depends(get_db),
                           current_user: models.User = Depends(get_superadmin)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    return {"card_image": u.kyc_card_image or "", "selfie_image": u.kyc_selfie_image or "",
            "video": u.kyc_video or "", "challenge": u.kyc_challenge or ""}


class KycDecision(BaseModel):
    approve: bool
    note: str = ""


@router.post("/admin/kyc/{user_id}/decide")
async def admin_kyc_decide(user_id: int, req: KycDecision, db: Session = Depends(get_db),
                           current_user: models.User = Depends(get_superadmin)):
    u = db.query(models.User).filter(models.User.id == user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    u.kyc_status = "verified" if req.approve else "rejected"
    if req.note:
        u.kyc_note = req.note
    db.commit()
    notify_user(db, u.id, "kyc",
                "احراز هویت تأیید شد" if req.approve else "احراز هویت رد شد",
                ("هویت شما تأیید شد ✅" if req.approve else f"مدارک شما تأیید نشد. {req.note}"))
    return {"kyc_status": u.kyc_status}
