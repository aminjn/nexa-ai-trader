"""Web Push (VAPID) — ارسال پوشِ واقعی به مرورگر/PWA حتی وقتی اپ بسته است.

روی iOS (PWA نصب‌شده، نسخهٔ ۱۶.۴+) از Apple Push استفاده می‌شود که در ایران در دسترس است.
کلیدهای VAPID یک‌بار ساخته و در SystemSettings ذخیره می‌شوند.
"""
import json
import base64
from . import models


def ensure_vapid_keys(db) -> tuple:
    """کلیدهای VAPID را برمی‌گرداند؛ اگر نبود، یک‌بار می‌سازد و ذخیره می‌کند.

    خروجی: (public_application_server_key_base64url, private_pem)
    """
    s = db.query(models.SystemSettings).first()
    if not s:
        return "", ""
    if (s.vapid_public_key or "").strip() and (s.vapid_private_key or "").strip():
        return s.vapid_public_key, s.vapid_private_key
    try:
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization
        priv = ec.generate_private_key(ec.SECP256R1())
        pem = priv.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()).decode()
        pub_point = priv.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        app_key = base64.urlsafe_b64encode(pub_point).rstrip(b"=").decode()
        s.vapid_public_key = app_key
        s.vapid_private_key = pem
        db.commit()
        return app_key, pem
    except Exception as e:
        print(f"⚠️ VAPID key generation failed: {e}")
        return "", ""


def send_web_push(db, sub: "models.PushSubscription", title: str, body: str, url: str = "/notifications") -> bool:
    """یک پیام پوش به یک اشتراک می‌فرستد. در صورت منقضی‌بودن (404/410) آن را حذف می‌کند."""
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        return False  # کتابخانه نصب نیست
    _, priv_pem = ensure_vapid_keys(db)
    if not priv_pem:
        return False
    s = db.query(models.SystemSettings).first()
    claim_email = (getattr(s, "support_contact", "") or "").strip()
    if not claim_email.startswith("mailto:"):
        claim_email = "mailto:admin@nexa.ai"
    info = {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}
    payload = json.dumps({"title": title, "body": body, "url": url})
    try:
        webpush(subscription_info=info, data=payload,
                vapid_private_key=priv_pem, vapid_claims={"sub": claim_email}, timeout=10)
        return True
    except Exception as e:
        msg = str(e)
        if "410" in msg or "404" in msg:
            try:
                db.delete(sub)
                db.commit()
            except Exception:
                db.rollback()
        return False


def push_to_users(db, user_ids, title: str, body: str, url: str = "/notifications") -> int:
    """به همهٔ اشتراک‌های پوشِ کاربرانِ داده‌شده پیام می‌فرستد. تعداد موفق را برمی‌گرداند."""
    q = db.query(models.PushSubscription)
    if user_ids:
        q = q.filter(models.PushSubscription.user_id.in_(list(user_ids)))
    sent = 0
    for sub in q.all():
        if send_web_push(db, sub, title, body, url):
            sent += 1
    return sent
