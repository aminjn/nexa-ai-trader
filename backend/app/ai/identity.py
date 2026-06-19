"""احراز هویت با هوش مصنوعی (مدل‌های گپ‌جی‌پی‌تی، vision).

تصویر کارت ملی و سلفی کاربر را به مدل می‌دهد و تطابق چهره را می‌سنجد.
خروجی: {match: bool, confidence: 0..100, reason: str, card_name: str}
"""
import json
import re
from .gapgpt import make_client, get_ai_config

_PROMPT = (
    "تو سامانهٔ احراز هویت هستی. دو تصویر دریافت می‌کنی: تصویر اول «کارت ملی» و تصویر دوم «سلفی/عکس زندهٔ کاربر». "
    "وظایف:\n"
    "1) بررسی کن آیا چهرهٔ روی کارت ملی با چهرهٔ سلفی متعلق به یک شخص است.\n"
    "2) بررسی کن تصویر اول واقعاً یک کارت ملی/مدرک شناسایی معتبر به نظر می‌رسد و سلفی یک چهرهٔ انسانی واقعی است (نه عکسِ عکس).\n"
    "فقط و فقط یک JSON معتبر برگردان، بدون هیچ متن اضافه، با این کلیدها:\n"
    '{"match": true/false, "confidence": عددی بین 0 تا 100, "is_id_card": true/false, '
    '"is_real_selfie": true/false, "reason": "توضیح کوتاه فارسی"}'
)


async def verify_identity(card_image: str, selfie_image: str, db=None) -> dict:
    """مقایسهٔ چهرهٔ کارت ملی با سلفی. card_image/selfie_image به‌صورت data-uri base64.

    در صورت خطا، نتیجهٔ خنثی برمی‌گرداند تا جریان قطع نشود (ادمین دستی بررسی کند).
    """
    cfg = get_ai_config(db)
    client = make_client(cfg["api_key"], timeout=90.0)
    try:
        resp = await client.chat.completions.create(
            model=cfg["model"],
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT},
                    {"type": "image_url", "image_url": {"url": card_image}},
                    {"type": "image_url", "image_url": {"url": selfie_image}},
                ],
            }],
            temperature=0,
            max_tokens=400,
        )
        raw = resp.choices[0].message.content or ""
    except Exception as e:
        return {"match": False, "confidence": 0, "is_id_card": False, "is_real_selfie": False,
                "reason": f"خطا در تماس با هوش مصنوعی: {str(e)[:120]}", "error": True}

    data = _parse_json(raw)
    if data is None:
        return {"match": False, "confidence": 0, "is_id_card": False, "is_real_selfie": False,
                "reason": "پاسخ هوش مصنوعی قابل‌خواندن نبود — بررسی دستی لازم است", "error": True}
    # نرمال‌سازی
    return {
        "match": bool(data.get("match")),
        "confidence": float(data.get("confidence", 0) or 0),
        "is_id_card": bool(data.get("is_id_card", True)),
        "is_real_selfie": bool(data.get("is_real_selfie", True)),
        "reason": str(data.get("reason", ""))[:400],
        "error": False,
    }


def _parse_json(text: str):
    text = text.strip()
    # حذف ```json ... ```
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
    return None


# آستانهٔ تأیید خودکار (درصد اطمینان تطابق)
AUTO_VERIFY_THRESHOLD = 80.0
