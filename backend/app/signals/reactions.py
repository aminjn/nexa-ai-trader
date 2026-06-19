"""واکنش‌های زیر پیام‌های کانال (👍 ❤️ 🔥) + دکمهٔ عضویت در کانال.

شمارش واکنش‌ها درون‌حافظه‌ای است (با ری‌استارت صفر می‌شود؛ برای جذابیت پیام
کافی است). هر کاربر فقط یک‌بار روی هر واکنش حساب می‌شود.
"""

# (کلید callback، ایموجی)
REACTIONS = [("like", "👍"), ("heart", "❤️"), ("fire", "🔥")]

# key = f"{platform}:{chat_id}:{message_id}" → {"like": set(user_ids), ...}
_state: dict[str, dict[str, set]] = {}

# سقف نگه‌داری حالت برای جلوگیری از رشد بی‌نهایت حافظه
_MAX = 500


def _key(platform, chat_id, message_id) -> str:
    return f"{platform}:{chat_id}:{message_id}"


def register(platform, chat_id, message_id):
    """یک پیام تازه‌ارسال‌شده را برای دریافت واکنش ثبت می‌کند."""
    if len(_state) > _MAX:
        # قدیمی‌ترین‌ها را حذف کن
        for k in list(_state.keys())[: len(_state) - _MAX]:
            _state.pop(k, None)
    _state.setdefault(_key(platform, chat_id, message_id), {k: set() for k, _ in REACTIONS})


def toggle(platform, chat_id, message_id, kind, user_id) -> bool:
    """واکنش کاربر را اضافه/حذف می‌کند. اگر پیام ثبت‌نشده بود هم می‌سازد."""
    key = _key(platform, chat_id, message_id)
    rec = _state.setdefault(key, {k: set() for k, _ in REACTIONS})
    if kind not in rec:
        return False
    # کاربر فقط روی یک واکنش می‌تواند فعال باشد؛ بقیه را پاک کن
    for k in rec:
        if k != kind:
            rec[k].discard(user_id)
    if user_id in rec[kind]:
        rec[kind].discard(user_id)
    else:
        rec[kind].add(user_id)
    return True


def _counts(platform, chat_id, message_id) -> dict:
    rec = _state.get(_key(platform, chat_id, message_id), {})
    return {k: len(rec.get(k, set())) for k, _ in REACTIONS}


def keyboard(platform, chat_id, message_id, join_url: str = "", join_label: str = "📢 عضویت در کانال") -> dict:
    """دکمه‌های واکنش + دکمهٔ عضویت را برای یک پیام می‌سازد."""
    counts = _counts(platform, chat_id, message_id)
    react_row = []
    for k, emoji in REACTIONS:
        n = counts.get(k, 0)
        label = f"{emoji} {n}" if n else emoji
        react_row.append({"text": label, "callback_data": f"react:{k}"})
    rows = [react_row]
    if join_url:
        rows.append([{"text": join_label, "url": join_url}])
    return {"inline_keyboard": rows}
