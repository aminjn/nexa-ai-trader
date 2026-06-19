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


async def generate_market_content(db) -> str:
    srow = db.query(models.SystemSettings).first()
    coins_raw = (srow.signal_coins if srow else "") or "BTC,ETH"
    coins = [c.strip().upper() for c in coins_raw.split(",") if c.strip()][:6]

    ex = NobitexExchange("")
    trainer = get_trainer()

    # ── جمع‌آوری داده‌ها ──
    coin_lines = []
    for coin in coins:
        try:
            pair = f"{coin}/RLS"
            t = await ex.get_ticker(pair)
            rial = t.get("last", 0) or 0
            if not rial:
                continue
            toman = rial / 10.0
            side = "—"
            if trainer.is_trained:
                ohlcv = await ex.get_ohlcv(pair, "1h", 200)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    ml = trainer.predict(df)
                    side = {"BUY": "🟢 خرید", "SELL": "🔴 فروش", "WAIT": "⏳ صبر"}.get(ml.get("signal"), "—")
            coin_lines.append(f"• <b>{coin}</b>: {_fmt(toman)} تومان | سیگنال: {side}")
        except Exception:
            continue

    fund_summary = ""
    try:
        from ..ai.fundamental import get_fundamental
        f = await get_fundamental(db, ex)
        fund_summary = f.get("summary", "") or ""
    except Exception:
        pass

    news = ""
    try:
        from ..scraping.scraper import collect_scraped_context
        news = collect_scraped_context(db, max_chars=1500)
    except Exception:
        pass

    # ── اگر کلید هوش مصنوعی هست، یک پست تمیز و کامل بنویس ──
    try:
        from ..ai.gapgpt import get_ai_response, get_ai_config
        if srow and get_ai_config(db).get("api_key"):
            ctx = "قیمت و سیگنال ارزها:\n" + "\n".join(coin_lines)
            if fund_summary:
                ctx += "\n\nتحلیل فاندامنتال: " + fund_summary
            if news:
                ctx += "\n\nاخبار خام (خلاصه کن): " + news[:1200]
            prompt = (
                "تو تولیدکننده محتوای کانال «NEXA AI» (سیگنال و تحلیل رمزارز) هستی. "
                "از داده‌های زیر یک پست کوتاه، روان و کامل فارسی برای کانال بنویس (حداکثر ۶ خط). "
                "خبرها را خودت خلاصه کن، جمله ناقص نگذار، قول سود تضمینی نده. "
                "در پایان یک خط «— کانال رسمی NEXA AI» بگذار.\n\n" + ctx
            )
            resp = await asyncio.wait_for(
                get_ai_response([{"role": "user", "content": prompt}], db=db),
                timeout=40,
            )
            if resp and len(resp.strip()) > 30:
                return resp.strip()[:3500]
    except Exception:
        pass

    # ── حالت پشتیبان: متن ساختاریافته با برش تمیز ──
    lines = [f"📈 <b>تحلیل بازار NEXA AI</b> — {datetime.utcnow().strftime('%Y/%m/%d')}", ""]
    lines += coin_lines
    if fund_summary:
        lines += ["", "🌍 <b>فاندامنتال:</b> " + _clean_cut(fund_summary, 400)]
    if news:
        lines += ["", "📰 <b>از اخبار:</b>", _clean_cut(news, 700)]
    lines += ["", "— کانال رسمی NEXA AI"]
    return "\n".join(lines)


async def publish_content(db) -> bool:
    srow = db.query(models.SystemSettings).first()
    if not srow:
        return False
    text = await generate_market_content(db)
    ok = False
    if srow.telegram_channel_id and srow.telegram_bot_token:
        ok = await send_telegram(srow.telegram_bot_token, srow.telegram_channel_id, text) or ok
    if srow.bale_channel_id and srow.bale_bot_token:
        ok = await send_bale(srow.bale_bot_token, srow.bale_channel_id, text) or ok
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
