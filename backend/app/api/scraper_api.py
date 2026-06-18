from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..scraping.scraper import scrape_url, scrape_all, analyze_page

router = APIRouter(prefix="/scraper", tags=["scraper"])


class SourceRequest(BaseModel):
    name: str
    url: str
    selector: str = ""
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
        "use_proxy": s.use_proxy, "enabled": s.enabled,
        "last_value": (s.last_value or "")[:300], "last_scraped": s.last_scraped,
    } for s in rows]


@router.post("/sources")
async def add_source(req: SourceRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = models.ScrapeSource(
        name=req.name, url=req.url, selector=req.selector,
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


@router.post("/run")
async def run_scrape(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """همه منابع فعال را همین حالا اسکرپ می‌کند."""
    _admin(current_user)
    count = await scrape_all(db)
    return {"message": f"{count} منبع اسکرپ شد", "count": count}
