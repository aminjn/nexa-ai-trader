from fastapi import APIRouter, Depends, HTTPException, Request, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import httpx

from .. import models
from ..database import get_db
from ..auth.router import get_current_user

router = APIRouter(prefix="/signals", tags=["signals"])


def _admin(user: models.User):
    if not user.is_superadmin:
        raise HTTPException(status_code=403, detail="فقط سوپر ادمین")


def _plan_dict(p: models.Plan) -> dict:
    return {
        "id": p.id, "key": p.key, "name": p.name, "level": p.level,
        "price_toman": p.price_toman, "duration_days": p.duration_days,
        "max_coins": p.max_coins, "delay_minutes": p.delay_minutes,
        "include_analysis": p.include_analysis, "channels": p.channels or [],
        "description": p.description or "", "active": p.active, "sort": p.sort,
    }


def _active_sub(db: Session, user_id: int) -> Optional[models.Subscription]:
    now = datetime.utcnow()
    sub = db.query(models.Subscription).filter(
        models.Subscription.user_id == user_id,
        models.Subscription.status == "active",
    ).order_by(models.Subscription.id.desc()).first()
    if sub and sub.end_at and sub.end_at < now:
        sub.status = "expired"
        db.commit()
        return None
    return sub


def _effective_plan(db: Session, user_id: int) -> models.Plan:
    """پلن مؤثر کاربر: پلن فعال، وگرنه پلن رایگان."""
    sub = _active_sub(db, user_id)
    if sub:
        p = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
        if p:
            return p
    free = db.query(models.Plan).filter(models.Plan.level == 0).order_by(models.Plan.id).first()
    if free:
        return free
    # پیش‌فرض اگر هیچ پلنی نبود
    return models.Plan(key="free", name="رایگان", level=0, delay_minutes=60,
                       include_analysis=False, channels=["inapp"], max_coins=1)


# ─────────────────────────── کاربر ───────────────────────────

