"""API نوتیفیکیشن‌ها (کاربر و سوپر ادمین)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from .. import models
from ..database import get_db
from ..auth.router import get_current_user

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
