"""موتور تولید و توزیع سیگنال.

برای هر ارز تنظیم‌شده: تصمیم ML + تحلیل تکنیکال + فاندامنتال را می‌گیرد،
یک رکورد Signal می‌سازد و سپس بر اساس پلن هر مشترک، آن را به کانال‌هایش
(تلگرام / بله / داخل پنل) می‌فرستد.
"""
from datetime import datetime, timedelta
import pandas as pd

from .. import models
from ..database import SessionLocal
from ..exchanges.nobitex import NobitexExchange
from ..ml.trainer import get_trainer
from .notifier import send_telegram, send_bale

# هدف سود/حد ضرر پیش‌فرض برای محاسبه‌ی قیمت هدف/حد ضررِ سیگنال
DEFAULT_TP = 3.5
DEFAULT_SL = 1.5


def _fmt(n: float) -> str:
    try:
        return f"{round(n):,}"
    except Exception:
        return str(n)


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
        for sig in created:
            try:
                await distribute_signal(db, sig, settings_row)
            except Exception:
                continue
    return len(created)


def _signal_text(sig: models.Signal, include_analysis: bool) -> str:
    side_fa = {"BUY": "🟢 خرید", "SELL": "🔴 فروش", "WAIT": "⏳ صبر"}.get(sig.side, sig.side)
    lines = [
        f"<b>سیگنال {sig.coin}</b>",
        f"تصمیم: {side_fa}  (اطمینان {round(sig.confidence*100)}٪)",
        f"قیمت فعلی: {_fmt(sig.entry_price)} تومان",
    ]
    if sig.side == "BUY":
        lines.append(f"🎯 هدف فروش: {_fmt(sig.target_price)} تومان")
        lines.append(f"🛑 حد ضرر: {_fmt(sig.stop_price)} تومان")
    lines.append(f"تکنیکال: {sig.tech_conclusion} | فاندامنتال: {sig.fund_conclusion}")
    if include_analysis and sig.analysis:
        lines.append("\n" + sig.analysis)
    lines.append("\n— NEXA AI")
    return "\n".join(lines)


async def distribute_signal(db, sig: models.Signal, settings_row: models.SystemSettings):
    """سیگنال را به مشترکان فعالی که سطح پلنشان اجازه می‌دهد می‌فرستد (بدون تأخیر)."""
    tg_token = settings_row.telegram_bot_token or ""
    bale_token = settings_row.bale_bot_token or ""

    subs = db.query(models.Subscription).filter(models.Subscription.status == "active").all()
    now = datetime.utcnow()
    for sub in subs:
        if sub.end_at and sub.end_at < now:
            continue
        plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
        if not plan or plan.level < sig.min_level:
            continue
        # پلن‌های دارای تأخیر (رایگان) را همان لحظه push نمی‌کنیم؛ در پنل با تأخیر می‌بینند
        if (plan.delay_minutes or 0) > 0:
            continue
        user = db.query(models.User).filter(models.User.id == sub.user_id).first()
        if not user:
            continue
        channels = plan.channels or []
        text = _signal_text(sig, include_analysis=bool(plan.include_analysis))
        if "telegram" in channels and user.telegram_chat_id:
            await send_telegram(tg_token, user.telegram_chat_id, text)
        if "bale" in channels and user.bale_chat_id:
            await send_bale(bale_token, user.bale_chat_id, text)


async def signals_loop():
    """حلقه‌ی زمان‌بندی تولید سیگنال طبق بازه‌ی تنظیم‌شده."""
    import asyncio
    while True:
        db = SessionLocal()
        try:
            srow = db.query(models.SystemSettings).first()
            interval = (srow.signal_interval_minutes if srow else 30) or 30
        except Exception:
            interval = 30
        finally:
            db.close()

        await asyncio.sleep(max(1, interval) * 60)

        db = SessionLocal()
        try:
            await generate_signals(db, push=True)
        except Exception as e:
            print(f"⚠️ signals loop warning: {e}")
        finally:
            db.close()
