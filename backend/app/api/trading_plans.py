"""API پلن‌های ربات معامله‌گر و اشتراک‌ها (کاربر + سوپر ادمین)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, get_superadmin
from ..trading import access
from ..trading.bot import stop_user_bot

router = APIRouter(prefix="/trading", tags=["trading-plans"])


def _plan_out(p: models.TradingPlan) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "plan_type": p.plan_type,
        "duration_days": p.duration_days,
        "price_toman": p.price_toman,
        "max_trades_per_day": p.max_trades_per_day,
        "allow_own_api": bool(p.allow_own_api),
        "commission_tiers": p.commission_tiers or [],
        "description": p.description or "",
        "features": p.features or [],
        "active": bool(p.active),
        "sort": p.sort or 0,
    }


# ───────────────────────── کاربر ─────────────────────────

@router.get("/plans")
async def list_plans(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """پلن‌های فعال برای صفحهٔ خرید."""
    plans = db.query(models.TradingPlan).filter(models.TradingPlan.active == True).order_by(
        models.TradingPlan.sort, models.TradingPlan.id).all()
    return [_plan_out(p) for p in plans]


@router.get("/my-access")
async def my_access(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """وضعیت دسترسی کاربر: اشتراک فعال، پلن، کارمزد، اجازهٔ API شخصی."""
    if current_user.is_superadmin:
        return {"has_access": True, "is_superadmin": True, "can_use_own_api": True,
                "subscription": None, "commission": access.commission_summary(db, current_user)}
    sub = access.get_active_subscription(db, current_user.id)
    plan = access.get_plan(db, sub.plan_id) if sub else None
    # آخرین اشتراک در انتظار/ردشده برای نمایش وضعیت
    pending = db.query(models.TradingSubscription).filter(
        models.TradingSubscription.user_id == current_user.id,
        models.TradingSubscription.status == "pending",
    ).order_by(models.TradingSubscription.id.desc()).first()
    sub_out = None
    if sub and plan:
        sub_out = {
            "status": "active",
            "plan_name": plan.name,
            "plan_type": plan.plan_type,
            "end_at": sub.end_at.isoformat() if sub.end_at else None,
            "days_left": max(0, (sub.end_at - datetime.utcnow()).days) if sub.end_at else None,
            "max_trades_per_day": plan.max_trades_per_day,
            "trades_today": access.trades_today(db, current_user.id),
        }
    return {
        "has_access": sub is not None,
        "is_superadmin": False,
        "can_use_own_api": access.can_use_own_api(db, current_user),
        "subscription": sub_out,
        "pending": bool(pending),
        "commission": access.commission_summary(db, current_user),
    }


class SubscribeRequest(BaseModel):
    plan_id: int


@router.post("/subscribe")
async def subscribe(req: SubscribeRequest, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    """درخواست یک پلن (در انتظار تأیید/پرداخت ادمین)."""
    plan = access.get_plan(db, req.plan_id)
    if not plan or not plan.active:
        raise HTTPException(status_code=404, detail="پلن یافت نشد")
    # اگر اشتراک فعال دارد، اجازهٔ درخواست مجدد نده
    if access.get_active_subscription(db, current_user.id):
        raise HTTPException(status_code=400, detail="شما در حال حاضر اشتراک فعال دارید")
    sub = models.TradingSubscription(
        user_id=current_user.id, plan_id=plan.id, status="pending",
    )
    db.add(sub)
    db.commit()
    return {"message": "درخواست شما ثبت شد. پس از واریز و تأیید ادمین، پلن فعال می‌شود.", "subscription_id": sub.id}


# ───────────────────────── سوپر ادمین ─────────────────────────

class PlanRequest(BaseModel):
    name: str
    plan_type: str = "self_api"            # self_api | managed
    duration_days: int = 30
    price_toman: int = 0
    max_trades_per_day: int = 0
    allow_own_api: bool = True
    commission_tiers: List[dict] = []
    description: str = ""
    features: List[str] = []
    active: bool = True
    sort: int = 0


@router.get("/admin/plans")
async def admin_list_plans(db: Session = Depends(get_db), current_user: models.User = Depends(get_superadmin)):
    plans = db.query(models.TradingPlan).order_by(models.TradingPlan.sort, models.TradingPlan.id).all()
    return [_plan_out(p) for p in plans]


@router.post("/admin/plans")
async def admin_create_plan(req: PlanRequest, db: Session = Depends(get_db),
                            current_user: models.User = Depends(get_superadmin)):
    p = models.TradingPlan(**req.dict())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _plan_out(p)


@router.put("/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: int, req: PlanRequest, db: Session = Depends(get_db),
                            current_user: models.User = Depends(get_superadmin)):
    p = access.get_plan(db, plan_id)
    if not p:
        raise HTTPException(status_code=404, detail="پلن یافت نشد")
    for k, v in req.dict().items():
        setattr(p, k, v)
    db.commit()
    return _plan_out(p)


@router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: int, db: Session = Depends(get_db),
                            current_user: models.User = Depends(get_superadmin)):
    p = access.get_plan(db, plan_id)
    if p:
        db.delete(p)
        db.commit()
    return {"message": "پلن حذف شد"}


@router.get("/admin/subscriptions")
async def admin_list_subs(db: Session = Depends(get_db), current_user: models.User = Depends(get_superadmin)):
    subs = db.query(models.TradingSubscription).order_by(models.TradingSubscription.id.desc()).all()
    out = []
    for s in subs:
        u = db.query(models.User).filter(models.User.id == s.user_id).first()
        p = access.get_plan(db, s.plan_id)
        comm = None
        if p and p.plan_type == "managed":
            rate = access.commission_rate_for(p, s.deposit_toman or 0)
            profit = access.realized_profit_toman(db, s.user_id)
            owed = max(0.0, profit) * rate / 100.0
            comm = {"rate": rate, "profit": round(profit), "owed": round(owed),
                    "settled": round(s.commission_settled_toman or 0),
                    "remaining": round(max(0.0, owed - (s.commission_settled_toman or 0)))}
        out.append({
            "id": s.id,
            "user_id": s.user_id,
            "user_name": u.full_name if u else "—",
            "user_phone": (u.phone or u.email) if u else "—",
            "plan_id": s.plan_id,
            "plan_name": p.name if p else "—",
            "plan_type": p.plan_type if p else "—",
            "status": s.status,
            "deposit_toman": s.deposit_toman or 0,
            "start_at": s.start_at.isoformat() if s.start_at else None,
            "end_at": s.end_at.isoformat() if s.end_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "commission": comm,
        })
    return out


class ActivateRequest(BaseModel):
    deposit_toman: int = 0
    duration_days: Optional[int] = None   # اگر بخواهی طول پلن را دستی عوض کنی


@router.post("/admin/subscriptions/{sub_id}/activate")
async def admin_activate(sub_id: int, req: ActivateRequest, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_superadmin)):
    s = db.query(models.TradingSubscription).filter(models.TradingSubscription.id == sub_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="اشتراک یافت نشد")
    plan = access.get_plan(db, s.plan_id)
    days = req.duration_days if req.duration_days else (plan.duration_days if plan else 30)
    s.status = "active"
    s.deposit_toman = req.deposit_toman or s.deposit_toman or 0
    s.start_at = datetime.utcnow()
    s.end_at = datetime.utcnow() + timedelta(days=days)
    db.commit()
    return {"message": f"اشتراک فعال شد (تا {days} روز)", "end_at": s.end_at.isoformat()}


@router.post("/admin/subscriptions/{sub_id}/reject")
async def admin_reject(sub_id: int, db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_superadmin)):
    s = db.query(models.TradingSubscription).filter(models.TradingSubscription.id == sub_id).first()
    if s:
        s.status = "rejected"
        db.commit()
        stop_user_bot(s.user_id)
    return {"message": "رد شد"}


@router.post("/admin/subscriptions/{sub_id}/expire")
async def admin_expire(sub_id: int, db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_superadmin)):
    """خاتمهٔ دستی اشتراک (ربات کاربر خاموش می‌شود)."""
    s = db.query(models.TradingSubscription).filter(models.TradingSubscription.id == sub_id).first()
    if s:
        s.status = "expired"
        db.commit()
        u = db.query(models.User).filter(models.User.id == s.user_id).first()
        if u:
            u.bot_active = False
            db.commit()
        stop_user_bot(s.user_id)
    return {"message": "اشتراک خاتمه یافت"}


class SettleRequest(BaseModel):
    amount_toman: int


@router.post("/admin/subscriptions/{sub_id}/settle")
async def admin_settle(sub_id: int, req: SettleRequest, db: Session = Depends(get_db),
                       current_user: models.User = Depends(get_superadmin)):
    """ثبت تسویهٔ کارمزد سود (افزایش مبلغ تسویه‌شده)."""
    s = db.query(models.TradingSubscription).filter(models.TradingSubscription.id == sub_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="اشتراک یافت نشد")
    s.commission_settled_toman = (s.commission_settled_toman or 0) + max(0, req.amount_toman)
    db.commit()
    return {"message": "تسویه ثبت شد", "settled": s.commission_settled_toman}
