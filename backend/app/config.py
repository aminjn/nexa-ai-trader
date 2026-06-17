from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    SECRET_KEY: str = "nexa-trader-secret-key-2024-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    DATABASE_URL: str = "sqlite:///./nexa_trader.db"

    GAPGPT_API_KEY: str = ""
    GAPGPT_BASE_URL: str = "https://api.gapgpt.app/v1"
    GAPGPT_MODEL: str = "gpt-4o"
    # پروکسی برای دسترسی به گپ‌جی‌پی‌تی (مثلاً http://127.0.0.1:8889 یا socks5://...)
    GAPGPT_PROXY: str = ""

    ADMIN_EMAIL: str = "admin@nexa.ai"
    ADMIN_PASSWORD: str = "Admin@12345"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
