"""API نوتیفیکیشن‌ها (کاربر و سوپر ادمین)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, get_superadmin

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _query_for(db, user):
    if user.is_superadmin:
        return db.query(models.Notification).filter(models.Notification.for_admin == True)
    return db.query(models.Notification).filter(
        models.Notification.for_admin == False,
        models.Notification.user_id == user.id,
    )


@router.get("/")
async def list_notifications(limit: int = 30, db: Session = Depends(get_db),
                             current_user: models.User = Depends(get_current_user)):
    rows = _query_for(db, current_user).order_by(models.Notification.created_at.desc()).limit(limit).all()
    unread = _query_for(db, current_user).filter(models.Notification.read == False).count()
    return {
        "unread": unread,
        "items": [{
            "id": n.id, "type": n.type, "title": n.title, "message": n.message,
            "link": n.link, "read": bool(n.read), "ref_user_id": n.ref_user_id,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        } for n in rows],
    }


@router.post("/read-all")
async def mark_all_read(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _query_for(db, current_user).filter(models.Notification.read == False).update({models.Notification.read: True})
    db.commit()
    return {"message": "همه خوانده شد"}


@router.post("/{nid}/read")
async def mark_read(nid: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    n = _query_for(db, current_user).filter(models.Notification.id == nid).first()
    if n:
        n.read = True
        db.commit()
    return {"message": "خوانده شد"}


# ───────────────────────── سوپر ادمین: ارسال اعلان به کاربران ─────────────────────────

class BroadcastRequest(BaseModel):
    title: str
    message: str
    user_ids: Optional[List[int]] = None   # None یا خالی = همهٔ کاربران
    send_telegram: bool = True             # ارسال به تلگرام/بلهٔ کاربرانِ متصل (push روی گوشی)
    link: str = "/notifications"


@router.post("/admin/broadcast")
async def broadcast(req: BroadcastRequest, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_superadmin)):
    """ارسال اعلان به کاربران: هم اعلانِ داخل اپ/PWA، هم پیامِ تلگرام/بله (push روی گوشی)."""
    q = db.query(models.User).filter(models.User.is_superadmin == False)
    if req.user_ids:
        q = q.filter(models.User.id.in_(req.user_ids))
    users = q.all()

    # ۱) اعلان داخل اپ (در زنگ/صفحهٔ اعلان‌ها و اعلان دستگاه هنگام باز بودن PWA دیده می‌شود)
    for u in users:
        db.add(models.Notification(for_admin=False, user_id=u.id, type="system",
                                   title=req.title, message=req.message, link=req.link))
    db.commit()

    # ۲) پیام تلگرام/بله برای کاربرانِ متصل → اعلان واقعی روی گوشی
    tg = bale = 0
    if req.send_telegram:
        from ..signals.notifier import send_telegram, send_bale
        s = db.query(models.SystemSettings).first()
        tg_token = (s.telegram_bot_token if s else "") or ""
        bale_token = (s.bale_bot_token if s else "") or ""
        text = f"🔔 {req.title}\n\n{req.message}"
        for u in users:
            if tg_token and (u.telegram_chat_id or "").strip():
                if await send_telegram(tg_token, u.telegram_chat_id, text):
                    tg += 1
            if bale_token and (u.bale_chat_id or "").strip():
                if await send_bale(bale_token, u.bale_chat_id, text):
                    bale += 1

    return {"message": f"اعلان برای {len(users)} کاربر ارسال شد",
            "users": len(users), "telegram": tg, "bale": bale}
