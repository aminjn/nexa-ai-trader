"""اسکرپر قابل‌تنظیم: هر سایتی را با CSS selector استخراج می‌کند."""
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from ..config import settings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "fa,en;q=0.9",
}


async def scrape_url(url: str, selector: str = "", use_proxy: bool = False, max_chars: int = 1200) -> str:
    """یک URL را می‌گیرد و متن المان‌های منطبق با selector را برمی‌گرداند."""
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    async with httpx.AsyncClient(timeout=25, proxy=proxy, follow_redirects=True,
                                 headers=_HEADERS, trust_env=False) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    if selector:
        els = soup.select(selector)
        parts = [e.get_text(" ", strip=True) for e in els[:30] if e.get_text(strip=True)]
        text = " | ".join(parts)
    else:
        # بدون selector: کل متن صفحه (محدود)
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
    return text[:max_chars].strip()


async def scrape_source(source) -> str:
    return await scrape_url(source.url, source.selector or "", source.use_proxy)


async def scrape_all(db) -> int:
    """همه منابع فعال را اسکرپ و در دیتابیس ذخیره می‌کند. تعداد موفق را برمی‌گرداند."""
    from .. import models
    sources = db.query(models.ScrapeSource).filter(models.ScrapeSource.enabled == True).all()
    ok = 0
    for s in sources:
        try:
            val = await scrape_source(s)
            s.last_value = val
            s.last_scraped = datetime.utcnow()
            ok += 1
        except Exception as e:
            s.last_value = f"خطا: {str(e)[:120]}"
            s.last_scraped = datetime.utcnow()
    db.commit()
    return ok


def collect_scraped_context(db, max_chars: int = 2000) -> str:
    """متن اسکرپ‌شده‌ی منابع فعال را برای تحلیل هوش مصنوعی جمع می‌کند."""
    from .. import models
    sources = db.query(models.ScrapeSource).filter(
        models.ScrapeSource.enabled == True
    ).all()
    chunks = []
    for s in sources:
        if s.last_value and not s.last_value.startswith("خطا"):
            chunks.append(f"[{s.name}]: {s.last_value}")
    return "\n".join(chunks)[:max_chars]
