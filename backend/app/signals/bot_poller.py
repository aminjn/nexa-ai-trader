"""اتصال خودکار ربات با long-polling (بدون نیاز به وب‌هوک/SSL).

کاربر در ربات می‌زند:  /start <CODE>
ربات شناسه‌ی چت او را به کاربری که آن CODE را دارد وصل می‌کند.
- تلگرام: getUpdates از طریق پروکسی (در ایران مسدود است)
- بله: getUpdates مستقیم
"""
import asyncio
import httpx
from .. import models
from ..database import SessionLocal
from ..config import settings
from ..ai.gapgpt import get_ai_response


async def _api(base: str, method: str, use_proxy: bool, **params):
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    async with httpx.AsyncClient(timeout=40, proxy=proxy, trust_env=False) as c:
        r = await c.get(f"{base}/{method}", params=params)
        return r.json()


def _link(chat_id: str, code: str, platform: str) -> str:
    """کد را به کاربر وصل می‌کند و پیام پاسخ مناسب برمی‌گرداند."""
    db = SessionLocal()
    try:
        code = (code or "").strip()
        if not code:
            return ("به NEXA AI خوش آمدی! 👋\n"
                    "برای اتصال حسابت، از پنل کد اتصال را بگیر و این‌طور بفرست:\n/start کد_شما")
        user = db.query(models.User).filter(models.User.link_code == code).first()
        if not user:
            return "کد اتصال نامعتبر است. از پنل NEXA کد درست را بگیر و دوباره امتحان کن."
        if platform == "telegram":
            user.telegram_chat_id = str(chat_id)
        else:
            user.bale_chat_id = str(chat_id)
        db.commit()
        return f"✅ حساب شما با موفقیت وصل شد، {user.full_name or 'کاربر'} عزیز!\nاز این پس سیگنال‌ها همین‌جا برایت ارسال می‌شود."
    except Exception:
        db.rollback()
        return "خطا در اتصال. کمی بعد دوباره امتحان کن."
    finally:
        db.close()


def _get_token(field: str) -> str:
    db = SessionLocal()
    try:
        s = db.query(models.SystemSettings).first()
        return (getattr(s, field, "") or "") if s else ""
    finally:
        db.close()


def _payment_text() -> str:
    """متن اطلاعات پلن‌ها + پرداخت کارت‌به‌کارت + ادمین."""
    db = SessionLocal()
    try:
        s = db.query(models.SystemSettings).first()
        plans = db.query(models.Plan).filter(models.Plan.active == True).order_by(models.Plan.sort, models.Plan.level).all()
        lines = ["💳 <b>پلن‌های اشتراک NEXA AI</b>", ""]
        for p in plans:
            price = f"{p.price_toman:,} تومان / {p.duration_days} روز" if p.price_toman > 0 else "رایگان"
            lines.append(f"• <b>{p.name}</b>: {price}")
            if p.description:
                lines.append(f"  {p.description}")
        if s and (s.card_number or s.account_number):
            lines += ["", "برای خرید، مبلغ پلن را به این حساب واریز کن:"]
            if s.card_number:
                lines.append(f"💳 کارت: <b>{s.card_number}</b>" + (f" — به نام {s.card_holder}" if s.card_holder else ""))
            if s.account_number:
                lines.append(f"🏦 شماره حساب/شبا: <b>{s.account_number}</b>")
        if s and s.support_contact:
            lines += ["", f"سپس رسید پرداخت را برای ادمین بفرست: <b>{s.support_contact}</b> تا اشتراکت فعال شود."]
        return "\n".join(lines)
    finally:
        db.close()


async def _ai_reply(text: str) -> str:
    """پاسخ هوش مصنوعی به سؤال کاربر در نقش دستیار فروش/پشتیبانی NEXA."""
    db = SessionLocal()
    try:
        s = db.query(models.SystemSettings).first()
        if not s or not s.ai_support_enabled or not (s.gapgpt_api_key or "").strip():
            return ""  # هوش مصنوعی غیرفعال یا کلید تنظیم نشده
        plans = db.query(models.Plan).filter(models.Plan.active == True).order_by(models.Plan.level).all()
        plans_txt = "؛ ".join(
            f"{p.name}: {('%d تومان/%d روز' % (p.price_toman, p.duration_days)) if p.price_toman>0 else 'رایگان'} ({p.description})"
            for p in plans
        )
        card = s.card_number or "(تنظیم نشده)"
        holder = s.card_holder or ""
        account = s.account_number or ""
        support = s.support_contact or "(تنظیم نشده)"
        pay_info = f"شماره کارت {card}" + (f" به نام {holder}" if holder else "")
        if account:
            pay_info += f" یا شماره حساب/شبا {account}"
        sys_prompt = (
            "تو «دستیار فروش و پشتیبانی NEXA AI» هستی؛ یک سرویس سیگنال و تحلیل رمزارز فارسی. "
            "کوتاه، دوستانه و فارسی جواب بده. به سؤال کاربر درباره سرویس، سیگنال‌ها و پلن‌ها پاسخ بده. "
            "اگر کاربر قصد خرید یا ارتقا داشت، او را راهنمایی کن: پلن مناسب را پیشنهاد بده، "
            f"مبلغ را بگو، اطلاعات پرداخت ({pay_info}) را بده و بگو رسید را برای ادمین {support} بفرستد تا فعال شود. "
            "هیچ‌وقت قول سود تضمینی نده. پلن‌های فعلی: " + plans_txt
        )
        resp = await get_ai_response(
            [{"role": "system", "content": sys_prompt}, {"role": "user", "content": text}],
            db=db,
        )
        return resp or ""
    except Exception:
        return ""
    finally:
        db.close()


