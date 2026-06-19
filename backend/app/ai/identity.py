"""احراز هویت با هوش مصنوعی (مدل‌های گپ‌جی‌پی‌تی، vision).

تصویر کارت ملی و سلفی کاربر را به مدل می‌دهد و تطابق چهره را می‌سنجد.
خروجی: {match: bool, confidence: 0..100, reason: str, card_name: str}
"""
import json
import re
from .gapgpt import make_client, get_ai_config

_PROMPT = (
    "تو سامانهٔ احراز هویت هستی. تصویر اول «کارت ملی» است و بقیهٔ تصاویر «فریم‌هایی از ویدئوی زندهٔ کاربر» "
    "هستند که هنگام گفتن یک عبارت گرفته شده‌اند. وظایف:\n"
    "1) آیا چهرهٔ روی کارت ملی با چهرهٔ فریم‌های ویدئو متعلق به یک شخص است؟\n"
    "2) آیا تصویر اول یک کارت ملی/مدرک شناسایی معتبر به نظر می‌رسد؟\n"
    "3) آیا فریم‌ها یک انسانِ واقعی و زنده را نشان می‌دهند (نه عکسِ عکس یا تصویر ثابت)؟ "
    "به تفاوت‌های جزئیِ حالت چهره بین فریم‌ها توجه کن.\n"
    "فقط و فقط یک JSON معتبر برگردان، بدون هیچ متن اضافه:\n"
    '{"match": true/false, "confidence": عددی بین 0 تا 100, "is_id_card": true/false, '
    '"is_real_selfie": true/false, "reason": "توضیح کوتاه فارسی"}'
)


async def verify_identity(card_image: str, frames, db=None) -> dict:
    """مقایسهٔ چهرهٔ کارت ملی با فریم‌های ویدئوی زنده.

    frames: یک رشتهٔ data-uri یا فهرستی از data-uriها (فریم‌های استخراج‌شده از ویدئو).
    در صورت خطا، نتیجهٔ خنثی برمی‌گرداند تا جریان قطع نشود (ادمین دستی بررسی کند).
    """
    if isinstance(frames, str):
        frames = [frames]
    frames = [f for f in (frames or []) if f][:4]  # حداکثر ۴ فریم
    if not frames:
        return {"match": False, "confidence": 0, "is_id_card": False, "is_real_selfie": False,
                "reason": "فریمی از ویدئو دریافت نشد", "error": True}
    cfg = get_ai_config(db)
    client = make_client(cfg["api_key"], timeout=45.0)
    content = [{"type": "text", "text": _PROMPT},
               {"type": "image_url", "image_url": {"url": card_image}}]
    for fr in frames:
        content.append({"type": "image_url", "image_url": {"url": fr}})
    try:
        resp = await client.chat.completions.create(
            model=cfg["model"],
            messages=[{"role": "user", "content": content}],
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


FA_NUM_WORDS = ['صفر', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']


async def transcribe_audio(video_data_uri: str, db=None) -> str:
    """رونویسی صدای ویدئوی KYC با whisper (مدل‌های گپ). در خطا رشتهٔ خالی برمی‌گرداند."""
    if not video_data_uri or "," not in video_data_uri:
        return ""
    import base64
    try:
        header, b64 = video_data_uri.split(",", 1)
        raw = base64.b64decode(b64)
    except Exception:
        return ""
    ext = "webm"
    if "mp4" in header:
        ext = "mp4"
    cfg = get_ai_config(db)
    client = make_client(cfg["api_key"], timeout=45.0)
    try:
        resp = await client.audio.transcriptions.create(
            model="whisper-1",
            file=(f"kyc.{ext}", raw),
            language="fa",
        )
        return (getattr(resp, "text", "") or "").strip()
    except Exception:
        return ""


def _normalize_fa(s: str) -> str:
    """نرمال‌سازی متن فارسی + تبدیل ارقام فارسی/عربی به انگلیسی."""
    fa = "۰۱۲۳۴۵۶۷۸۹"; ar = "٠١٢٣٤٥٦٧٨٩"
    out = []
    for ch in s:
        if ch in fa:
            out.append(str(fa.index(ch)))
        elif ch in ar:
            out.append(str(ar.index(ch)))
        else:
            out.append(ch)
    return "".join(out)


def check_spoken(transcript: str, challenge_text: str) -> dict:
    """بررسی این‌که اعداد چالش در گفتار کاربر آمده‌اند.

    challenge_text مثل: «۳ (سه) - ۷ (هفت) - ...». انتظار: همان رقم‌ها (به‌صورت عدد یا واژهٔ فارسی).
    """
    import re
    if not transcript:
        return {"ok": False, "matched": 0, "expected": 0, "transcript": ""}
    # رقم‌های موردانتظار را از متن چالش دربیاور
    norm_ch = _normalize_fa(challenge_text)
    expected_digits = re.findall(r"\d", norm_ch)
    if not expected_digits:
        return {"ok": False, "matched": 0, "expected": 0, "transcript": transcript}
    norm_tr = _normalize_fa(transcript)
    matched = 0
    for d in expected_digits:
        word = FA_NUM_WORDS[int(d)]
        if d in norm_tr or word in transcript:
            matched += 1
    expected = len(expected_digits)
    return {"ok": matched >= max(2, expected - 1), "matched": matched,
            "expected": expected, "transcript": transcript[:200]}


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
