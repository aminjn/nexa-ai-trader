"""ارسال پیام به تلگرام و بله (Bale).

هر دو API بسیار شبیه هم هستند:
- تلگرام:  https://api.telegram.org/bot<token>/sendMessage
- بله:     https://tapi.bale.ai/bot<token>/sendMessage
ارسال تلگرام از طریق پروکسی انجام می‌شود (در ایران مسدود است)؛ بله مستقیم.
"""
import httpx
from ..config import settings


async def _post(url: str, chat_id: str, text: str, use_proxy: bool, platform: str = "") -> bool:
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    try:
        async with httpx.AsyncClient(timeout=15, proxy=proxy, trust_env=False) as c:
            r = await c.post(url, json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            })
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
    # تلگرام در ایران فیلتر است → از طریق پروکسی
    return await _post(f"https://api.telegram.org/bot{token}/sendMessage", chat_id, text, use_proxy=True, platform="telegram")


async def send_bale(token: str, chat_id: str, text: str) -> bool:
    if not token or not chat_id:
        return False
    # بله داخلی است → مستقیم
    return await _post(f"https://tapi.bale.ai/bot{token}/sendMessage", chat_id, text, use_proxy=False, platform="bale")
