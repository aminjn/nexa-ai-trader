"""زمان‌بند واحد و ماندگار برای سیگنال، محتوا، تبلیغ و اسکرپ.

زمان آخرین اجرای هر کار در دیتابیس ذخیره می‌شود (SystemSettings)، پس با
ری‌استارت سرور صفر نمی‌شود و زمان‌بندی دقیق و پایدار می‌ماند.
"""
import asyncio
from datetime import datetime
from ..database import SessionLocal
from .. import models


async def _run(label, coro):
    try:
        await coro
    except Exception as e:
        print(f"⚠️ scheduler {label}: {e}")


async def scheduler_loop():
    await asyncio.sleep(15)  # کمی صبر تا برنامه کامل بالا بیاید
    try:
        from ..trading.bot import log_bot_event
    except Exception:
        def log_bot_event(*a, **k):
            pass

    while True:
        db = SessionLocal()
        try:
            s = db.query(models.SystemSettings).first()
            if s:
                now = datetime.utcnow()

                # ── تولید و ارسال سیگنال ──
                iv = max(1, (s.signal_interval_minutes or 30)) * 60
                if not s.last_signal_at or (now - s.last_signal_at).total_seconds() >= iv:
                    s.last_signal_at = now
                    db.commit()
                    from .engine import generate_signals
                    n = 0
                    try:
                        n = await generate_signals(db, push=True)
                    except Exception as e:
                        print(f"⚠️ scheduler signal: {e}")
                    log_bot_event(f"📡 {n} سیگنال خودکار تولید و ارسال شد (هر {s.signal_interval_minutes} دقیقه)")

                # ── انتشار محتوای تحلیلی ──
                iv = max(1, (s.content_interval_hours or 6)) * 3600
                if not s.last_content_at or (now - s.last_content_at).total_seconds() >= iv:
                    s.last_content_at = now
                    db.commit()
                    from .content import publish_content
                    await _run("content", publish_content(db))
                    log_bot_event(f"📝 محتوای تحلیلی خودکار منتشر شد (هر {s.content_interval_hours} ساعت)")

                # ── انتشار تبلیغ ──
                iv = max(1, (s.ad_interval_hours or 12)) * 3600
                if not s.last_ad_at or (now - s.last_ad_at).total_seconds() >= iv:
                    s.last_ad_at = now
                    db.commit()
                    from .content import publish_ad
                    await _run("ad", publish_ad(db))
                    log_bot_event(f"📣 تبلیغ خودکار منتشر شد (هر {s.ad_interval_hours} ساعت)")

            # ── اسکرپ خودکار منابع (هر منبع طبق بازه‌ی خودش، ماندگار با last_scraped) ──
            from ..scraping.scraper import scrape_all
            await _run("scrape", scrape_all(db, respect_schedule=True))
        except Exception as e:
            print(f"⚠️ scheduler loop: {e}")
        finally:
            db.close()

        await asyncio.sleep(60)  # هر دقیقه بررسی می‌کند چه کاری سررسید شده
