"""اسکرپر قابل‌تنظیم: هر سایتی را با CSS selector استخراج می‌کند."""
import asyncio
import httpx
from datetime import datetime
from bs4 import BeautifulSoup
from ..config import settings

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "fa,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


def _is_feed(url: str, html: str) -> bool:
    head = (html or "")[:600].lower()
    return ("<rss" in head or "<feed" in head or "<?xml" in head) or url.rstrip("/").endswith(("feed", "rss", ".xml"))


def _parse_feed(html: str, max_items: int):
    """خوراک RSS/Atom را پارس می‌کند و آیتم‌های تازه را برمی‌گرداند (عنوان + خلاصه + لینک)."""
    soup = BeautifulSoup(html, "html.parser")
    nodes = soup.find_all("item") or soup.find_all("entry")
    out = []
    for n in nodes[:max_items]:
        title = n.find("title")
        title = title.get_text(" ", strip=True) if title else ""
        desc = n.find("description") or n.find("summary") or n.find("content")
        desc = BeautifulSoup(desc.get_text(" ", strip=True), "html.parser").get_text(" ", strip=True) if desc else ""
        link = n.find("link")
        href = (link.get("href") or link.get_text(strip=True)) if link else ""
        text = title if not desc else f"{title} — {desc[:300]}"
        if text.strip():
            out.append({"url": href or title, "text": text.strip()})
    return out


def _discover_feed(html: str, base_url: str):
    """آدرس فید RSS/Atom را از <link> داخل صفحه پیدا می‌کند یا مسیرهای رایج را امتحان می‌کند."""
    from urllib.parse import urljoin
    try:
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.find_all("link"):
            t = (link.get("type") or "").lower()
            if ("rss" in t or "atom" in t or "xml" in t) and link.get("href"):
                return urljoin(base_url, link.get("href"))
    except Exception:
        pass
    return None


def _feed_result(html: str, source, persist: bool, max_items: int) -> str:
    """منطق مشترک پردازش فید (تست/ذخیره)."""
    feed_items = _parse_feed(html, max_items if persist else 5)
    seen = set(getattr(source, "seen_urls", None) or []) if persist else set()
    new_items = [it for it in feed_items if it["url"] not in seen]
    if persist:
        items = (getattr(source, "items", None) or []) + new_items
        items = items[-50:]
        source.items = items
        source.seen_urls = (list(seen) + [it["url"] for it in new_items])[-300:]
        shown = list(reversed(items[-15:]))  # تازه‌ترین‌ها بالا
        source.last_value = "\n".join(i["text"] for i in shown)[:3000]
        return f"{len(new_items)} مطلب جدید"
    return "\n".join(i["text"] for i in feed_items)[:3000] or "(آیتمی در خوراک یافت نشد)"


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


def _extract_from_soup(soup, selector: str, max_chars: int = 800) -> str:
    if not selector:
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        return soup.get_text(" ", strip=True)[:max_chars]
    els = soup.select(selector)
    parts = [e.get_text(" ", strip=True) for e in els[:30] if e.get_text(strip=True)]
    return " | ".join(parts)[:max_chars]


async def _fetch_html(url: str, use_proxy: bool = False, timeout: float = 25) -> str:
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    async with httpx.AsyncClient(timeout=timeout, proxy=proxy, follow_redirects=True,
                                 headers=_HEADERS, trust_env=False) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.text


async def _fetch_smart(url: str, prefer_proxy: bool, timeout: float = 25) -> str:
    """ابتدا با مسیر دلخواه تلاش می‌کند؛ اگر خطا/۵۰۳ گرفت، مسیر دیگر (پروکسی↔مستقیم) را امتحان می‌کند.
    این باعث می‌شود هم سایت‌های ایرانی (مستقیم) و هم خارجی (پروکسی) کار کنند."""
    last = None
    for up in (prefer_proxy, not prefer_proxy):
        try:
            return await _fetch_html(url, up, timeout=timeout)
        except Exception as e:
            last = e
    raise last if last else Exception("fetch failed")