@router.get("/plans")
async def list_plans(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    plans = db.query(models.Plan).filter(models.Plan.active == True).order_by(models.Plan.sort, models.Plan.level).all()
    return [_plan_dict(p) for p in plans]


@router.get("/subscription")
async def my_subscription(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    sub = _active_sub(db, current_user.id)
    plan = _effective_plan(db, current_user.id)
    pending = db.query(models.Subscription).filter(
        models.Subscription.user_id == current_user.id,
        models.Subscription.status == "pending",
    ).order_by(models.Subscription.id.desc()).first()
    return {
        "plan": _plan_dict(plan),
        "status": sub.status if sub else "free",
        "end_at": sub.end_at if sub else None,
        "pending": _plan_dict(db.query(models.Plan).filter(models.Plan.id == pending.plan_id).first()) if pending else None,
        "telegram_chat_id": current_user.telegram_chat_id or "",
        "bale_chat_id": current_user.bale_chat_id or "",
    }


class ConnectRequest(BaseModel):
    telegram_chat_id: Optional[str] = None
    bale_chat_id: Optional[str] = None


@router.post("/connect")
async def connect_messengers(req: ConnectRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    if req.telegram_chat_id is not None:
        current_user.telegram_chat_id = req.telegram_chat_id.strip()
    if req.bale_chat_id is not None:
        current_user.bale_chat_id = req.bale_chat_id.strip()
    db.commit()
    return {"ok": True}


class SubscribeRequest(BaseModel):
    plan_id: int


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    plan = db.query(models.Plan).filter(models.Plan.id == req.plan_id, models.Plan.active == True).first()
    if not plan:
        raise HTTPException(status_code=404, detail="پلن یافت نشد")
    now = datetime.utcnow()
    # پلن رایگان → بلافاصله فعال
    if plan.price_toman <= 0:
        sub = models.Subscription(
            user_id=current_user.id, plan_id=plan.id, status="active",
            payment_method="manual", amount_toman=0,
            start_at=now, end_at=now + timedelta(days=plan.duration_days or 30),
        )
        db.add(sub)
        db.commit()
        return {"status": "active", "message": "پلن رایگان فعال شد"}
    # پلن پولی → در انتظار پرداخت/تأیید دستی
    sub = models.Subscription(
        user_id=current_user.id, plan_id=plan.id, status="pending",
        payment_method="manual", amount_toman=plan.price_toman,
    )
    db.add(sub)
    db.commit()
    return {"status": "pending", "message": "درخواست ثبت شد. پس از پرداخت و تأیید ادمین فعال می‌شود.", "subscription_id": sub.id}


@router.get("/link-code")
async def my_link_code(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """کد اتصال خودکار ربات را برمی‌گرداند (در صورت نبود، می‌سازد)."""
    import secrets
    if not current_user.link_code:
        current_user.link_code = secrets.token_hex(4).upper()  # ۸ کاراکتر
        db.commit()
    s = db.query(models.SystemSettings).first()
    return {
        "code": current_user.link_code,
        "telegram_bot": (s.telegram_bot_username if s else "") or "",
        "bale_bot": (s.bale_bot_username if s else "") or "",
        "telegram_connected": bool(current_user.telegram_chat_id),
        "bale_connected": bool(current_user.bale_chat_id),
    }


@router.get("/feed")
async def signal_feed(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    plan = _effective_plan(db, current_user.id)
    now = datetime.utcnow()
    cutoff = now - timedelta(minutes=plan.delay_minutes or 0)
    rows = db.query(models.Signal).filter(
        models.Signal.min_level <= plan.level,
        models.Signal.created_at <= cutoff,
    ).order_by(models.Signal.created_at.desc()).limit(60).all()
    out = []
    for s in rows:
        out.append({
            "id": s.id, "coin": s.coin, "side": s.side, "confidence": s.confidence,
            "entry_price": s.entry_price, "target_price": s.target_price, "stop_price": s.stop_price,
            "tech_conclusion": s.tech_conclusion, "fund_conclusion": s.fund_conclusion,
            "analysis": s.analysis if plan.include_analysis else "",
            "created_at": s.created_at,
        })
    return {"plan": _plan_dict(plan), "signals": out}


# ─────────────────────────── پرداخت (زرین‌پال) ───────────────────────────

@router.post("/pay/request")
async def pay_request(req: SubscribeRequest, request: Request, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    plan = db.query(models.Plan).filter(models.Plan.id == req.plan_id, models.Plan.active == True).first()
    if not plan or plan.price_toman <= 0:
        raise HTTPException(status_code=400, detail="پلن نامعتبر")
    srow = db.query(models.SystemSettings).first()
    merchant = (srow.zarinpal_merchant_id if srow else "") or ""
    if not merchant:
        raise HTTPException(status_code=400, detail="درگاه پرداخت تنظیم نشده — از فعال‌سازی دستی استفاده کنید")

    sub = models.Subscription(
        user_id=current_user.id, plan_id=plan.id, status="pending",
        payment_method="online", amount_toman=plan.price_toman,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)

    base = str(request.base_url).rstrip("/")
    callback = f"{base}/api/signals/pay/verify?sub_id={sub.id}"
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as c:
            r = await c.post("https://api.zarinpal.com/pg/v4/payment/request.json", json={
                "merchant_id": merchant,
                "amount": plan.price_toman * 10,  # زرین‌پال به ریال
                "description": f"اشتراک {plan.name} - NEXA",
                "callback_url": callback,
            })
            data = r.json()
        authority = (data.get("data") or {}).get("authority")
        if not authority:
            raise Exception(str(data.get("errors") or data))
        sub.ref_id = authority
        db.commit()
        return {"pay_url": f"https://www.zarinpal.com/pg/StartPay/{authority}"}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"خطا در اتصال به درگاه: {str(e)[:150]}")


@router.get("/pay/verify")
async def pay_verify(sub_id: int, Authority: str = Query("", alias="Authority"),
                     Status: str = Query("", alias="Status"), db: Session = Depends(get_db)):
    sub = db.query(models.Subscription).filter(models.Subscription.id == sub_id).first()
    if not sub:
        return RedirectResponse("/subscription?pay=notfound")
    plan = db.query(models.Plan).filter(models.Plan.id == sub.plan_id).first()
    srow = db.query(models.SystemSettings).first()
    merchant = (srow.zarinpal_merchant_id if srow else "") or ""
    if Status != "OK":
        sub.status = "rejected"
        db.commit()
        return RedirectResponse("/subscription?pay=failed")
    try:
        async with httpx.AsyncClient(timeout=20, trust_env=False) as c:
            r = await c.post("https://api.zarinpal.com/pg/v4/payment/verify.json", json={
                "merchant_id": merchant,
                "amount": (plan.price_toman if plan else sub.amount_toman) * 10,
                "authority": Authority or sub.ref_id,
            })
            data = r.json()
        code = (data.get("data") or {}).get("code")
        if code in (100, 101):
            now = datetime.utcnow()
            sub.status = "active"
            sub.start_at = now
            sub.end_at = now + timedelta(days=(plan.duration_days if plan else 30))
            db.commit()
            return RedirectResponse("/subscription?pay=success")
    except Exception:
        pass
    sub.status = "rejected"
    db.commit()
    return RedirectResponse("/subscription?pay=failed")


# ─────────────────────────── ادمین ───────────────────────────

class PlanRequest(BaseModel):
    key: str
    name: str
    level: int = 0
    price_toman: int = 0
    duration_days: int = 30
    max_coins: int = 1
    delay_minutes: int = 0
    include_analysis: bool = False
    channels: list[str] = []
    description: str = ""
    active: bool = True
    sort: int = 0


@router.get("/admin/plans")
async def admin_list_plans(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    return [_plan_dict(p) for p in db.query(models.Plan).order_by(models.Plan.sort, models.Plan.level).all()]


@router.post("/admin/plans")
async def admin_create_plan(req: PlanRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    existing = db.query(models.Plan).filter(models.Plan.key == req.key).first()
    if existing:
        for k, v in req.dict().items():
            setattr(existing, k, v)
        db.commit()
        return {"id": existing.id, "message": "پلن به‌روزرسانی شد"}
    p = models.Plan(**req.dict())
    db.add(p)
    db.commit()
    return {"id": p.id, "message": "پلن ایجاد شد"}


@router.put("/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: int, req: PlanRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    p = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="یافت نشد")
    for k, v in req.dict().items():
        setattr(p, k, v)
    db.commit()
    return {"message": "ذخیره شد"}


@router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    p = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if p:
        db.delete(p)
        db.commit()
    return {"message": "حذف شد"}


@router.get("/admin/subscriptions")
async def admin_subscriptions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    rows = db.query(models.Subscription).order_by(models.Subscription.id.desc()).limit(200).all()
    out = []
    for s in rows:
        u = db.query(models.User).filter(models.User.id == s.user_id).first()
        p = db.query(models.Plan).filter(models.Plan.id == s.plan_id).first()
        out.append({
            "id": s.id, "user": (u.full_name or u.email or u.phone or f"#{s.user_id}") if u else f"#{s.user_id}",
            "user_id": s.user_id, "plan": p.name if p else "—", "status": s.status,
            "payment_method": s.payment_method, "amount_toman": s.amount_toman,
            "created_at": s.created_at, "end_at": s.end_at,
        })
    return out


@router.post("/admin/subscriptions/{sub_id}/activate")
async def admin_activate(sub_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = db.query(models.Subscription).filter(models.Subscription.id == sub_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="یافت نشد")
    p = db.query(models.Plan).filter(models.Plan.id == s.plan_id).first()
    now = datetime.utcnow()
    s.status = "active"
    s.start_at = now
    s.end_at = now + timedelta(days=(p.duration_days if p else 30))
    db.commit()
    return {"message": "اشتراک فعال شد"}


@router.post("/admin/subscriptions/{sub_id}/reject")
async def admin_reject(sub_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = db.query(models.Subscription).filter(models.Subscription.id == sub_id).first()
    if s:
        s.status = "rejected"
        db.commit()
    return {"message": "رد شد"}


class SignalSettingsRequest(BaseModel):
    telegram_bot_token: Optional[str] = None
    bale_bot_token: Optional[str] = None
    zarinpal_merchant_id: Optional[str] = None
    signal_coins: Optional[str] = None
    signal_interval_minutes: Optional[int] = None
    telegram_channel_id: Optional[str] = None
    bale_channel_id: Optional[str] = None
    telegram_bot_username: Optional[str] = None
    bale_bot_username: Optional[str] = None
    content_interval_hours: Optional[int] = None
    ad_interval_hours: Optional[int] = None
    ad_text: Optional[str] = None
    ai_support_enabled: Optional[bool] = None
    card_number: Optional[str] = None
    card_holder: Optional[str] = None
    account_number: Optional[str] = None
    support_contact: Optional[str] = None
    # ورود با پیامک (IPPanel)
    ippanel_token: Optional[str] = None
    ippanel_pattern_code: Optional[str] = None
    ippanel_from_number: Optional[str] = None
    ippanel_param_name: Optional[str] = None
    sms_login_enabled: Optional[bool] = None


# ارزهای رایج نوبیتکس برای انتخاب در لیست
AVAILABLE_COINS = [
    "BTC", "ETH", "USDT", "XRP", "ADA", "DOGE", "LTC", "TRX", "BCH", "BNB",
    "SOL", "DOT", "AVAX", "MATIC", "SHIB", "LINK", "UNI", "ATOM", "FIL", "ETC",
    "XLM", "NEAR", "AAVE", "GRT", "SAND", "MANA", "FTM", "GALA", "AXS", "APE",
    "GMT", "CRV", "COMP", "MKR", "1INCH", "ENS", "SNX", "IMX", "FLOW", "CHZ",
    "ENJ", "BAT", "QNT", "LDO", "ARB", "OP", "APT", "FET", "TON", "NOT",
    "PEPE", "WLD", "FLOKI", "INJ", "DYDX",
]


@router.get("/admin/available-coins")
async def available_coins(current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    return {"coins": AVAILABLE_COINS}


@router.get("/admin/settings")
async def admin_get_settings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = db.query(models.SystemSettings).first()
    if not s:
        s = models.SystemSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return {
        "telegram_bot_token": s.telegram_bot_token or "",
        "bale_bot_token": s.bale_bot_token or "",
        "zarinpal_merchant_id": s.zarinpal_merchant_id or "",
        "signal_coins": s.signal_coins or "BTC,ETH",
        "signal_interval_minutes": s.signal_interval_minutes or 30,
        "telegram_channel_id": s.telegram_channel_id or "",
        "bale_channel_id": s.bale_channel_id or "",
        "telegram_bot_username": s.telegram_bot_username or "",
        "bale_bot_username": s.bale_bot_username or "",
        "content_interval_hours": s.content_interval_hours or 6,
        "ad_interval_hours": s.ad_interval_hours or 12,
        "ad_text": s.ad_text or "",
        "ai_support_enabled": bool(s.ai_support_enabled),
        "card_number": s.card_number or "",
        "card_holder": s.card_holder or "",
        "account_number": s.account_number or "",
        "support_contact": s.support_contact or "",
        "ippanel_token": s.ippanel_token or "",
        "ippanel_pattern_code": s.ippanel_pattern_code or "",
        "ippanel_from_number": s.ippanel_from_number or "",
        "ippanel_param_name": s.ippanel_param_name or "code",
        "sms_login_enabled": bool(s.ippanel_token and s.sms_login_enabled),
    }


@router.post("/admin/settings")
async def admin_save_settings(req: SignalSettingsRequest, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    s = db.query(models.SystemSettings).first()
    if not s:
        s = models.SystemSettings()
        db.add(s)
    for k, v in req.dict().items():
        if v is not None:
            setattr(s, k, v)
    db.commit()
    return {"message": "تنظیمات ذخیره شد"}


@router.post("/admin/test-channel")
async def admin_test_channel(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """به کانال‌های تلگرام و بله پیام تست می‌فرستد و پاسخ خام API را برمی‌گرداند."""
    _admin(current_user)
    import httpx
    from ..config import settings as cfg
    s = db.query(models.SystemSettings).first()
    out = {}
    text = "✅ پیام تست NEXA AI — اتصال کانال برقرار است."

    async def _try(name, url, chat_id, use_proxy):
        if not chat_id:
            return {"ok": False, "detail": "آی‌دی کانال خالی است"}
        proxy = cfg.GAPGPT_PROXY if use_proxy else None
        try:
            async with httpx.AsyncClient(timeout=15, proxy=proxy, trust_env=False) as c:
                r = await c.post(url, json={"chat_id": chat_id, "text": text})
                return {"ok": r.json().get("ok", False), "detail": str(r.json())[:400]}
        except Exception as e:
            return {"ok": False, "detail": str(e)[:300]}

    if s and s.telegram_bot_token:
        out["telegram"] = await _try("telegram",
            f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
            s.telegram_channel_id, use_proxy=True)
    else:
        out["telegram"] = {"ok": False, "detail": "توکن تلگرام تنظیم نشده"}

    if s and s.bale_bot_token:
        out["bale"] = await _try("bale",
            f"https://tapi.bale.ai/bot{s.bale_bot_token}/sendMessage",
            s.bale_channel_id, use_proxy=True)
    else:
        out["bale"] = {"ok": False, "detail": "توکن بله تنظیم نشده"}

    return out


@router.post("/admin/generate-now")
async def admin_generate_now(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    from ..signals.engine import generate_signals
    n = await generate_signals(db, push=True)
    return {"message": f"{n} سیگنال تولید و ارسال شد", "count": n}


@router.post("/admin/publish-now")
async def admin_publish_now(current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    import asyncio
    from ..database import SessionLocal
    from ..signals.content import publish_content

    async def _bg():
        db2 = SessionLocal()
        try:
            await publish_content(db2)
        except Exception as e:
            print(f"⚠️ publish-now bg: {e}")
        finally:
            db2.close()

    asyncio.create_task(_bg())
    return {"message": "در حال آماده‌سازی و انتشار محتوا... چند لحظه دیگر کانال را بررسی کن"}


@router.post("/admin/publish-ad")
async def admin_publish_ad(current_user: models.User = Depends(get_current_user)):
    _admin(current_user)
    import asyncio
    from ..database import SessionLocal
    from ..signals.content import publish_ad

    async def _bg():
        db2 = SessionLocal()
        try:
            await publish_ad(db2)
        except Exception as e:
            print(f"⚠️ publish-ad bg: {e}")
        finally:
            db2.close()

    asyncio.create_task(_bg())
    return {"message": "در حال ساخت و انتشار تبلیغ... چند لحظه دیگر کانال را بررسی کن"}
