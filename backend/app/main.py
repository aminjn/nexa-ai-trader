from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from .database import engine, Base
from . import models
from .auth.router import router as auth_router
from .api.dashboard import router as dashboard_router
from .api.strategy import router as strategy_router
from .api.exchanges import router as exchanges_router
from .api.history import router as history_router
from .api.model_api import router as model_router
from .api.ai_api import router as ai_router
from .api.admin import router as admin_router
from .api.scraper_api import router as scraper_router
from .api.signals_api import router as signals_router
from .api.trading_plans import router as trading_plans_router
from .api.profile import router as profile_router
from .api.wallet import router as wallet_router
from .api.notifications import router as notifications_router
from .auth.service import create_user, get_user_by_email
from .database import SessionLocal
from .config import settings
from sqlalchemy import inspect, text


def ensure_columns():
    """ستون‌های جدید را به جدول‌های موجود اضافه می‌کند (migration سبک برای SQLite)."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    # system_settings: ستون‌های مربوط به هوش مصنوعی
    if "system_settings" in tables:
        cols = {c["name"] for c in inspector.get_columns("system_settings")}
        with engine.begin() as conn:
            if "gapgpt_api_key" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN gapgpt_api_key VARCHAR DEFAULT ''"))
            if "gapgpt_model" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN gapgpt_model VARCHAR DEFAULT 'gpt-4o'"))
            if "telegram_bot_token" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN telegram_bot_token VARCHAR DEFAULT ''"))
            if "bale_bot_token" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN bale_bot_token VARCHAR DEFAULT ''"))
            if "zarinpal_merchant_id" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN zarinpal_merchant_id VARCHAR DEFAULT ''"))
            if "signal_coins" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN signal_coins VARCHAR DEFAULT 'BTC,ETH'"))
            if "signal_interval_minutes" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN signal_interval_minutes INTEGER DEFAULT 30"))
            if "telegram_channel_id" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN telegram_channel_id VARCHAR DEFAULT ''"))
            if "bale_channel_id" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN bale_channel_id VARCHAR DEFAULT ''"))
            if "telegram_bot_username" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN telegram_bot_username VARCHAR DEFAULT ''"))
            if "bale_bot_username" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN bale_bot_username VARCHAR DEFAULT ''"))
            if "content_interval_hours" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN content_interval_hours INTEGER DEFAULT 6"))
            if "ad_interval_hours" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ad_interval_hours INTEGER DEFAULT 12"))
            if "ad_text" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ad_text TEXT DEFAULT ''"))
            if "last_signal_at" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN last_signal_at DATETIME"))
            if "last_content_at" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN last_content_at DATETIME"))
            if "last_ad_at" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN last_ad_at DATETIME"))
            if "ai_support_enabled" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ai_support_enabled BOOLEAN DEFAULT 1"))
            if "card_number" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN card_number VARCHAR DEFAULT ''"))
            if "card_holder" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN card_holder VARCHAR DEFAULT ''"))
            if "account_number" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN account_number VARCHAR DEFAULT ''"))
            if "support_contact" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN support_contact VARCHAR DEFAULT ''"))
            if "ippanel_token" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ippanel_token VARCHAR DEFAULT ''"))
            if "ippanel_pattern_code" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ippanel_pattern_code VARCHAR DEFAULT ''"))
            if "ippanel_from_number" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ippanel_from_number VARCHAR DEFAULT ''"))
            if "ippanel_param_name" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN ippanel_param_name VARCHAR DEFAULT 'code'"))
            if "sms_login_enabled" not in cols:
                conn.execute(text("ALTER TABLE system_settings ADD COLUMN sms_login_enabled BOOLEAN DEFAULT 0"))
    # users: شناسه‌های پیام‌رسان
    if "users" in tables:
        cols = {c["name"] for c in inspector.get_columns("users")}
        with engine.begin() as conn:
            if "telegram_chat_id" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN telegram_chat_id VARCHAR DEFAULT ''"))
            if "bale_chat_id" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN bale_chat_id VARCHAR DEFAULT ''"))
            if "link_code" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN link_code VARCHAR DEFAULT ''"))
            if "ml_exit_enabled" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN ml_exit_enabled BOOLEAN DEFAULT 0"))
            if "trading_coins" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN trading_coins VARCHAR DEFAULT 'BTC,ETH,XRP,ADA,DOGE,LTC,TRX,BCH,BNB,SOL,DOT,AVAX,MATIC,SHIB,LINK,UNI,ATOM,FIL,ETC,XLM'"))
            if "fee_pct" not in cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN fee_pct FLOAT DEFAULT 0.25"))
            # پروفایل / احراز هویت / کیف پول
            for col, ddl in [
                ("national_id", "VARCHAR DEFAULT ''"),
                ("birth_date", "VARCHAR DEFAULT ''"),
                ("avatar", "TEXT DEFAULT ''"),
                ("kyc_status", "VARCHAR DEFAULT 'none'"),
                ("kyc_card_image", "TEXT DEFAULT ''"),
                ("kyc_selfie_image", "TEXT DEFAULT ''"),
                ("kyc_video", "TEXT DEFAULT ''"),
                ("kyc_challenge", "VARCHAR DEFAULT ''"),
                ("kyc_match_score", "FLOAT DEFAULT 0.0"),
                ("kyc_note", "TEXT DEFAULT ''"),
                ("kyc_submitted_at", "DATETIME"),
                ("wallet_balance_toman", "INTEGER DEFAULT 0"),
            ]:
                if col not in cols:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {ddl}"))
    # exchange_apis: علامت حساب استخر مدیریت‌شده
    if "exchange_apis" in tables:
        cols = {c["name"] for c in inspector.get_columns("exchange_apis")}
        with engine.begin() as conn:
            if "is_pool" not in cols:
                conn.execute(text("ALTER TABLE exchange_apis ADD COLUMN is_pool BOOLEAN DEFAULT 0"))
    # trading_subscriptions: واحدهای استخر (برای دیتابیس‌هایی که جدول قبلاً ساخته شده)
    if "trading_subscriptions" in tables:
        cols = {c["name"] for c in inspector.get_columns("trading_subscriptions")}
        with engine.begin() as conn:
            if "units" not in cols:
                conn.execute(text("ALTER TABLE trading_subscriptions ADD COLUMN units FLOAT DEFAULT 0.0"))
    # trading_plans: فیلدهای جدیدِ قابل‌تنظیم
    if "trading_plans" in tables:
        cols = {c["name"] for c in inspector.get_columns("trading_plans")}
        with engine.begin() as conn:
            if "ai_chat_daily_limit" not in cols:
                conn.execute(text("ALTER TABLE trading_plans ADD COLUMN ai_chat_daily_limit INTEGER DEFAULT 0"))
            if "signals_level" not in cols:
                conn.execute(text("ALTER TABLE trading_plans ADD COLUMN signals_level INTEGER DEFAULT 0"))
            if "signals_delay_minutes" not in cols:
                conn.execute(text("ALTER TABLE trading_plans ADD COLUMN signals_delay_minutes INTEGER DEFAULT 0"))
            if "signals_include_analysis" not in cols:
                conn.execute(text("ALTER TABLE trading_plans ADD COLUMN signals_include_analysis BOOLEAN DEFAULT 0"))
    # pool_withdrawals: مقادیر قفل‌شده در لحظهٔ درخواست
    if "pool_withdrawals" in tables:
        cols = {c["name"] for c in inspector.get_columns("pool_withdrawals")}
        with engine.begin() as conn:
            if "unit_price" not in cols:
                conn.execute(text("ALTER TABLE pool_withdrawals ADD COLUMN unit_price FLOAT DEFAULT 0.0"))
            if "gross_toman" not in cols:
                conn.execute(text("ALTER TABLE pool_withdrawals ADD COLUMN gross_toman INTEGER DEFAULT 0"))
            if "deposit_removed_toman" not in cols:
                conn.execute(text("ALTER TABLE pool_withdrawals ADD COLUMN deposit_removed_toman INTEGER DEFAULT 0"))
    # ml_models: ستون‌های جزئیات آموزش
    if "ml_models" in tables:
        cols = {c["name"] for c in inspector.get_columns("ml_models")}
        with engine.begin() as conn:
            if "feature_importances" not in cols:
                conn.execute(text("ALTER TABLE ml_models ADD COLUMN feature_importances JSON"))
            if "metrics" not in cols:
                conn.execute(text("ALTER TABLE ml_models ADD COLUMN metrics JSON"))
            if "ai_explanation" not in cols:
                conn.execute(text("ALTER TABLE ml_models ADD COLUMN ai_explanation TEXT DEFAULT ''"))
            if "data_source" not in cols:
                conn.execute(text("ALTER TABLE ml_models ADD COLUMN data_source VARCHAR DEFAULT ''"))
    # scrape_sources: ستون چندفیلدی
    if "scrape_sources" in tables:
        cols = {c["name"] for c in inspector.get_columns("scrape_sources")}
        with engine.begin() as conn:
            if "fields" not in cols:
                conn.execute(text("ALTER TABLE scrape_sources ADD COLUMN fields JSON"))
            if "link_selector" not in cols:
                conn.execute(text("ALTER TABLE scrape_sources ADD COLUMN link_selector VARCHAR DEFAULT ''"))
            if "max_items" not in cols:
                conn.execute(text("ALTER TABLE scrape_sources ADD COLUMN max_items INTEGER DEFAULT 5"))
            if "interval_minutes" not in cols:
                conn.execute(text("ALTER TABLE scrape_sources ADD COLUMN interval_minutes INTEGER DEFAULT 60"))
            if "seen_urls" not in cols:
                conn.execute(text("ALTER TABLE scrape_sources ADD COLUMN seen_urls JSON"))
            if "items" not in cols:
                conn.execute(text("ALTER TABLE scrape_sources ADD COLUMN items JSON"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    Base.metadata.create_all(bind=engine)

    # Migration سبک برای دیتابیس‌های قدیمی
    try:
        ensure_columns()
    except Exception as e:
        print(f"⚠️ migration warning: {e}")

    # Create super admin if not exists
    db = SessionLocal()
    try:
        if not get_user_by_email(db, settings.ADMIN_EMAIL):
            admin = create_user(
                db,
                email=settings.ADMIN_EMAIL,
                password=settings.ADMIN_PASSWORD,
                full_name="سوپر ادمین",
                is_superadmin=True,
            )
            # Create default ML model record
            ml = models.MLModel(name="NexaML v1", status="idle")
            db.add(ml)
            # Create default system settings
            sys_settings = models.SystemSettings()
            db.add(sys_settings)
            db.commit()
            print(f"✅ Admin created: {settings.ADMIN_EMAIL}")
    finally:
        db.close()

    # ساخت پلن‌های پیش‌فرض فروش سیگنال (اگر وجود نداشته باشند)
    db = SessionLocal()
    try:
        if db.query(models.Plan).count() == 0:
            db.add_all([
                models.Plan(key="free", name="رایگان", level=0, price_toman=0,
                            duration_days=3650, max_coins=1, delay_minutes=60,
                            include_analysis=False, channels=["inapp"],
                            description="سیگنال بیت‌کوین با تأخیر، فقط داخل پنل", sort=0),
                models.Plan(key="pro", name="حرفه‌ای", level=1, price_toman=290000,
                            duration_days=30, max_coins=5, delay_minutes=0,
                            include_analysis=False, channels=["telegram", "bale", "inapp"],
                            description="همه‌ی سیگنال‌های آنی روی ارزهای اصلی + تلگرام و بله", sort=1),
                models.Plan(key="vip", name="VIP", level=2, price_toman=690000,
                            duration_days=30, max_coins=20, delay_minutes=0,
                            include_analysis=True, channels=["telegram", "bale", "inapp"],
                            description="همه‌ی ارزها + تحلیل کامل فاندامنتال/تکنیکال + کانال اختصاصی", sort=2),
            ])
            db.commit()
            print("✅ Default plans created")
    except Exception as e:
        print(f"⚠️ plan seed warning: {e}")
    finally:
        db.close()

    # ساخت پلن‌های پیش‌فرض ربات معامله‌گر (اگر وجود نداشته باشند)
    db = SessionLocal()
    try:
        if db.query(models.TradingPlan).count() == 0:
            db.add_all([
                models.TradingPlan(
                    name="آزمایشی ۳ روزه", plan_type="self_api", duration_days=3,
                    price_toman=0, max_trades_per_day=5, allow_own_api=True,
                    commission_tiers=[], sort=0,
                    ai_chat_daily_limit=10, signals_level=0,
                    description="۳ روز معامله با ربات روی حساب خودتان (API شخصی)، حداکثر ۵ معامله در روز",
                    features=["اتصال API شخصی", "حداکثر ۵ معامله در روز", "چت هوش مصنوعی محدود", "اعتبار ۳ روزه"]),
                models.TradingPlan(
                    name="ماهانه کامل", plan_type="self_api", duration_days=30,
                    price_toman=10000000, max_trades_per_day=0, allow_own_api=True,
                    commission_tiers=[], sort=1,
                    ai_chat_daily_limit=100, signals_level=1, signals_include_analysis=True,
                    description="یک ماه دسترسی کامل با همهٔ امکانات روی حساب خودتان",
                    features=["اتصال API شخصی", "معاملهٔ نامحدود", "سیگنال + تحلیل", "چت هوش مصنوعی", "اعتبار ۳۰ روزه"]),
                models.TradingPlan(
                    name="مدیریت‌شده (VIP)", plan_type="managed", duration_days=30,
                    price_toman=0, max_trades_per_day=0, allow_own_api=False,
                    commission_tiers=[{"min_toman": 100000000, "pct": 10}, {"min_toman": 0, "pct": 20}],
                    sort=2,
                    ai_chat_daily_limit=100, signals_level=2, signals_include_analysis=True,
                    description="واریز به حساب ما و معاملهٔ ما به‌جای شما؛ کارمزد پله‌ای از سود (بالای ۱۰۰م: ۱۰٪، زیر آن: ۲۰٪)",
                    features=["واریز به حساب ما", "مدیریت کامل توسط NEXA", "کارمزد فقط از سود", "پله‌ای بر اساس واریزی"]),
            ])
            db.commit()
            print("✅ Default trading plans created")
    except Exception as e:
        print(f"⚠️ trading plan seed warning: {e}")
    finally:
        db.close()

    # راه‌اندازی مجدد ربات‌های فعال پس از ری‌استارت سرور
    db = SessionLocal()
    try:
        from .trading.bot import start_user_bot
        active_users = db.query(models.User).filter(models.User.bot_active == True).all()
        for u in active_users:
            start_user_bot(u.id)
            print(f"🤖 Bot resumed for user {u.id}")
    except Exception as e:
        print(f"⚠️ bot resume warning: {e}")
    finally:
        db.close()

    # آموزش خودکار دوره‌ای مدل (هر ۶ ساعت با داده جدید)
    import asyncio as _asyncio
    from .api.model_api import auto_retrain_loop
    _asyncio.create_task(auto_retrain_loop(6.0))

    # زمان‌بند واحد و ماندگار: سیگنال، محتوا، تبلیغ و اسکرپ (مستقل از ری‌استارت)
    from .signals.scheduler import scheduler_loop
    _asyncio.create_task(scheduler_loop())

    # اتصال خودکار ربات‌ها (long-polling) برای تلگرام و بله
    from .signals.bot_poller import telegram_poll_loop, bale_poll_loop
    _asyncio.create_task(telegram_poll_loop())
    _asyncio.create_task(bale_poll_loop())

    yield


app = FastAPI(
    title="NEXA AI Trader API",
    description="سیستم معاملاتی خودکار رمزارز با هوش مصنوعی",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(strategy_router)
app.include_router(exchanges_router)
app.include_router(history_router)
app.include_router(model_router)
app.include_router(ai_router)
app.include_router(admin_router)
app.include_router(scraper_router)
app.include_router(signals_router)
app.include_router(trading_plans_router)
app.include_router(profile_router)
app.include_router(wallet_router)
app.include_router(notifications_router)


@app.get("/")
async def root():
    return {"message": "NEXA AI Trader API", "version": "1.0.0", "status": "running"}


BUILD_VERSION = "2026-06-18-positions-toman-v2"


@app.get("/health")
async def health():
    return {"status": "ok", "build": BUILD_VERSION}
