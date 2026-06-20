"""استراتژیِ زندهٔ بات که سیستمِ خودبهینه‌ساز به‌طور خودکار انتخاب و اعمال می‌کند.

هیچ دکمه‌ای لازم نیست: بهینه‌ساز در پس‌زمینه چند ده ترکیب را بک‌تست می‌کند،
سوددهترین ترکیبِ پس از کمیسیون را برمی‌گزیند و اینجا می‌نویسد؛ بات هر چرخه
آن را می‌خواند. اگر هیچ ترکیبِ سودده‌ای نباشد، active=False می‌ماند و بات
معاملهٔ واقعی باز نمی‌کند.
"""
import json
import os
from datetime import datetime

STRATEGY_PATH = "bot_strategy.json"

_DEFAULT = {"active": False, "mode": "—", "invert": False, "threshold": 0.62,
            "tp_pct": 3.0, "sl_pct": 2.0, "horizon_h": 72,
            "expectancy_pct": None, "profit_factor": None, "trades": 0,
            "updated_at": None}


def get_strategy() -> dict:
    if os.path.exists(STRATEGY_PATH):
        try:
            with open(STRATEGY_PATH, "r", encoding="utf-8") as f:
                d = json.load(f)
                return {**_DEFAULT, **d}
        except Exception:
            pass
    return dict(_DEFAULT)


def set_strategy(d: dict):
    out = dict(_DEFAULT)
    out.update(d)
    out["updated_at"] = datetime.utcnow().isoformat()
    try:
        with open(STRATEGY_PATH, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False)
    except Exception:
        pass
    return out