async def scrape_source(source, persist: bool = False) -> str:
    """منبع را اسکرپ می‌کند. دوسطحی + عدم تکرار + محدودیت تعداد + جمع‌آوری تجمعی."""
    from urllib.parse import urljoin
    fields = getattr(source, "fields", None) or []
    link_sel = getattr(source, "link_selector", "") or ""
    max_items = getattr(source, "max_items", 5) or 5
    # در حالت تست (persist=False) سریع‌تر باش تا کاربر منتظر نماند
    if not persist:
        max_items = min(max_items, 3)
    item_timeout = 15.0

    html = await _fetch_smart(source.url, source.use_proxy)

    # ── خوراک RSS/Atom (تازه‌ترین اخبار، بدون نیاز به جاوااسکریپت) ──
    if _is_feed(source.url, html):
        return _feed_result(html, source, persist, max_items)

    # ── اگر رسپی‌ای تعریف نشده، خودکار فید سایت را پیدا و استفاده کن ──
    has_recipe = bool(link_sel and fields) or bool(getattr(source, "selector", "") or "")
    if not has_recipe:
        feed_url = _discover_feed(html, source.url)
        if feed_url:
            try:
                fh = await _fetch_smart(feed_url, source.use_proxy, timeout=item_timeout)
                if _is_feed(feed_url, fh):
                    return _feed_result(fh, source, persist, max_items)
            except Exception:
                pass

    soup = BeautifulSoup(html, "html.parser")

    # ── اسکرپ دوسطحی ──
    if link_sel and fields:
        anchors = soup.select(link_sel)
        all_urls = []
        for a in anchors:
            href = a.get("href") or (a.find("a") and a.find("a").get("href"))
            if href:
                all_urls.append(urljoin(source.url, href))
        all_urls = list(dict.fromkeys(all_urls))

        seen = set(getattr(source, "seen_urls", None) or []) if persist else set()
        new_urls = [u for u in all_urls if u not in seen][:max_items]

        # دریافت همه‌ی مطلب‌ها به‌صورت هم‌زمان (به‌جای سریالی) تا سریع باشد
        async def _fetch_one(u):
            try:
                return u, await _fetch_html(u, source.use_proxy, timeout=item_timeout)
            except Exception:
                return u, None

        results = await asyncio.gather(*[_fetch_one(u) for u in new_urls])

        new_items = []
        for u, h in results:
            if not h:
                continue
            s2 = BeautifulSoup(h, "html.parser")
            parts = []
            for f in fields:
                val = _extract_from_soup(s2, f.get("selector", ""), 400)
                if val:
                    parts.append(f"{f.get('name', 'فیلد')}: {val}")
            if parts:
                new_items.append({"url": u, "text": " — ".join(parts)})

        if persist:
            items = (getattr(source, "items", None) or []) + new_items
            items = items[-50:]  # نگه‌داری ۵۰ مطلب آخر
            source.items = items
            source.seen_urls = (list(seen) + new_urls)[-300:]
            source.last_value = "\n".join(i["text"] for i in items[-15:])[:3000]
            return f"{len(new_items)} مطلب جدید"
        # حالت تست: همین چند مطلب تازه را نشان بده
        return "\n".join(i["text"] for i in new_items)[:3000] or "(مطلب جدیدی یافت نشد)"

    # ── تک‌سطحی ──
    if fields:
        parts = []
        for f in fields:
            val = _extract_from_soup(soup, f.get("selector", ""), 500)
            if val:
                parts.append(f"[{f.get('name', 'فیلد')}]: {val}")
        result = "\n".join(parts)[:2000]
    else:
        result = _extract_from_soup(soup, source.selector or "", 1200)
    if persist:
        source.last_value = result
    return result


async def analyze_page(url: str, use_proxy: bool = False) -> list:
    """صفحه را تحلیل می‌کند و گروه‌های قابل‌انتخاب (عناوین، محتوا، جدول‌ها و...) را برمی‌گرداند."""
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    async with httpx.AsyncClient(timeout=25, proxy=proxy, follow_redirects=True,
                                 headers=_HEADERS, trust_env=False) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    def samples(els, n=4):
        out = []
        for e in els:
            txt = e.get_text(" ", strip=True)
            if txt and len(txt) > 3:
                out.append(txt[:120])
            if len(out) >= n:
                break
        return out

    groups = []

    # عناوین / تیترها
    heads = soup.select("h1, h2, h3, article a, .title")
    heads = [e for e in heads if e.get_text(strip=True)]
    if heads:
        groups.append({"label": "عناوین و تیترها", "selector": "h1, h2, h3, article a, .title",
                       "count": len(heads), "samples": samples(heads)})

    # محتوا / پاراگراف‌ها
    paras = [e for e in soup.select("p") if len(e.get_text(strip=True)) > 30]
    if paras:
        groups.append({"label": "محتوا و پاراگراف‌ها", "selector": "p",
                       "count": len(paras), "samples": samples(paras)})

    # لینک‌های خبری
    links = [a for a in soup.select("a") if len(a.get_text(strip=True)) > 15]
    if links:
        groups.append({"label": "لینک‌ها و اخبار", "selector": "a",
                       "count": len(links), "samples": samples(links)})

    # جدول‌ها
    tables = soup.find_all("table")
    if tables:
        groups.append({"label": "جدول‌ها", "selector": "table",
                       "count": len(tables), "samples": samples(tables, 2)})

    # آیتم‌های لیست
    lis = [e for e in soup.select("li") if len(e.get_text(strip=True)) > 10]
    if lis:
        groups.append({"label": "آیتم‌های لیست", "selector": "li",
                       "count": len(lis), "samples": samples(lis)})

    return groups


async def scrape_all(db, respect_schedule: bool = False) -> int:
    """همه منابع فعال را اسکرپ و ذخیره می‌کند. respect_schedule=True فقط منابع سررسیدشده."""
    from .. import models
    sources = db.query(models.ScrapeSource).filter(models.ScrapeSource.enabled == True).all()
    now = datetime.utcnow()
    ok = 0
    for s in sources:
        if respect_schedule and s.last_scraped:
            interval = (s.interval_minutes or 60)
            if (now - s.last_scraped).total_seconds() < interval * 60:
                continue  # هنوز زمانش نرسیده
        try:
            await scrape_source(s, persist=True)
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
