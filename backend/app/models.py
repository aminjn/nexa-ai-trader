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
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    fields = Column(JSON, default=list)     # [{name, selector}] حالت چندفیلدی
    use_proxy = Column(Boolean, default=False)  # برای سایت‌های خارجی
    enabled = Column(Boolean, default=True)
    last_value = Column(Text, default="")
    last_scraped = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