async def _poll_loop(platform: str, base_fn, token_field: str, use_proxy: bool):
    offset = 0
    initialized = False
    while True:
        token = _get_token(token_field)
        if not token:
            await asyncio.sleep(20)
            continue
        base = base_fn(token)
        try:
            # نخستین بار فقط وب‌هوک را پاک کن؛ پیام‌های در انتظار را نگه دار تا /startهای
            # ارسال‌شده قبل از بالا آمدن ربات هم پردازش شوند (تلگرام بعد از تأیید offset
            # آن‌ها را تکرار نمی‌کند، پس با ری‌استارت دوباره پردازش نمی‌شوند).
            if not initialized:
                try:
                    await _api(base, "deleteWebhook", use_proxy)
                except Exception:
                    pass
                initialized = True

            data = await _api(base, "getUpdates", use_proxy, offset=offset, timeout=30)
            for u in data.get("result", []):
                offset = max(offset, u.get("update_id", 0) + 1)
                # کلیک روی دکمه‌های واکنش زیر پست کانال
                cq = u.get("callback_query")
                if cq:
                    asyncio.create_task(_handle_callback(platform, base, use_proxy, cq))
                    continue
                msg = u.get("message") or u.get("edited_message") or {}
                chat = msg.get("chat") or {}
                chat_id = chat.get("id")
                chat_type = chat.get("type")
                text = (msg.get("text") or "").strip()
                if not chat_id or not text:
                    continue
                # فقط به چت خصوصی پاسخ بده؛ پست‌های کانال/گروه (مثل سیگنال‌های خودِ ربات) را نادیده بگیر
                if chat_type and chat_type != "private":
                    continue
                # هر پیام را در یک تسک جدا پردازش کن تا تأخیر هوش مصنوعی، دریافت را بلاک نکند
                asyncio.create_task(_handle_message(platform, base, use_proxy, chat_id, text))
        except Exception:
            await asyncio.sleep(10)
            continue


_BUY_WORDS = ("خرید", "پرداخت", "اشتراک", "پلن", "قیمت", "تمدید", "vip", "خريد", "/buy", "/plans", "/pay")


async def _handle_message(platform, base, use_proxy, chat_id, text):
    try:
        low = text.strip().lower()
        if low.startswith("/start"):
            parts = text.split(maxsplit=1)
            code = parts[1] if len(parts) > 1 else ""
            reply = _link(str(chat_id), code, platform)
        elif low in ("/help", "راهنما", "help"):
            reply = ("دستیار NEXA AI 🤖\n"
                     "هر سؤالی درباره سیگنال‌ها یا پلن‌ها داری بپرس.\n"
                     "برای خرید اشتراک کلمه «خرید» را بفرست.")
        elif any(w in low for w in _BUY_WORDS):
            reply = _payment_text()
        else:
            reply = await _ai_reply(text)
            if not reply:
                reply = _payment_text()
        from .notifier import _strip_html
        try:
            # تگ‌های HTML را حذف می‌کنیم چون نه بله و نه این مسیر تلگرام HTML را رندر نمی‌کنند
            await _api(base, "sendMessage", use_proxy, chat_id=chat_id, text=_strip_html(reply))
        except Exception:
            pass
    except Exception:
        pass


async def _handle_callback(platform, base, use_proxy, cq):
    """کلیک روی واکنش 👍/❤️/🔥 را پردازش و شمارنده را به‌روز می‌کند."""
    from . import reactions
    from .notifier import edit_markup, answer_callback
    from .engine import _channel_join_url
    try:
        data = (cq.get("data") or "")
        cb_id = cq.get("id")
        if not data.startswith("react:"):
            if cb_id:
                await answer_callback(base, cb_id, use_proxy=use_proxy)
            return
        kind = data.split(":", 1)[1]
        message = cq.get("message") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        message_id = message.get("message_id")
        user_id = (cq.get("from") or {}).get("id")
        if chat_id is None or message_id is None:
            return
        reactions.toggle(platform, chat_id, message_id, kind, user_id)
        # لینک عضویت را دوباره از تنظیمات بساز تا دکمهٔ عضویت حفظ شود
        join = ""
        db = SessionLocal()
        try:
            s = db.query(models.SystemSettings).first()
            if s:
                join = _channel_join_url(platform, s)
        finally:
            db.close()
        kb = reactions.keyboard(platform, chat_id, message_id, join)
        await edit_markup(base, chat_id, message_id, kb, use_proxy=use_proxy)
        if cb_id:
            await answer_callback(base, cb_id, "ثبت شد ✓", use_proxy=use_proxy)
    except Exception as e:
        print(f"⚠️ callback error: {str(e)[:150]}")


async def telegram_poll_loop():
    await _poll_loop(
        "telegram",
        lambda t: f"https://api.telegram.org/bot{t}",
        "telegram_bot_token",
        use_proxy=True,
    )


async def bale_poll_loop():
    await _poll_loop(
        "bale",
        lambda t: f"https://tapi.bale.ai/bot{t}",
        "bale_bot_token",
        use_proxy=True,  # روی این سرور بله فقط از طریق پروکسی در دسترس است
    )
