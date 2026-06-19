"""موتور تولید و توزیع سیگنال.

برای هر ارز تنظیم‌شده: تصمیم ML + تحلیل تکنیکال + فاندامنتال را می‌گیرد،
یک رکورد Signal می‌سازد و سپس بر اساس پلن هر مشترک، آن را به کانال‌هایش
(تلگرام / بله / داخل پنل) می‌فرستد.
"""
from datetime import datetime, timedelta
import pandas as pd


def tehran_now() -> datetime:
    """زمان فعلی به وقت تهران (ایران UTC+3:30، بدون ساعت تابستانی)."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Tehran"))
    except Exception:
        return datetime.utcnow() + timedelta(hours=3, minutes=30)

from .. import models
from ..database import SessionLocal
from ..exchanges.nobitex import NobitexExchange
from ..ml.trainer import get_trainer
from .notifier import send_telegram, send_bale

# هدف سود/حد ضرر پیش‌فرض برای محاسبه‌ی قیمت هدف/حد ضررِ سیگنال
DEFAULT_TP = 3.5
DEFAULT_SL = 1.5


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _fmt(n: float) -> str:
    try:
        return f"{round(n):,}".translate(_FA_DIGITS)
    except Exception:
        return str(n)


def _bar(conf: float) -> str:
    """نوار اطمینان گرافیکی با بلوک‌های یونیکد."""
    filled = max(0, min(10, round((conf or 0) * 10)))
    return "█" * filled + "░" * (10 - filled)


def _pct(conf: float) -> str:
    return f"{round((conf or 0) * 100)}".translate(_FA_DIGITS)


async def generate_signals(db, push: bool = True) -> int:
    """برای هر ارز تنظیم‌شده یک سیگنال می‌سازد و (در صورت push) توزیع می‌کند."""
    settings_row = db.query(models.SystemSettings).first()
    coins_raw = (settings_row.signal_coins if settings_row else "") or "BTC,ETH"
    coins = [c.strip().upper() for c in coins_raw.split(",") if c.strip()]
    if not coins:
        coins = ["BTC", "ETH"]

    ex = NobitexExchange("")  # داده‌ی عمومی نوبیتکس بدون نیاز به توکن
    trainer = get_trainer()

    created = []
    for idx, coin in enumerate(coins):
        try:
            pair = f"{coin}/RLS"
            ticker = await ex.get_ticker(pair)
            rial = ticker.get("last", 0) or 0
            if not rial:
                continue
            price_toman = rial / 10.0

            ohlcv = await ex.get_ohlcv(pair, "1h", 300)
            if not ohlcv:
                continue
            df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

            # تصمیم ML
            side, conf = "WAIT", 0.0
            if trainer.is_trained:
                ml = trainer.predict(df)
                side, conf = ml.get("signal", "WAIT"), ml.get("confidence", 0.0)

            # تحلیل تکنیکال + فاندامنتال (متن)
            tech_c, fund_c, analysis = "خنثی", "خنثی", ""
            try:
                from ..api.dashboard import _compute_technical
                t = _compute_technical(df) or {}
                tech_c = t.get("conclusion", "خنثی")
                analysis += "📊 تحلیل تکنیکال: " + (t.get("text", "") or "") + f"\nنتیجه‌گیری: {tech_c}\n\n"
            except Exception:
                pass
            try:
                from ..ai.fundamental import get_fundamental
                f = await get_fundamental(db, ex)
                sc = f.get("score", 0)
                fund_c = "صعودی" if sc > 0.1 else ("نزولی" if sc < -0.1 else "خنثی")
                analysis += "🌍 تحلیل فاندامنتال: " + (f.get("summary", "") or "") + f"\nنتیجه‌گیری: {fund_c}\n"
            except Exception:
                pass

            sig = models.Signal(
                coin=coin,
                side=side,
                confidence=round(conf, 4),
                entry_price=round(price_toman, 2),
                target_price=round(price_toman * (1 + DEFAULT_TP / 100), 2),
                stop_price=round(price_toman * (1 - DEFAULT_SL / 100), 2),
                timeframe="1h",
                tech_conclusion=tech_c,
                fund_conclusion=fund_c,
                analysis=analysis.strip(),
                # ارز اول (معمولاً BTC) برای همه؛ بقیه برای پلن‌های بالاتر
                min_level=0 if idx == 0 else 1,
            )
            db.add(sig)
            db.commit()
            db.refresh(sig)
            created.append(sig)
        except Exception:
            db.rollback()
            continue

    if push and created and settings_row:
        # همه‌ی سیگنال‌های این دور در یک پیام جمع‌بندی به کانال می‌روند (نه یک پیام برای هر ارز)
        try:
            await post_batch_to_channel(created, settings_row)
        except Exception:
            pass
        # ارسال به مشترکان (هر مشترک یک پیام جمع‌بندی طبق پلنش)
        try:
            await distribute_batch(db, created, settings_row)
        except Exception:
            pass
    return len(created)


def _buy_card(s) -> str:
    return (
        f"🟢 <b>خرید {s.coin}</b>\n"
        f"💵 قیمت: {_fmt(s.entry_price)} ت\n"
        f"🎯 هدف: {_fmt(s.target_price)}  ┊  🛑 حد ضرر: {_fmt(s.stop_price)}\n"
        f"📊 اطمینان: {_bar(s.confidence)} {_pct(s.confidence)}٪"
    )


def _sell_card(s) -> str:
    return (
        f"🔴 <b>فروش / احتیاط {s.coin}</b>\n"
        f"💵 قیمت: {_fmt(s.entry_price)} ت\n"
        f"📊 اطمینان: {_bar(s.confidence)} {_pct(s.confidence)}٪"
    )


def _batch_messages(signals, header: str, include_analysis: bool = False, limit: int = 3500):
    """سیگنال‌ها را به‌صورت کارت‌های گرافیکی خوانا می‌سازد (خرید/فروش جدا، صبر جمع‌وجور)."""
    buys = [s for s in signals if s.side == "BUY"]
    sells = [s for s in signals if s.side == "SELL"]
    waits = [s for s in signals if s.side not in ("BUY", "SELL")]
    sep = "➖➖➖➖➖➖➖➖➖"

    blocks = []
    for s in buys:
        blocks.append(_buy_card(s))
    for s in sells:
        blocks.append(_sell_card(s))

    head = header + "\n" + sep
    foot_parts = []
    if waits:
        foot_parts.append("⏳ <b>در انتظار:</b> " + "، ".join(s.coin for s in waits))
    foot_parts.append("🤖 <b>NEXA AI</b>")
    footer = sep + "\n" + "\n".join(foot_parts)

    # کارت‌ها را با جداکننده کنار هم بگذار و در صورت طولانی‌شدن به چند پیام تقسیم کن
    msgs, cur = [], head
    for b in blocks:
        piece = "\n\n" + b
        if len(cur) + len(piece) + len(footer) + 4 > limit:
            msgs.append(cur + "\n\n" + sep)
            cur = head
        cur += piece
    msgs.append(cur + "\n\n" + footer)
    return msgs


async def post_batch_to_channel(created, settings_row):
    """همه‌ی سیگنال‌های یک دور را در یک پیام به کانال تلگرام/بله می‌فرستد."""
    header = f"📡 <b>سیگنال‌های NEXA AI</b> — {tehran_now().strftime('%H:%M')}"
    for msg in _batch_messages(created, header):
        if settings_row.telegram_channel_id and settings_row.telegram_bot_token:
            await send_telegram(settings_row.telegram_bot_token, settings_row.telegram_channel_id, msg)
        if settings_row.bale_channel_id and settings_row.bale_bot_token:
            await send_bale(settings_row.bale_bot_token, settings_row.bale_channel_id, msg)


async def distribute_batch(db, created, settings_row):
    """به هر مشترک فعال، یک پیام جمع‌بندی از سیگنال‌های مجازِ پلنش می‌فرستد."""
    tg_token = settings_row.telegram_bot_token or ""
    bale_token = settings_row.bale_bot_token or ""
    subs = db.query(models.Subscription).filter(models.Subscription.status == "active").all()
    now = datetime.utcnow()
    for sub in subs:
        if sub.end_at and sub.end_at < now:
            continue
        plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
        if not plan or (plan.delay_minutes or 0) > 0:
            continue
        allowed = [s for s in created if s.min_level <= plan.level]
        if not allowed:
            continue
        user = db.query(models.User).filter(models.User.id == sub.user_id).first()
        if not user:
            continue
        channels = plan.channels or []
        header = "📡 <b>سیگنال‌های NEXA AI</b>"
        for msg in _batch_messages(allowed, header):
            if "telegram" in channels and user.telegram_chat_id:
                await send_telegram(tg_token, user.telegram_chat_id, msg)
            if "bale" in channels and user.bale_chat_id:
                await send_bale(bale_token, user.bale_chat_id, msg)


async def signals_loop():
    """حلقه‌ی زمان‌بندی تولید سیگنال.

    هر ۳۰ ثانیه بررسی می‌کند؛ اگر از آخرین تولید به‌اندازه‌ی بازه‌ی تنظیم‌شده
    گذشته باشد، سیگنال تولید و در کانال/برای مشترکان ارسال می‌کند. تغییر بازه
    در پنل بدون نیاز به ری‌استارت اعمال می‌شود. هر اجرا در لاگ فعالیت ثبت می‌شود.
    """
    import asyncio
    import time
    try:
        from ..trading.bot import log_bot_event
    except Exception:
        def log_bot_event(*a, **k):
            pass

    await asyncio.sleep(20)  # کمی صبر تا برنامه کامل بالا بیاید
    last_run = 0.0
    while True:
        db = SessionLocal()
        try:
            srow = db.query(models.SystemSettings).first()
            interval = (srow.signal_interval_minutes if srow else 30) or 30
        except Exception:
            interval = 30
        finally:
            db.close()

        now = time.time()
        if now - last_run >= interval * 60:
            last_run = now
            db = SessionLocal()
            try:
                n = await generate_signals(db, push=True)
                if n:
                    log_bot_event(f"📡 {n} سیگنال خودکار تولید و ارسال شد (هر {interval} دقیقه)")
                else:
                    log_bot_event("📡 تولید خودکار سیگنال اجرا شد ولی قیمتی از نوبیتکس دریافت نشد", "error")
            except Exception as e:
                log_bot_event(f"📡 خطا در تولید خودکار سیگنال: {str(e)[:100]}", "error")
                print(f"⚠️ signals loop warning: {e}")
            finally:
                db.close()

        await asyncio.sleep(30)

