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


@app.get("/")
async def root():
    return {"message": "NEXA AI Trader API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "ok"}
