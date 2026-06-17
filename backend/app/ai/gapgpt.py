import httpx
from openai import AsyncOpenAI
from typing import List, Dict, AsyncGenerator, Optional
from ..config import settings


def get_ai_config(db=None) -> Dict[str, str]:
    """کلید و مدل AI را اول از دیتابیس می‌خواند، اگر نبود از .env."""
    api_key = settings.GAPGPT_API_KEY
    model = settings.GAPGPT_MODEL
    if db is not None:
        from .. import models
        s = db.query(models.SystemSettings).first()
        if s:
            if s.gapgpt_api_key:
                api_key = s.gapgpt_api_key
            if s.gapgpt_model:
                model = s.gapgpt_model
    return {"api_key": api_key, "model": model}


def make_client(api_key: str, timeout: float = 60.0) -> AsyncOpenAI:
    """کلاینت گپ‌جی‌پی‌تی را می‌سازد و در صورت تنظیم بودن، از پروکسی استفاده می‌کند."""
    http_client = None
    if settings.GAPGPT_PROXY:
        http_client = httpx.AsyncClient(proxy=settings.GAPGPT_PROXY, timeout=timeout)
    return AsyncOpenAI(
        api_key=api_key or "placeholder",
        base_url=settings.GAPGPT_BASE_URL,
        timeout=timeout,
        http_client=http_client,
    )

SYSTEM_PROMPT_FA = """تو دستیار هوش مصنوعی سیستم معاملاتی NEXA AI هستی.
وظایف تو:
- تحلیل بازار ارزهای دیجیتال و ارائه سیگنال‌های معاملاتی
- کمک به بهینه‌سازی استراتژی معاملاتی کاربر
- تفسیر نتایج مدل یادگیری ماشین
- پاسخ به سوالات تخصصی حوزه رمزارز
- ارائه تحلیل‌های تکنیکال و فاندامنتال

همیشه به فارسی پاسخ بده. در تحلیل‌هایت دقیق، مختصر و عملی باش.
هرگز تضمین سود ندهی و ریسک‌های معاملاتی را یادآوری کن."""


def get_ai_client(db=None) -> AsyncOpenAI:
    cfg = get_ai_config(db)
    return make_client(cfg["api_key"])


async def get_ai_response(messages: List[Dict[str, str]], stream: bool = False, db=None) -> str:
    cfg = get_ai_config(db)
    client = make_client(cfg["api_key"])
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT_FA}] + messages

    if stream:
        return  # handled separately

    response = await client.chat.completions.create(
        model=cfg["model"],
        messages=full_messages,
        temperature=0.7,
        max_tokens=1000,
    )
    return response.choices[0].message.content


async def stream_ai_response(messages: List[Dict[str, str]], db=None) -> AsyncGenerator[str, None]:
    cfg = get_ai_config(db)
    client = make_client(cfg["api_key"])
    full_messages = [{"role": "system", "content": SYSTEM_PROMPT_FA}] + messages

    stream = await client.chat.completions.create(
        model=cfg["model"],
        messages=full_messages,
        temperature=0.7,
        max_tokens=1000,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def analyze_market_for_trade(
    symbol: str,
    current_price: float,
    ohlcv_data: list,
    strategy: dict,
    db=None,
) -> Dict:
    prompt = f"""تحلیل معامله برای {symbol}:
- قیمت فعلی: {current_price}
- استراتژی: سود هدف {strategy.get('target_profit')}%، حد ضرر {strategy.get('stop_loss')}%
- نوع بازار: {strategy.get('market_type', 'اسپات')}

بر اساس داده‌های OHLCV اخیر (آرایه {len(ohlcv_data)} کندل)، آیا باید:
1. خرید (BUY)
2. فروش (SELL)
3. صبر (WAIT)

فقط یکی از این سه گزینه را با توضیح کوتاه بنویس."""

    response = await get_ai_response([{"role": "user", "content": prompt}], db=db)

    signal = "WAIT"
    if "خرید" in response or "BUY" in response.upper():
        signal = "BUY"
    elif "فروش" in response or "SELL" in response.upper():
        signal = "SELL"

    return {"signal": signal, "analysis": response}
