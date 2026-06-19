"""ارسال پیام به تلگرام و بله (Bale).

هر دو API بسیار شبیه هم هستند:
- تلگرام:  https://api.telegram.org/bot<token>/sendMessage
- بله:     https://tapi.bale.ai/bot<token>/sendMessage
ارسال هر دو از طریق پروکسی انجام می‌شود (در ایران مسدود/محدودند).
"""
import re
import httpx
from ..config import settings


def _strip_html(text: str) -> str:
    """تگ‌های HTML را حذف می‌کند (بله HTML را رندر نمی‌کند و خام نشان می‌دهد)."""
    return re.sub(r"</?[^>]+>", "", text or "")


async def _post(url: str, chat_id: str, text: str, use_proxy: bool, platform: str = "",
                html: bool = True, reply_markup: dict | None = None):
    """پیام را می‌فرستد و در صورت موفقیت، دادهٔ پاسخ (شامل message_id) را برمی‌گرداند؛ وگرنه None."""
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if html:
        payload["parse_mode"] = "HTML"
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        async with httpx.AsyncClient(timeout=15, proxy=proxy, trust_env=False) as c:
            r = await c.post(url, json=payload)
            data = r.json()
            if not data.get("ok"):
                print(f"⚠️ {platform} send failed (chat={chat_id}): {str(data)[:300]}")
                return None
            return data.get("result")
    except Exception as e:
        print(f"⚠️ {platform} send error (chat={chat_id}): {str(e)[:200]}")
        return None


async def send_telegram(token: str, chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    if not token or not chat_id:
        return False
    res = await _post(f"https://api.telegram.org/bot{token}/sendMessage", chat_id, text,
                      use_proxy=True, platform="telegram", html=True, reply_markup=reply_markup)
    return res is not None


async def send_telegram_post(token: str, chat_id: str, text: str, reply_markup: dict | None = None):
    """مثل send_telegram ولی message_id پیام ارسالی را برمی‌گرداند (برای واکنش‌ها)."""
    if not token or not chat_id:
        return None
    res = await _post(f"https://api.telegram.org/bot{token}/sendMessage", chat_id, text,
                      use_proxy=True, platform="telegram", html=True, reply_markup=reply_markup)
    return (res or {}).get("message_id") if res else None


async def send_bale(token: str, chat_id: str, text: str, reply_markup: dict | None = None) -> bool:
    if not token or not chat_id:
        return False
    # بله HTML را رندر نمی‌کند → تگ‌ها حذف و متن ساده فرستاده می‌شود. (از پروکسی)
    res = await _post(f"https://tapi.bale.ai/bot{token}/sendMessage", chat_id, _strip_html(text),
                      use_proxy=True, platform="bale", html=False, reply_markup=reply_markup)
    return res is not None


async def send_bale_post(token: str, chat_id: str, text: str, reply_markup: dict | None = None):
    if not token or not chat_id:
        return None
    res = await _post(f"https://tapi.bale.ai/bot{token}/sendMessage", chat_id, _strip_html(text),
                      use_proxy=True, platform="bale", html=False, reply_markup=reply_markup)
    return (res or {}).get("message_id") if res else None


async def edit_markup(base: str, chat_id, message_id, reply_markup: dict, use_proxy: bool = True):
    """فقط دکمه‌های یک پیام را به‌روزرسانی می‌کند (برای شمارندهٔ واکنش‌ها)."""
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    try:
        async with httpx.AsyncClient(timeout=15, proxy=proxy, trust_env=False) as c:
            await c.post(f"{base}/editMessageReplyMarkup",
                         json={"chat_id": chat_id, "message_id": message_id, "reply_markup": reply_markup})
    except Exception as e:
        print(f"⚠️ edit_markup error: {str(e)[:150]}")


async def answer_callback(base: str, callback_id: str, text: str = "", use_proxy: bool = True):
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    try:
        async with httpx.AsyncClient(timeout=10, proxy=proxy, trust_env=False) as c:
            await c.post(f"{base}/answerCallbackQuery",
                         json={"callback_query_id": callback_id, "text": text})
    except Exception:
        pass
