"""تولید و انتشار خودکار محتوای متنی در کانال عمومی (تلگرام/بله).

تحلیل روزانه‌ی بازار = قیمت + تصمیم ML + تحلیل تکنیکال/فاندامنتال + سرتیتر اخبار.
"""
import asyncio
from datetime import datetime
import pandas as pd

from .. import models
from ..database import SessionLocal
from ..exchanges.nobitex import NobitexExchange
from ..ml.trainer import get_trainer
from .notifier import send_telegram, send_bale


def _fmt(n: float) -> str:
    try:
        return f"{round(n):,}"
    except Exception:
        return str(n)


def _clean_cut(text: str, limit: int) -> str:
    """متن را در مرز جمله (نقطه/خط‌جدید) می‌بُرد تا نصفه نماند."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", ".", "؟", "!", "\n", "،"):
        idx = cut.rfind(sep)
        if idx > limit * 0.5:
            return cut[:idx + 1].strip() + " …"
    return cut.strip() + " …"


BAR = "━━━━━━━━━━━━━━"


def _is_english(text: str) -> bool:
    """آیا متن عمدتاً انگلیسی/لاتین است؟ (برای حذف خبرهای ترجمه‌نشده)"""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    latin = sum(1 for c in letters if ord(c) < 0x0600)  # حروف غیرفارسی/عربی
    return latin / len(letters) > 0.35


async def _news_bullets(db, news_raw: str, n: int = 5) -> list:
    """اخبار خام را به چند خبرِ کوتاهِ فارسیِ روان تبدیل می‌کند.

    خبرهای خارجی حتماً به فارسی ترجمه می‌شوند؛ اگر هوش مصنوعی در دسترس نباشد یا
    ترجمه نشود، خبرِ انگلیسی نمایش داده نمی‌شود (به‌جای اینکه خام انگلیسی برود).
    """
    news_raw = (news_raw or "").strip()
    if not news_raw:
        return []
    try:
        from ..ai.gapgpt import get_ai_response, get_ai_config
        if get_ai_config(db).get("api_key"):
            prompt = (
                f"خبرهای خامِ زیر دربارهٔ رمزارز هستند و ممکن است انگلیسی باشند. "
                f"آن‌ها را به حداکثر {n} خبرِ کوتاهِ فارسی ترجمه و خلاصه کن. "
                "🔴 قانون مهم: خروجی باید ۱۰۰٪ فارسی باشد؛ هر خبر انگلیسی را حتماً ترجمه کن و "
                "هیچ جمله یا عبارت انگلیسی در خروجی نگذار (فقط نمادهای ارز مثل BTC/ETH مجازند). "
                "هر خبر دقیقاً یک خط و کامل (بدون جملهٔ ناقص). "
                "فقط خطوط خبر را برگردان؛ هر خط با «🔹 » شروع شود و هیچ توضیح اضافه نده.\n\n"
                + news_raw[:1500]
            )
            resp = await asyncio.wait_for(get_ai_response([{"role": "user", "content": prompt}], db=db), timeout=40)
            lines = [l.strip() for l in (resp or "").splitlines() if l.strip()]
            lines = [(l if l.startswith("🔹") else "🔹 " + l.lstrip("•-–* ")) for l in lines]
            # خطوطی که هنوز عمدتاً انگلیسی‌اند (ترجمه‌نشده) را حذف کن
            lines = [l for l in lines if not _is_english(l)]
            if lines:
                return lines[:n]
    except Exception:
        pass
    # بدون ترجمهٔ هوش مصنوعی: فقط خبرهای فارسیِ موجود را نشان بده (انگلیسی را حذف کن)
    import re
    sents = [s.strip() for s in re.split(r"[\n.؟!]", news_raw) if len(s.strip()) > 25]
    fa = [s for s in sents if not _is_english(s)]
    return ["🔹 " + _clean_cut(s, 140) for s in fa[:n]]


async def generate_market_content(db) -> str:
    srow = db.query(models.SystemSettings).first()
    coins_raw = (srow.signal_coins if srow else "") or "BTC,ETH"
    coins = [c.strip().upper() for c in coins_raw.split(",") if c.strip()][:6]

    ex = NobitexExchange("")
    trainer = get_trainer()

    # ── قیمت و سیگنال لحظه‌ای هر ارز ──
    coin_lines = []
    for coin in coins:
        try:
            pair = f"{coin}/RLS"
            t = await ex.get_ticker(pair)
            rial = t.get("last", 0) or 0
            if not rial:
                continue
            toman = rial / 10.0
            side = "⏳ صبر"
            if trainer.is_trained:
                ohlcv = await ex.get_ohlcv(pair, "1h", 200)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    ml = trainer.predict(df)
                    side = {"BUY": "🟢 خرید", "SELL": "🔴 فروش", "WAIT": "⏳ صبر"}.get(ml.get("signal"), "⏳ صبر")
            coin_lines.append(f"🔸 <b>{coin}</b> — {_fmt(toman)} ت  |  {side}")
        except Exception:
            continue

    fund_summary = ""
    try:
        from ..ai.fundamental import get_fundamental
        f = await get_fundamental(db, ex)
        fund_summary = f.get("summary", "") or ""
    except Exception:
        pass

    news_raw = ""
    try:
        from ..scraping.scraper import collect_scraped_context
        news_raw = collect_scraped_context(db, max_chars=1500)
    except Exception:
        pass
    bullets = await _news_bullets(db, news_raw)

    # ── ساخت پستِ گرافیکیِ تمیز در کد (قالب ثابت و خوانا) ──
    from .engine import tehran_now
    now = tehran_now()
    parts = [f"📊 <b>گزارش بازار NEXA AI</b>\n🗓 {now.strftime('%Y/%m/%d')}  ·  🕐 {now.strftime('%H:%M')}"]
    if coin_lines:
        parts.append("💰 <b>قیمت و سیگنال لحظه‌ای</b>\n" + "\n".join(coin_lines))
    if fund_summary:
        parts.append("🌍 <b>نبض بازار</b>\n" + _clean_cut(fund_summary, 450))
    if bullets:
        parts.append("📰 <b>مهم‌ترین خبرها</b>\n" + "\n".join(bullets))
    parts.append("🤖 <b>NEXA AI</b> — تحلیل هوشمند بازار رمزارز\n⚠️ سیگنال‌ها تضمین سود نیستند؛ مدیریت ریسک کنید.")
    msg = ("\n" + BAR + "\n").join(parts)
    return _clean_cut(msg, 3500)


def _join_footer(platform: str, srow) -> str:
    """فوتر متنیِ عضویت/پشتیبانی — چون متن است، هنگام فوروارد حفظ می‌شود
    (برخلاف دکمه‌های inline که تلگرام/بله موقع فوروارد حذف می‌کنند)."""
    from .engine import _channel_join_url, SEP
    parts = []
    url = _channel_join_url(platform, srow)
    if url:
        parts.append(f"📢 عضویت و دنبال‌کردن کانال: {url}")
    sup = (getattr(srow, "support_contact", "") or "").strip()
    if sup:
        parts.append(f"💬 ثبت‌نام و پشتیبانی: {sup}")
    if not parts:
        return ""
    return "\n" + SEP + "\n" + "\n".join(parts)


async def publish_content(db) -> bool:
    srow = db.query(models.SystemSettings).first()
    if not srow:
        return False
    text = await generate_market_content(db)
    ok = False
    if srow.telegram_channel_id and srow.telegram_bot_token:
        ok = await send_telegram(srow.telegram_bot_token, srow.telegram_channel_id, text + _join_footer("telegram", srow)) or ok
    if srow.bale_channel_id and srow.bale_bot_token:
        ok = await send_bale(srow.bale_bot_token, srow.bale_channel_id, text + _join_footer("bale", srow)) or ok
    return ok


async def content_loop():
    while True:
        db = SessionLocal()
        try:
            srow = db.query(models.SystemSettings).first()
            hours = (srow.content_interval_hours if srow else 6) or 6
        except Exception:
            hours = 6
        finally:
            db.close()

        await asyncio.sleep(max(1, hours) * 3600)

        db = SessionLocal()
        try:
            await publish_content(db)
        except Exception as e:
            print(f"⚠️ content loop warning: {e}")
        finally:
            db.close()


# ─────────────────────────── تبلیغ (Ad) ───────────────────────────

async def generate_ad(db) -> str:
    """تبلیغ را برمی‌گرداند: اگر متن دستی تنظیم شده باشد همان، وگرنه هوش مصنوعی می‌سازد."""
    srow = db.query(models.SystemSettings).first()
    if srow and (srow.ad_text or "").strip():
        return srow.ad_text.strip()
    # از پلن‌های جدیدِ ربات معامله‌گر استفاده می‌کنیم (نه پلن‌های قدیمی سیگنال)
    plans = db.query(models.TradingPlan).filter(models.TradingPlan.active == True).order_by(
        models.TradingPlan.sort, models.TradingPlan.id).all()

    def _price(p):
        if p.plan_type == "managed":
            return "کارمزد از سود"
        return ('%s تومان/%d روز' % (f"{p.price_toman:,}", p.duration_days)) if p.price_toman > 0 else 'رایگان'
    # کارت پلن‌ها به‌صورت گرافیکی (هر پلن یک خط با ایموجی)
    plan_cards = []
    for p in plans:
        icon = "👑" if p.plan_type == "managed" else "⚡"
        plan_cards.append(f"{icon} <b>{p.name}</b> — {_price(p)}")
    plans_block = "\n".join(plan_cards)
    support = (srow.support_contact if srow else "") or ""

    body = ""
    try:
        from ..ai.gapgpt import get_ai_response, get_ai_config
        if srow and get_ai_config(db).get("api_key"):
            prompt = (
                "یک متنِ تبلیغاتیِ کوتاه (۲ تا ۳ خط)، جذاب و حرفه‌ای فارسی برای ربات معامله‌گر «NEXA AI» بنویس "
                "که کاربر را به استفاده ترغیب کند. لحن پرانرژی ولی صادقانه؛ هیچ قول سود تضمینی نده. "
                "فقط همان ۲-۳ خط متن را برگردان، بدون عنوان و بدون لیست پلن (پلن‌ها جداگانه اضافه می‌شوند)."
            )
            resp = await asyncio.wait_for(
                get_ai_response([{"role": "user", "content": prompt}], db=db), timeout=40)
            if resp and len(resp.strip()) > 20:
                body = _clean_cut(resp.strip(), 400)
    except Exception:
        pass
    if not body:
        body = ("با ربات هوشمند NEXA AI، با مدل یادگیری ماشین + تحلیل فاندامنتال و تکنیکال، "
                "معاملات رمزارز را خودکار و حساب‌شده انجام بده.")

    # ساخت تبلیغِ گرافیکیِ تمیز
    parts = ["🚀 <b>NEXA AI — ربات معامله‌گر هوشمند رمزارز</b>", body]
    if plans_block:
        parts.append("💎 <b>پلن‌ها</b>\n" + plans_block)
    cta = []
    if support:
        cta.append(f"📩 ثبت‌نام و مشاوره: {support}")
    cta.append("✅ همین حالا شروع کن!")
    parts.append("\n".join(cta))
    return ("\n" + BAR + "\n").join(parts)


async def publish_ad(db) -> bool:
    srow = db.query(models.SystemSettings).first()
    if not srow:
        return False
    text = await generate_ad(db)
    ok = False
    if srow.telegram_channel_id and srow.telegram_bot_token:
        ok = await send_telegram(srow.telegram_bot_token, srow.telegram_channel_id, text + _join_footer("telegram", srow)) or ok
    if srow.bale_channel_id and srow.bale_bot_token:
        ok = await send_bale(srow.bale_bot_token, srow.bale_channel_id, text + _join_footer("bale", srow)) or ok
    return ok


async def ad_loop():
    while True:
        db = SessionLocal()
        try:
            srow = db.query(models.SystemSettings).first()
            hours = (srow.ad_interval_hours if srow else 12) or 12
        except Exception:
            hours = 12
        finally:
            db.close()

        await asyncio.sleep(max(1, hours) * 3600)

        db = SessionLocal()
        try:
            await publish_ad(db)
        except Exception as e:
            print(f"⚠️ ad loop warning: {e}")
        finally:
            db.close()
