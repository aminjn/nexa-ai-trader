from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    phone = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=True)
    full_name = Column(String, default="کاربر جدید")
    is_active = Column(Boolean, default=True)
    is_superadmin = Column(Boolean, default=False)
    bot_active = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Trading settings
    target_profit = Column(Float, default=3.5)
    trades_per_day = Column(Integer, default=30)
    capital_pct = Column(Float, default=80.0)
    stop_loss = Column(Float, default=1.5)
    market_type = Column(String, default="spot")
    short_enabled = Column(Boolean, default=False)
    leverage = Column(Integer, default=3)
    ai_trading_enabled = Column(Boolean, default=True)
    # خروج زودهنگام با سیگنال فروش ML (اگر خاموش باشد فقط سود هدف/حد ضرر اعمال می‌شود)
    ml_exit_enabled = Column(Boolean, default=False)
    # ارزهایی که ربات روی آن‌ها معامله می‌کند (با کاما)
    trading_coins = Column(String, default="BTC,ETH,XRP,ADA,DOGE,LTC,TRX,BCH,BNB,SOL,DOT,AVAX,MATIC,SHIB,LINK,UNI,ATOM,FIL,ETC,XLM")
    # درصد کارمزد نوبیتکس برای هر طرف معامله (تیکر بازار تومانی، سطح پایه = ۰.۲۵٪) — در محاسبه سود/ضرر لحاظ می‌شود
    fee_pct = Column(Float, default=0.25)

    # شناسه‌های پیام‌رسان برای دریافت سیگنال (هر کاربر آی‌دی عددی خودش را وصل می‌کند)
    telegram_chat_id = Column(String, default="")
    bale_chat_id = Column(String, default="")
    link_code = Column(String, default="", index=True)  # کد اتصال خودکار ربات (/start CODE)

    exchanges = relationship("ExchangeAPI", back_populates="user", cascade="all, delete-orphan")
    trades = relationship("Trade", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")


class ExchangeAPI(Base):
    __tablename__ = "exchange_apis"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exchange_name = Column(String)  # nobitex, binance, etc.
    api_key = Column(String)
    api_secret = Column(String)
    is_primary = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    balance = Column(Float, default=0.0)
    last_sync = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="exchanges")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    exchange = Column(String)
    pair = Column(String)
    side = Column(String)  # buy/sell/long/short
    entry_price = Column(Float)
    exit_price = Column(Float, nullable=True)
    amount = Column(Float)
    pnl = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    status = Column(String, default="open")  # open/closed
    trade_type = Column(String, default="spot")  # spot/futures
    leverage = Column(Integer, default=1)
    order_id = Column(String, nullable=True)
    ai_assisted = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="trades")


