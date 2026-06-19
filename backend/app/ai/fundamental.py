"""تحلیل فاندامنتال بازار با کمک هوش مصنوعی.

ML جهت معامله را تصمیم می‌گیرد؛ این ماژول یک «امتیاز احساسات فاندامنتال»
(بین -۱ تا +۱) تولید می‌کند که اطمینان مدل ML را تقویت یا تضعیف می‌کند.
داده‌های واقعی (روند دلار/تتر در ایران و بیت‌کوین) به هوش مصنوعی داده می‌شود.
"""
import time
import asyncio
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


def _rule_based(usd7: float, btc7: float, btc30: float) -> dict:
    """امتیاز و خلاصه فاندامنتال بر پایه‌ی قواعد (بدون نیاز به هوش مصنوعی).

    این به‌عنوان پایه همیشه محاسبه می‌شود تا تحلیل هیچ‌وقت خالی نماند.
    """
    # امتیاز بیت‌کوین: روند ۷روزه وزن بیشتر، ۳۰روزه وزن کمتر
    btc_score = max(-1.0, min(1.0, (btc7 / 10.0) * 0.7 + (btc30 / 25.0) * 0.3))
    # دلار صعودی در ایران معمولاً به نفع قیمت ریالی رمزارزهاست (پوشش تورمی)
    usd_score = max(-0.5, min(0.5, usd7 / 15.0))
    score = round(max(-1.0, min(1.0, btc_score * 0.75 + usd_score * 0.25)), 2)

    def _word(v, up="صعودی", down="نزولی", flat="کم‌نوسان"):
        if v > 1:
            return up
        if v < -1:
            return down
        return flat

    parts = [
        f"روند بیت‌کوین در ۷ روز اخیر {btc7:+.1f}٪ ({_word(btc7)}) و در ۳۰ روز اخیر {btc30:+.1f}٪ ({_word(btc30)}) بوده است.",
        f"قیمت دلار (تتر به تومان) در ۷ روز اخیر {usd7:+.1f}٪ تغییر کرده ({_word(usd7)}).",
    ]
    if score > 0.25:
        parts.append("جمع‌بندی: شرایط فاندامنتال نسبتاً صعودی است و از خرید پشتیبانی می‌کند.")
    elif score < -0.25:
        parts.append("جمع‌بندی: شرایط فاندامنتال نسبتاً نزولی است و احتیاط در خرید توصیه می‌شود.")
    else:
        parts.append("جمع‌بندی: شرایط فاندامنتال خنثی است و سیگنال قوی فاندامنتالی دیده نمی‌شود.")
    return {"score": score, "summary": " ".join(parts)}


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

        # پایه‌ی قاعده‌محور: همیشه محاسبه می‌شود تا تحلیل هرگز خالی نماند
        base = _rule_based(data["usd_trend_7d"], data["btc_trend_7d"], data["btc_trend_30d"])
        data["score"] = base["score"]
        data["summary"] = base["summary"]

        # داده‌های اسکرپ‌شده از سایت‌های انتخابی کاربر
        scraped = ""
        try:
            from ..scraping.scraper import collect_scraped_context
            scraped = collect_scraped_context(db)
        except Exception:
            scraped = ""

        if get_ai_config(db)["api_key"]:
            news_section = f"\n\nمهم‌ترین اخبار اخیر (از منابع):\n{scraped[:2500]}\n" if scraped else ""
            prompt = (
                "تو تحلیلگر فاندامنتال بازار رمزارز هستی. بر اساس داده‌ها و اخبار زیر، یک تحلیل "
                "کوتاه و روانِ فارسی در ۳ تا ۵ جمله بنویس که هم روند قیمت‌ها و هم مهم‌ترین خبرها را پوشش دهد "
                "و در پایان یک جمع‌بندی (صعودی/نزولی/خنثی) بدهد. اخبار انگلیسی را به فارسی بیاور. "
                "فقط متن تحلیل را بنویس، بدون مقدمه و بدون JSON.\n\n"
                f"- روند دلار (تتر به تومان) ۷روزه: {data['usd_trend_7d']}٪\n"
                f"- روند بیت‌کوین ۷روزه: {data['btc_trend_7d']}٪ | ۳۰روزه: {data['btc_trend_30d']}٪"
                f"{news_section}"
            )
            try:
                resp = await asyncio.wait_for(
                    get_ai_response([{"role": "user", "content": prompt}], db=db), timeout=45)
                if resp and len(resp.strip()) > 40:
                    # امتیاز عددی از قاعده‌محور می‌ماند (برای ربات)، ولی متن تحلیل از هوش مصنوعی
                    data["summary"] = resp.strip()[:1200]
            except Exception:
                pass  # در صورت خطا/تایم‌اوت، خلاصه‌ی قاعده‌محور باقی می‌ماند
    except Exception:
        pass

    # تضمین نهایی: اگر به هر دلیلی خلاصه خالی ماند، پایه‌ی قاعده‌محور را بگذار
    if not data.get("summary"):
        base = _rule_based(data["usd_trend_7d"], data["btc_trend_7d"], data["btc_trend_30d"])
        data["score"] = base["score"]
        data["summary"] = base["summary"]

    _cache["ts"] = now
    _cache["data"] = data
    return data


def get_cached_fundamental() -> Optional[dict]:
    return _cache["data"]
