"""اتصال خودکار ربات با long-polling (بدون نیاز به وب‌هوک/SSL).

کاربر در ربات می‌زند:  /start <CODE>
ربات شناسه‌ی چت او را به کاربری که آن CODE را دارد وصل می‌کند.
- تلگرام: getUpdates از طریق پروکسی (در ایران مسدود است)
- بله: getUpdates مستقیم
"""
import asyncio
import httpx
from .. import models
from ..database import SessionLocal
from ..config import settings


async def _api(base: str, method: str, use_proxy: bool, **params):
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    async with httpx.AsyncClient(timeout=40, proxy=proxy, trust_env=False) as c:
        r = await c.get(f"{base}/{method}", params=params)
        return r.json()


def _link(chat_id: str, code: str, platform: str) -> str:
    """کد را به کاربر وصل می‌کند و پیام پاسخ مناسب برمی‌گرداند."""
    db = SessionLocal()
    try:
        code = (code or "").strip()
        if not code:
            return ("به NEXA AI خوش آمدی! 👋\n"
                    "برای اتصال حسابت، از پنل کد اتصال را بگیر و این‌طور بفرست:\n/start کد_شما")
        user = db.query(models.User).filter(models.User.link_code == code).first()
        if not user:
            return "کد اتصال نامعتبر است. از پنل NEXA کد درست را بگیر و دوباره امتحان کن."
        if platform == "telegram":
            user.telegram_chat_id = str(chat_id)
        else:
            user.bale_chat_id = str(chat_id)
        db.commit()
        return f"✅ حساب شما با موفقیت وصل شد، {user.full_name or 'کاربر'} عزیز!\nاز این پس سیگنال‌ها همین‌جا برایت ارسال می‌شود."
    except Exception:
        db.rollback()
        return "خطا در اتصال. کمی بعد دوباره امتحان کن."
    finally:
        db.close()


def _get_token(field: str) -> str:
    db = SessionLocal()
    try:
        s = db.query(models.SystemSettings).first()
        return (getattr(s, field, "") or "") if s else ""
    finally:
        db.close()


async def _poll_loop(platform: str, base_fn, token_field: str, use_proxy: bool):
    offset = 0
    initialized = False
    while True:
        token = _get_token(token_field)
        if not token:
            await asyncio.sleep(20)
            continue
        base = base_fn(token)
        try:
            # نخستین بار: وب‌هوک را پاک و فقط offset را همگام کن (پیام‌های قدیمی را پردازش نکن)
            if not initialized:
                try:
                    await _api(base, "deleteWebhook", use_proxy)
                except Exception:
                    pass
                data = await _api(base, "getUpdates", use_proxy, timeout=0)
                for u in data.get("result", []):
                    offset = max(offset, u.get("update_id", 0) + 1)
                initialized = True

            data = await _api(base, "getUpdates", use_proxy, offset=offset, timeout=30)
            for u in data.get("result", []):
                offset = max(offset, u.get("update_id", 0) + 1)
                msg = u.get("message") or u.get("edited_message") or {}
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                if text.startswith("/start"):
                    parts = text.split(maxsplit=1)
                    code = parts[1] if len(parts) > 1 else ""
                    reply = _link(str(chat_id), code, platform)
                    try:
                        await _api(base, "sendMessage", use_proxy, chat_id=chat_id, text=reply)
                    except Exception:
                        pass
        except Exception:
            await asyncio.sleep(10)
            continue


async def telegram_poll_loop():
    await _poll_loop(
        "telegram",
        lambda t: f"https://api.telegram.org/bot{t}",
        "telegram_bot_token",
        use_proxy=True,
    )


async def bale_poll_loop():
    await _poll_loop(
        "bale",
        lambda t: f"https://tapi.bale.ai/bot{t}",
        "bale_bot_token",
        use_proxy=False,
    )
