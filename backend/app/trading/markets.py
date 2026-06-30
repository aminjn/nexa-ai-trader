"""کشفِ خودکارِ بازارهای نوبیتکس (با کش).

لیستِ همهٔ ارزهای فعالِ نوبیتکس را پویا می‌گیرد تا ارزِ جدیدی که نوبیتکس اضافه
می‌کند، خودکار وارد ربات شود. هر ۶ ساعت یک‌بار تازه می‌شود.
"""
import time

# کش ماژولی
_cache = {"ts": 0.0, "coins": []}
_TTL = 6 * 3600   # هر ۶ ساعت → ارزِ جدید حداکثر ظرف ۶ ساعت خودکار اضافه می‌شود

# پشتیبان اگر API در دسترس نبود (همان لیستِ پایدارِ قبلی)
_FALLBACK = [
    "BTC", "ETH", "XRP", "ADA", "DOGE", "LTC", "TRX", "BCH", "BNB", "SOL",
    "DOT", "AVAX", "MATIC", "SHIB", "LINK", "UNI", "ATOM", "FIL", "ETC", "XLM", "AAVE",
]

_ALL_TOKENS = {"ALL", "*", "همه", "همه‌ارزها", "همه ارزها", "AUTO", "خودکار"}

# پیش‌فرض‌های قدیمی که عملاً «همه ارزها» منظور بوده — این‌ها هم به‌صورت همه تفسیر می‌شوند
_LEGACY_DEFAULTS = {
    "BTC,ETH",
    "BTC,ETH,XRP,ADA,DOGE,LTC,TRX,BCH,BNB,SOL,DOT,AVAX,MATIC,SHIB,LINK,UNI,ATOM,FIL,ETC,XLM",
}


def is_all(coins_raw: str) -> bool:
    """آیا تنظیمِ کاربر یعنی «همهٔ ارزها به‌صورت خودکار»؟"""
    return (coins_raw or "").strip().upper() in {t.upper() for t in _ALL_TOKENS}


def wants_all(coins_raw: str) -> bool:
    """آیا باید همهٔ ارزها پوشش داده شوند؟ (خالی، «همه»، یا پیش‌فرضِ قدیمی)"""
    s = (coins_raw or "").strip()
    if not s or is_all(s):
        return True
    return s.upper() in {d.upper() for d in _LEGACY_DEFAULTS}


async def get_all_nobitex_coins(quote: str = "IRT") -> list:
    """لیستِ کش‌شدهٔ همهٔ ارزهای فعالِ نوبیتکس (با fallback)."""
    now = time.time()
    if _cache["coins"] and (now - _cache["ts"] < _TTL):
        return _cache["coins"]
    coins = []
    try:
        from ..exchanges.nobitex import NobitexExchange
        ex = NobitexExchange(api_key="")   # دادهٔ عمومی، توکن لازم نیست
        coins = await ex.get_all_markets(quote)
    except Exception:
        coins = []
    if not coins:
        # اگر گرفتن نشد، کشِ قبلی یا fallback
        return _cache["coins"] or list(_FALLBACK)
    _cache["coins"] = coins
    _cache["ts"] = now
    return coins
