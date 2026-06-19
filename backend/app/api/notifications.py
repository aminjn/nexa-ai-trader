"""API نوتیفیکیشن‌ها (کاربر و سوپر ادمین)."""
from fastapi import APIRouter, Depends, BackgroundTasks
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


# ───────────────────────── Web Push (PWA/موبایل) ─────────────────────────

@router.get("/vapid-public-key")
async def vapid_public_key(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    from ..push_web import ensure_vapid_keys
    pub, _ = ensure_vapid_keys(db)
    return {"key": pub}


class PushSub(BaseModel):
    endpoint: str
    p256dh: str
    auth: str


@router.post("/subscribe")
async def subscribe_push(req: PushSub, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_current_user)):
    """اشتراک Web Push مرورگر را ذخیره می‌کند (برای پوشِ واقعی روی گوشی)."""
    existing = db.query(models.PushSubscription).filter(
        models.PushSubscription.endpoint == req.endpoint).first()
    if existing:
        existing.user_id = current_user.id
        existing.p256dh = req.p256dh
        existing.auth = req.auth
    else:
        db.add(models.PushSubscription(user_id=current_user.id, endpoint=req.endpoint,
                                       p256dh=req.p256dh, auth=req.auth))
    db.commit()
    return {"message": "ثبت شد"}


# ───────────────────────── سوپر ادمین: ارسال اعلان به کاربران ─────────────────────────

class BroadcastRequest(BaseModel):
    title: str
    message: str
    user_ids: Optional[List[int]] = None   # None یا خالی = همهٔ کاربران
    send_telegram: bool = True             # ارسال به تلگرام/بلهٔ کاربرانِ متصل (push روی گوشی)
    link: str = "/notifications"


async def _deliver_broadcast(user_ids, title, message, link, send_messengers):
    """ارسال Web Push و پیام تلگرام/بله در پس‌زمینه (تا درخواست کند نشود)."""
    from ..database import SessionLocal
    db = SessionLocal()
    try:
        # Web Push (اپِ بسته هم می‌رسد)
        try:
            from ..push_web import push_to_users
            push_to_users(db, user_ids, title, message, link)
        except Exception:
            pass
        # تلگرام/بله برای کاربرانِ متصل
        if send_messengers:
            from ..signals.notifier import send_telegram, send_bale
            s = db.query(models.SystemSettings).first()
            tg_token = (s.telegram_bot_token if s else "") or ""
            bale_token = (s.bale_bot_token if s else "") or ""
            text = f"🔔 {title}\n\n{message}"
            users = db.query(models.User).filter(models.User.id.in_(user_ids)).all() if user_ids else []
            for u in users:
                try:
                    if tg_token and (u.telegram_chat_id or "").strip():
                        await send_telegram(tg_token, u.telegram_chat_id, text)
                    if bale_token and (u.bale_chat_id or "").strip():
                        await send_bale(bale_token, u.bale_chat_id, text)
                except Exception:
                    continue
    finally:
        db.close()


@router.post("/admin/broadcast")
async def broadcast(req: BroadcastRequest, background_tasks: BackgroundTasks,
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_superadmin)):
    """ارسال اعلان به کاربران: اعلانِ داخل اپ فوری ثبت می‌شود؛ پوش و تلگرام/بله در پس‌زمینه."""
    q = db.query(models.User).filter(models.User.is_superadmin == False)
    if req.user_ids:
        q = q.filter(models.User.id.in_(req.user_ids))
    users = q.all()
    user_ids = [u.id for u in users]

    # ۱) اعلان داخل اپ (سریع — همین‌جا ثبت می‌شود)
    for uid in user_ids:
        db.add(models.Notification(for_admin=False, user_id=uid, type="system",
                                   title=req.title, message=req.message, link=req.link))
    db.commit()

    # ۲) ارسال پوش و تلگرام/بله در پس‌زمینه (درخواست بلافاصله برمی‌گردد)
    background_tasks.add_task(_deliver_broadcast, user_ids, req.title, req.message,
                             req.link, req.send_telegram)

    return {"message": f"اعلان برای {len(users)} کاربر ثبت شد و در حال ارسال است.",
            "users": len(users)}