class MLModel(Base):
    __tablename__ = "ml_models"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="NexaML v1")
    version = Column(String, default="1.0.0")
    status = Column(String, default="idle")  # idle/training/ready
    accuracy = Column(Float, default=0.0)
    loss = Column(Float, default=0.0)
    epochs_done = Column(Integer, default=0)
    total_epochs = Column(Integer, default=100)
    training_data_days = Column(Integer, default=1825)  # 5 years
    features = Column(JSON, default=list)
    feature_importances = Column(JSON, default=list)  # [{name, importance}]
    metrics = Column(JSON, default=dict)  # precision, recall, samples, date range, source
    ai_explanation = Column(Text, default="")  # توضیح هوش مصنوعی از آموخته‌های مدل
    data_source = Column(String, default="")
    model_path = Column(String, nullable=True)
    last_trained = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    role = Column(String)  # user/assistant
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="chat_messages")


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    max_profit_per_trade = Column(Float, default=5.0)
    max_trades_per_day = Column(Integer, default=120)
    max_leverage = Column(Integer, default=10)
    platform_fee_pct = Column(Float, default=10.0)
    auto_approve_users = Column(Boolean, default=True)
    require_kyc = Column(Boolean, default=False)
    allow_short = Column(Boolean, default=True)
    allow_futures = Column(Boolean, default=True)
    maintenance_mode = Column(Boolean, default=False)
    # AI / GapGPT configuration (set from super admin panel, persisted)
    gapgpt_api_key = Column(String, default="")
    gapgpt_model = Column(String, default="gpt-4o")
    # تنظیمات فروش سیگنال (از پنل سوپر ادمین)
    telegram_bot_token = Column(String, default="")
    bale_bot_token = Column(String, default="")
    zarinpal_merchant_id = Column(String, default="")
    signal_coins = Column(String, default="BTC,ETH")     # ارزهای تولید سیگنال (با کاما)
    signal_interval_minutes = Column(Integer, default=30)  # هر چند دقیقه سیگنال تولید شود
    # انتشار خودکار محتوا در کانال عمومی
    telegram_channel_id = Column(String, default="")     # @channel یا آی‌دی عددی
    bale_channel_id = Column(String, default="")
    telegram_bot_username = Column(String, default="")   # برای راهنمای اتصال (@MyBot)
    bale_bot_username = Column(String, default="")
    content_interval_hours = Column(Integer, default=6)  # هر چند ساعت محتوا منتشر شود
    ad_interval_hours = Column(Integer, default=12)       # هر چند ساعت تبلیغ منتشر شود
    ad_text = Column(Text, default="")                    # متن تبلیغ دستی (اگر خالی باشد هوش مصنوعی می‌سازد)
    # زمان آخرین اجرای خودکار (ماندگار، مستقل از ری‌استارت)
    last_signal_at = Column(DateTime, nullable=True)
    last_content_at = Column(DateTime, nullable=True)
    last_ad_at = Column(DateTime, nullable=True)
    # پشتیبانی هوش مصنوعی داخل ربات + اطلاعات پرداخت کارت‌به‌کارت
    ai_support_enabled = Column(Boolean, default=True)
    card_number = Column(String, default="")
    card_holder = Column(String, default="")
    account_number = Column(String, default="")   # شماره حساب / شبا
    support_contact = Column(String, default="")  # آی‌دی ادمین برای ارسال رسید (@admin)
    # ورود با پیامک (IPPanel — Edge API)
    ippanel_token = Column(String, default="")          # توکن/کلید Authorization
    ippanel_pattern_code = Column(String, default="")   # کد الگوی پیامک کد تأیید
    ippanel_from_number = Column(String, default="")    # شمارهٔ فرستنده (مثلاً +983000505)
    ippanel_param_name = Column(String, default="code") # نام متغیر کد در الگو
    sms_login_enabled = Column(Boolean, default=False)  # ارسال واقعی پیامک فعال است؟
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)   # free / pro / vip
    name = Column(String)                            # نام نمایشی فارسی
    level = Column(Integer, default=0)               # 0=رایگان 1=حرفه‌ای 2=VIP (برای دسترسی سطحی)
    price_toman = Column(Integer, default=0)
    duration_days = Column(Integer, default=30)
    max_coins = Column(Integer, default=1)           # چند ارز را می‌بیند/می‌گیرد
    delay_minutes = Column(Integer, default=60)      # تأخیر دریافت سیگنال (برای رایگان)
    include_analysis = Column(Boolean, default=False)  # متن تحلیل کامل دارد؟
    channels = Column(JSON, default=list)            # ['telegram','bale','inapp']
    description = Column(Text, default="")
    active = Column(Boolean, default=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    plan_id = Column(Integer, ForeignKey("plans.id"))
    status = Column(String, default="pending")   # pending/active/expired/rejected
    payment_method = Column(String, default="manual")  # manual/online
    amount_toman = Column(Integer, default=0)
    ref_id = Column(String, default="")          # authority/مرجع پرداخت
    note = Column(String, default="")
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class TradingPlan(Base):
    """پلن دسترسی به ربات معامله‌گر (جدا از پلن سیگنال).

    دو نوع:
    - self_api: کاربر کلید API نوبیتکس خودش را وصل می‌کند؛ تعداد معاملهٔ روزانه محدود؛ هزینهٔ ثابت.
    - managed: کاربر پول را به حساب نوبیتکسِ ما واریز می‌کند؛ ما معامله می‌کنیم؛
      کارمزد درصدی بر اساس مبلغ واریزی (پله‌ای) از سود گرفته می‌شود.
    """
    __tablename__ = "trading_plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)                              # نام نمایشی فارسی
    plan_type = Column(String, default="self_api")     # self_api | managed
    duration_days = Column(Integer, default=30)        # طول اعتبار پلن
    price_toman = Column(Integer, default=0)           # هزینهٔ اشتراک (کارت‌به‌کارت به ما)
    max_trades_per_day = Column(Integer, default=0)    # سقف معاملهٔ روزانه (۰ = نامحدود)
    allow_own_api = Column(Boolean, default=True)      # کاربر API خودش را وصل کند؟
    # پله‌های کارمزدِ سود بر اساس مبلغ واریزی (برای managed):
    # [{"min_toman": 100000000, "pct": 10}, {"min_toman": 0, "pct": 20}]
    commission_tiers = Column(JSON, default=list)
    description = Column(Text, default="")
    features = Column(JSON, default=list)              # لیست امکانات (نمایشی)
    active = Column(Boolean, default=True)
    sort = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class TradingSubscription(Base):
    """اشتراک ربات معامله‌گر برای هر کاربر."""
    __tablename__ = "trading_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    plan_id = Column(Integer, ForeignKey("trading_plans.id"))
    status = Column(String, default="pending")          # pending | active | expired | rejected
    deposit_toman = Column(Integer, default=0)          # مبلغ واریزی کاربر (managed — ادمین ثبت می‌کند)
    commission_settled_toman = Column(Integer, default=0)  # کارمزد سود تسویه‌شده تا کنون
    note = Column(String, default="")
    start_at = Column(DateTime, nullable=True)
    end_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    coin = Column(String, index=True)            # BTC, ETH, ...
    side = Column(String)                         # BUY / SELL / WAIT
    confidence = Column(Float, default=0.0)       # 0..1
    entry_price = Column(Float, default=0.0)      # تومان
    target_price = Column(Float, default=0.0)
    stop_price = Column(Float, default=0.0)
    timeframe = Column(String, default="1h")
    tech_conclusion = Column(String, default="")
    fund_conclusion = Column(String, default="")
    analysis = Column(Text, default="")           # متن کامل (برای پلن‌های شامل تحلیل)
    min_level = Column(Integer, default=0)         # حداقل سطح پلن برای دیدن این سیگنال
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String, index=True)
    code = Column(String)
    expires_at = Column(DateTime)
    used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ScrapeSource(Base):
    __tablename__ = "scrape_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)            # نام منبع (مثلاً «اخبار ارزدیجیتال»)
    url = Column(String)             # آدرس سایت
    selector = Column(String, default="")  # CSS selector (حالت تک‌فیلدی قدیمی)
    link_selector = Column(String, default="")  # selector لینک‌ها (برای اسکرپ دوسطحی)
    fields = Column(JSON, default=list)     # [{name, selector}] فیلدهای محتوا
    use_proxy = Column(Boolean, default=False)  # برای سایت‌های خارجی
    max_items = Column(Integer, default=5)       # چند مطلب در هر بار
    interval_minutes = Column(Integer, default=60)  # هر چند دقیقه اسکرپ شود
    seen_urls = Column(JSON, default=list)       # URLهای دیده‌شده (جلوگیری از تکرار)
    items = Column(JSON, default=list)           # مطالب جمع‌آوری‌شده
    enabled = Column(Boolean, default=True)
    last_value = Column(Text, default="")
    last_scraped = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
