"""ارسال پیامک کد تأیید (OTP) با سرویس آی‌پی‌پنل (IPPanel — Edge API).

مستندات: https://github.com/ippanelcom/Edge-Document
- Base URL: https://edge.ippanel.com/v1
- ارسال با الگو: POST /api/send  (sending_type=pattern)
- هدر احراز هویت: Authorization: <token>

آی‌پی‌پنل سرویس ایرانی است → اتصال مستقیم (بدون پروکسی).
تنظیمات (توکن/کد الگو/شمارهٔ فرستنده) از جدول SystemSettings خوانده می‌شود
تا از پنل قابل ویرایش باشد.
"""
import httpx
from .. import models

BASE_URL = "https://edge.ippanel.com/v1"


def normalize_phone(phone: str) -> str:
    """شمارهٔ موبایل ایران را به فرمت E.164 (+98...) تبدیل می‌کند."""
    p = (phone or "").strip().replace(" ", "").replace("-", "")
    if p.startswith("+"):
        return p
    if p.startswith("0098"):
        return "+" + p[2:]
    if p.startswith("98"):
        return "+" + p
    if p.startswith("0"):
        return "+98" + p[1:]
    return "+98" + p


async def send_otp_sms(phone: str, code: str, db) -> tuple[bool, str]:
    """کد تأیید را با الگوی آی‌پی‌پنل پیامک می‌کند. (موفقیت, پیام/خطا) را برمی‌گرداند."""
    s = db.query(models.SystemSettings).first()
    if not s or not s.sms_login_enabled:
        return False, "sms_disabled"
    token = (s.ippanel_token or "").strip()
    pattern = (s.ippanel_pattern_code or "").strip()
    sender = (s.ippanel_from_number or "").strip()
    if not (token and pattern and sender):
        return False, "not_configured"
    param = (s.ippanel_param_name or "code").strip() or "code"

    payload = {
        "sending_type": "pattern",
        "from_number": sender,
        "code": pattern,
        "recipients": [normalize_phone(phone)],
        "params": {param: str(code)},
    }
    headers = {"Authorization": token, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as c:
            r = await c.post(f"{BASE_URL}/api/send", json=payload, headers=headers)
            try:
                data = r.json()
            except Exception:
                return False, f"http {r.status_code}: {r.text[:150]}"
            meta = data.get("meta") or {}
            if meta.get("status"):
                return True, "ok"
            return False, str(meta.get("message") or data)[:200]
    except Exception as e:
        return False, str(e)[:200]
