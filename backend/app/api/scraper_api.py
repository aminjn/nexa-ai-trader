from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import httpx
from bs4 import BeautifulSoup
from .. import models
from ..database import get_db, SessionLocal
from ..auth.router import get_current_user
from ..auth.utils import decode_token
from ..auth import service as auth_service
from ..config import settings
from ..scraping.scraper import scrape_url, scrape_all, analyze_page

router = APIRouter(prefix="/scraper", tags=["scraper"])


_PICKER_JS = """
<style>* { cursor: crosshair !important; }
.nexa-hl { outline: 3px solid #4be0ff !important; outline-offset: -1px !important; background: rgba(75,224,255,0.12) !important; }</style>
<script>
(function(){
  function cssPath(el){
    if(!(el instanceof Element)) return '';
    var path=[];
    while(el && el.nodeType===1 && el.tagName.toLowerCase()!=='body' && el.tagName.toLowerCase()!=='html'){
      var sel=el.tagName.toLowerCase();
      if(el.id){ path.unshift('#'+el.id); break; }
      var cls=(el.className&&typeof el.className==='string')?el.className.trim().split(/\\s+/).filter(Boolean):[];
      if(cls.length){ sel+='.'+cls.slice(0,2).join('.'); }
      else { var i=1, sib=el; while(sib=sib.previousElementSibling){ if(sib.tagName===el.tagName) i++; } sel+=':nth-of-type('+i+')'; }
      path.unshift(sel); el=el.parentElement;
    }
    return path.join(' > ');
  }
  var hovered=null;
  document.addEventListener('mouseover',function(e){ if(hovered) hovered.classList.remove('nexa-hl'); hovered=e.target; if(hovered.classList) hovered.classList.add('nexa-hl'); },true);
  document.addEventListener('click',function(e){
    e.preventDefault(); e.stopPropagation();
    var sel=cssPath(e.target);
    var text=(e.target.innerText||e.target.textContent||'').trim().slice(0,150);
    var a=e.target.closest('a');
    var href=a?a.href:'';
    parent.postMessage({type:'nexa-pick', selector:sel, text:text, href:href}, '*');
    return false;
  },true);
  document.addEventListener('submit',function(e){ e.preventDefault(); },true);
})();
</script>
"""


def _check_token(token: str):
    payload = decode_token(token or "")
    if not payload:
        raise HTTPException(status_code=401, detail="توکن نامعتبر")
    db = SessionLocal()
    try:
        user = auth_service.get_user_by_id(db, int(payload.get("sub", 0)))
        if not user or not user.is_superadmin:
            raise HTTPException(status_code=403, detail="دسترسی مجاز نیست")
    finally:
        db.close()


@router.get("/proxy", response_class=HTMLResponse)
async def proxy_page(url: str = Query(...), token: str = Query(""), use_proxy: bool = Query(False)):
    """صفحه‌ی هدف را پروکسی و انتخابگر بصری تزریق می‌کند (برای نمایش در iframe)."""
    _check_token(token)
    proxy = settings.GAPGPT_PROXY if use_proxy else None
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
    try:
        async with httpx.AsyncClient(timeout=25, proxy=proxy, follow_redirects=True, headers=headers, trust_env=False) as c:
            resp = await c.get(url)
            html = resp.text
    except Exception as e:
        return HTMLResponse(f"<html dir='rtl'><body style='font-family:sans-serif;padding:40px;color:#c00'>خطا در بازکردن سایت: {str(e)[:200]}</body></html>")

    soup = BeautifulSoup(html, "html.parser")
    for s in soup(["script"]):
        s.decompose()
    # base href برای بارگذاری CSS/تصاویر
    if soup.head:
        base = soup.new_tag("base", href=url)
        soup.head.insert(0, base)
    # تزریق انتخابگر
    target = soup.body or soup
    picker = BeautifulSoup(_PICKER_JS, "html.parser")
    target.append(picker)
    return HTMLResponse(str(soup))



