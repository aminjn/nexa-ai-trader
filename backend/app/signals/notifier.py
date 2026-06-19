"""ارسال پیام به تلگرام و بله (Bale).

هر دو API بسیار شبیه هم هستند:
- تلگرام:  https://api.telegram.org/bot<token>/sendMessage
- بله:     https://tapi.bale.ai/bot<token>/sendMessage
ارسال تلگرام از طریق پروکسی انجام می‌شود (در ایران مسدود است)؛ بله مستقیم.
"""
import re
import httpx
from ..config import settings


def _strip_html(text: str) -> str:
    """تگ‌های HTML را حذف می‌کند (بله HTML را رندر نمی‌کند و خام نشان می‌دهد)."""
    return re.sub(r"</?[^>]+>", "", text or "")


async def _post(url: str, chat_id: str, text: str, use_proxy: bool, platform: str = "", html: bool = True) -> bool:
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if html:
        payload["parse_mode"] = "HTML"
    try:
        async with httpx.AsyncClient(timeout=15, proxy=proxy, trust_env=False) as c:
            r = await c.post(url, json=payload)
            data = r.json()
            if not data.get("ok"):
                print(f"⚠️ {platform} send failed (chat={chat_id}): {str(data)[:300]}")
            return bool(data.get("ok"))
    except Exception as e:
        print(f"⚠️ {platform} send error (chat={chat_id}): {str(e)[:200]}")
        return False


async def send_telegram(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    # تلگرام در ایران فیلتر است → از طریق پروکسی؛ HTML را پشتیبانی می‌کند
    return await _post(f"https://api.telegram.org/bot{token}/sendMessage", chat_id, text, use_proxy=True, platform="telegram", html=True)


async def send_bale(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    # بله HTML را رندر نمی‌کند → تگ‌ها حذف و متن ساده فرستاده می‌شود. (از پروکسی)
    return await _post(f"https://tapi.bale.ai/bot{token}/sendMessage", chat_id, _strip_html(text), use_proxy=True, platform="bale", html=False)
