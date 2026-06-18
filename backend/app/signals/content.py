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


async def generate_market_content(db) -> str:
    srow = db.query(models.SystemSettings).first()
    coins_raw = (srow.signal_coins if srow else "") or "BTC,ETH"
    coins = [c.strip().upper() for c in coins_raw.split(",") if c.strip()][:6]

    ex = NobitexExchange("")
    trainer = get_trainer()
    lines = [f"📈 <b>تحلیل بازار NEXA AI</b> — {datetime.utcnow().strftime('%Y/%m/%d')}", ""]

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
            lines.append(f"• <b>{coin}</b>: {_fmt(toman)} تومان | سیگنال: {side}")
        except Exception:
            continue

    # فاندامنتال
    try:
        from ..ai.fundamental import get_fundamental
        f = await get_fundamental(db, ex)
        if f.get("summary"):
            lines.append("")
            lines.append("🌍 <b>فاندامنتال:</b> " + f["summary"])
    except Exception:
        pass

    # سرتیتر اخبار اسکرپ‌شده
    try:
        from ..scraping.scraper import collect_scraped_context
        news = collect_scraped_context(db, max_chars=600)
        if news:
            lines.append("")
            lines.append("📰 <b>از اخبار:</b>")
            lines.append(news[:600])
    except Exception:
        pass

    lines.append("")
    lines.append("— کانال رسمی NEXA AI")
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