class FieldItem(BaseModel):
    name: str
    selector: str


class SourceRequest(BaseModel):
    name: str
    url: str
    selector: str = ""
    link_selector: str = ""
    fields: list[FieldItem] = []
    use_proxy: bool = False
    enabled: bool = True


class TestRequest(BaseModel):
    url: str
    selector: str = ""
    use_proxy: bool = False


def _admin(user: models.User):
    if not user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین")


@router.get("/sources")
async def list_sources(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    rows = db.query(models.ScrapeSource).order_by(models.ScrapeSource.created_at.desc()).all()
    return [{
        "id": s.id, "name": s.name, "url": s.url, "selector": s.selector,
        "fields": s.fields or [], "use_proxy": s.use_proxy, "enabled": s.enabled,
        "last_value": (s.last_value or "")[:400], "last_scraped": s.last_scraped,
    } for s in rows]


@router.post("/sources")
async def add_source(req: SourceRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = models.ScrapeSource(
        name=req.name, url=req.url, selector=req.selector,
        link_selector=req.link_selector,
        fields=[f.dict() for f in req.fields],
        use_proxy=req.use_proxy, enabled=req.enabled,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "message": "منبع اضافه شد"}


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = db.query(models.ScrapeSource).filter(models.ScrapeSource.id == source_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="یافت نشد")
    db.delete(s)
    db.commit()
    return {"message": "حذف شد"}


@router.put("/sources/{source_id}/toggle")
async def toggle_source(source_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = db.query(models.ScrapeSource).filter(models.ScrapeSource.id == source_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="یافت نشد")
    s.enabled = not s.enabled
    db.commit()
    return {"enabled": s.enabled}


@router.post("/analyze")
async def analyze(req: TestRequest, current_user: models.User = Depends(get_current_user)):
    """صفحه را تحلیل می‌کند و گزینه‌های آماده برای انتخاب برمی‌گرداند."""
    _admin(current_user)
    try:
        groups = await analyze_page(req.url, req.use_proxy)
        return {"ok": True, "groups": groups}
    except Exception as e:
        return {"ok": False, "error": f"خطا: {str(e)[:200]}", "groups": []}


@router.post("/test")
async def test_scrape(req: TestRequest, current_user: models.User = Depends(get_current_user)):
    """تست استخراج: متن استخراج‌شده را برمی‌گرداند تا selector را بررسی کنید."""
    _admin(current_user)
    try:
        text = await scrape_url(req.url, req.selector, req.use_proxy)
        if not text:
            return {"ok": True, "preview": "(چیزی استخراج نشد — selector را بررسی کنید)"}
        return {"ok": True, "preview": text}
    except Exception as e:
        return {"ok": False, "preview": f"خطا: {str(e)[:200]}"}


class TestRecipeRequest(BaseModel):
    url: str
    selector: str = ""
    link_selector: str = ""
    fields: list[FieldItem] = []
    use_proxy: bool = False


@router.post("/test-recipe")
async def test_recipe(req: TestRecipeRequest, current_user: models.User = Depends(get_current_user)):
    """تست رسپی کامل (لینک‌ها + فیلدها) همان‌طور که هنگام اسکرپ واقعی اجرا می‌شود."""
    _admin(current_user)
    from types import SimpleNamespace
    from ..scraping.scraper import scrape_source
    src = SimpleNamespace(
        url=req.url, selector=req.selector, link_selector=req.link_selector,
        fields=[f.dict() for f in req.fields], use_proxy=req.use_proxy,
    )
    try:
        text = await scrape_source(src)
        return {"ok": True, "preview": text or "(چیزی استخراج نشد)"}
    except Exception as e:
        return {"ok": False, "preview": f"خطا: {str(e)[:200]}"}


@router.post("/run")
async def run_scrape(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """همه منابع فعال را همین حالا اسکرپ می‌کند."""
    _admin(current_user)
    count = await scrape_all(db)
    return {"message": f"{count} منبع اسکرپ شد", "count": count}
