"""کمک‌توابع ساخت نوتیفیکیشن."""
from . import models


def notify_admin(db, type_: str, title: str, message: str, ref_user_id=None, link=""):
    """نوتیف برای سوپر ادمین‌ها."""
    n = models.Notification(for_admin=True, type=type_, title=title, message=message,
                            ref_user_id=ref_user_id, link=link)
    db.add(n)
    db.commit()
    return n


def notify_user(db, user_id: int, type_: str, title: str, message: str, link=""):
    """نوتیف برای یک کاربر (داخل اپ + Web Push روی گوشی)."""
    n = models.Notification(for_admin=False, user_id=user_id, type=type_, title=title,
                            message=message, link=link)
    db.add(n)
    db.commit()
    # تلاش برای پوشِ دستگاه (بهترین‌تلاش)
    try:
        from .push_web import push_to_users
        push_to_users(db, [user_id], title, message, link or "/notifications")
    except Exception:
        pass
    return n
