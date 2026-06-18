"""تحلیل فاندامنتال بازار با کمک هوش مصنوعی.

ML جهت معامله را تصمیم می‌گیرد؛ این ماژول یک «امتیاز احساسات فاندامنتال»
(بین -۱ تا +۱) تولید می‌کند که اطمینان مدل ML را تقویت یا تضعیف می‌کند.
داده‌های واقعی (روند دلار/تتر در ایران و بیت‌کوین) به هوش مصنوعی داده می‌شود.
"""
import time
import json
import re
from typing import Optional
from .gapgpt import get_ai_response, get_ai_config

# کش برای جلوگیری از فراخوانی مکرر هوش مصنوعی
_cache = {"ts": 0.0, "data": None}
_TTL = 1800  # هر ۳۰ دقیقه به‌روزرسانی


def _change_pct(ohlcv, n: int) -> float:
    try:
        closes = [row[4] for row in ohlcv]
        if len(closes) > n:
            old = closes[-1 - n]
            return round((closes[-1] - old) / old * 100, 2) if old else 0.0
    except Exception:
        pass
    return 0.0


async def get_fundamental(db, exchange, force: bool = False) -> dict:
    """امتیاز و خلاصه تحلیل فاندامنتال را برمی‌گرداند (با کش)."""
    now = time.time()
    if not force and _cache["data"] and (now - _cache["ts"] < _TTL):
        return _cache["data"]

    data = {"score": 0.0, "summary": "", "usd_trend_7d": 0.0, "btc_trend_7d": 0.0, "btc_trend_30d": 0.0}
    try:
        usdt = await exchange.get_ohlcv("USDT/RLS", "1d", 40)   # دلار/تتر به تومان (شاخص دلار در ایران)
        btc = await exchange.get_ohlcv("BTC/USDT", "1d", 40)
        data["usd_trend_7d"] = _change_pct(usdt, 7)
        data["btc_trend_7d"] = _change_pct(btc, 7)
        data["btc_trend_30d"] = _change_pct(btc, 30)

        # داده‌های اسکرپ‌شده از سایت‌های انتخابی کاربر
        scraped = ""
        try:
            from ..scraping.scraper import collect_scraped_context
            scraped = collect_scraped_context(db)
        except Exception:
            scraped = ""

        if get_ai_config(db)["api_key"]:
            news_section = f"\n\nاخبار و داده‌های اسکرپ‌شده از منابع:\n{scraped}\n" if scraped else ""
            prompt = (
                "تو یک تحلیلگر فاندامنتال بازار رمزارز هستی. این داده‌های واقعی را تحلیل کن:\n"
                f"- تغییر قیمت دلار (تتر به تومان) در ۷ روز اخیر: {data['usd_trend_7d']}%\n"
                f"- تغییر قیمت بیت‌کوین در ۷ روز اخیر: {data['btc_trend_7d']}%\n"
                f"- تغییر قیمت بیت‌کوین در ۳۰ روز اخیر: {data['btc_trend_30d']}%"
                f"{news_section}\n"
                "با توجه به این داده‌ها، اخبار بالا، شرایط کلی اقتصادی ایران (روند دلار)، و دانش فاندامنتال‌ات "
                "از بازار کریپتو، یک «امتیاز احساسات بازار» بین -۱ (بسیار نزولی) تا +۱ (بسیار صعودی) بده.\n"
                "فقط به این صورت JSON پاسخ بده (بدون هیچ متن اضافه):\n"
                '{"score": 0.3, "summary": "خلاصه تحلیل فارسی در یک یا دو جمله"}'
            )
            resp = await get_ai_response([{"role": "user", "content": prompt}], db=db)
            m = re.search(r"\{.*\}", resp or "", re.DOTALL)
            if m:
                parsed = json.loads(m.group())
                data["score"] = max(-1.0, min(1.0, float(parsed.get("score", 0))))
                data["summary"] = str(parsed.get("summary", ""))[:500]
    except Exception:
        pass

    _cache["ts"] = now
    _cache["data"] = data
    return data


def get_cached_fundamental() -> Optional[dict]:
    return _cache["data"]
