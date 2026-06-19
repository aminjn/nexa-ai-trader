"""محافظِ سوددهی: جلوگیری از بازکردنِ معاملهٔ واقعی وقتی آخرین بک‌تست ضرده بوده.

بک‌تست هنگام اجرا، انتظارِ سود (expectancy) را اینجا ثبت می‌کند. بات پیش از هر ورود
آن را می‌خواند؛ اگر منفی باشد و سوپر ادمین override نکرده باشد، معاملهٔ واقعی باز نمی‌شود.
"""
import json
import os
from datetime import datetime

GUARD_PATH = "bot_guard.json"


def _read() -> dict:
    if os.path.exists(GUARD_PATH):
        try:
            with open(GUARD_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write(d: dict):
    try:
        with open(GUARD_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


def set_expectancy(expectancy_pct: float, trades: int = 0):
    """نتیجهٔ آخرین بک‌تست را ثبت می‌کند (انتظارِ سودِ هر معامله، ٪)."""
    d = _read()
    d["expectancy_pct"] = round(float(expectancy_pct), 4)
    d["trades"] = int(trades)
    d["updated_at"] = datetime.utcnow().isoformat()
    _write(d)


def set_override(override: bool):
    """سوپر ادمین می‌تواند محافظ را دور بزند (با مسئولیت خودش)."""
    d = _read()
    d["override"] = bool(override)
    d["override_at"] = datetime.utcnow().isoformat()
    _write(d)


def get_guard() -> dict:
    d = _read()
    exp = d.get("expectancy_pct")
    override = bool(d.get("override", False))
    # وقتی بک‌تستی نداریم، وضعیت نامشخص است و مانع نمی‌شویم (بات قطع نشود).
    known = exp is not None
    blocking = known and exp <= 0 and not override
    return {
        "expectancy_pct": exp,
        "trades": d.get("trades", 0),
        "updated_at": d.get("updated_at"),
        "override": override,
        "known": known,
        "blocking": blocking,
    }


def is_live_trading_allowed() -> bool:
    """True اگر معاملهٔ واقعی مجاز است (سوددهیِ مثبت، یا override، یا هنوز بک‌تستی نداریم)."""
    return not get_guard()["blocking"]
