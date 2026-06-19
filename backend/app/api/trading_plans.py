"""API پلن‌های ربات معامله‌گر و اشتراک‌ها (کاربر + سوپر ادمین)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, get_superadmin
from ..trading import access, pool
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
    # کارمزد: برای managed از استخر (واحد)، وگرنه غیرفعال
    if sub and plan and plan.plan_type == "managed":
        commission = await pool.managed_commission(db, sub, plan)
    else:
        commission = {"applicable": False}
    return {
        "has_access": sub is not None,
        "is_superadmin": False,
        "can_use_own_api": access.can_use_own_api(db, current_user),
        "subscription": sub_out,
        "pending": bool(pending),
        "commission": commission,
    }


@router.get("/payment-info")
async def payment_info(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """اطلاعات پرداخت کارت‌به‌کارت برای خرید پلن (از تنظیمات سیستم)."""
    s = db.query(models.SystemSettings).first()
    return {
        "card_number": (s.card_number if s else "") or "",
        "card_holder": (s.card_holder if s else "") or "",
        "account_number": (s.account_number if s else "") or "",
        "support_contact": (s.support_contact if s else "") or "",
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


class WithdrawRequest(BaseModel):
    amount_toman: int = 0   # ۰ = برداشت کل موجودی


@router.post("/withdraw")
async def request_withdraw(req: WithdrawRequest, db: Session = Depends(get_db),
                           current_user: models.User = Depends(get_current_user)):
    """درخواست برداشت از استخر مدیریت‌شده (فقط پلن managed با اشتراک فعال)."""
    sub = access.get_active_subscription(db, current_user.id)
    plan = access.get_plan(db, sub.plan_id) if sub else None
    if not sub or not plan or plan.plan_type != "managed":
        raise HTTPException(status_code=400, detail="برداشت فقط برای پلن مدیریت‌شدهٔ فعال ممکن است")
    value = await pool.user_value_toman(db, sub)
    if req.amount_toman and req.amount_toman > value + 1:
        raise HTTPException(status_code=400, detail=f"مبلغ درخواستی بیش از موجودی شماست ({round(value):,} تومان)")
    # جلوگیری از درخواست تکراری در انتظار
    existing = db.query(models.PoolWithdrawal).filter(
        models.PoolWithdrawal.subscription_id == sub.id,
        models.PoolWithdrawal.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="یک درخواست برداشت در انتظار تأیید دارید")
    # محاسبهٔ لحظه‌ای و قفلِ مبلغ در همین لحظهٔ درخواست
    f = await pool.compute_redemption(db, sub, plan, float(req.amount_toman))
    w = models.PoolWithdrawal(
        user_id=current_user.id, subscription_id=sub.id,
        amount_toman=max(0, req.amount_toman), status="pending",
        unit_price=f["unit_price"], units_redeemed=f["units_redeemed"],
        gross_toman=f["gross"], deposit_removed_toman=f["deposit_removed"],
        commission_toman=f["commission"], payout_toman=f["payout"],
    )
    db.add(w)
    db.commit()
    return {
        "message": f"درخواست برداشت ثبت شد. مبلغ قطعی‌شدهٔ این لحظه: {f['payout']:,} تومان "
                   f"(کارمزد سود: {f['commission']:,}). پس از تأیید ادمین پرداخت می‌شود.",
        "gross": f["gross"], "commission": f["commission"], "payout": f["payout"],
    }


@router.get("/my-withdrawals")
async def my_withdrawals(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    ws = db.query(models.PoolWithdrawal).filter(
        models.PoolWithdrawal.user_id == current_user.id,
    ).order_by(models.PoolWithdrawal.id.desc()).limit(20).all()
    return [{"id": w.id, "amount_toman": w.amount_toman, "payout_toman": w.payout_toman,
             "commission_toman": w.commission_toman, "status": w.status,
             "created_at": w.created_at.isoformat() if w.created_at else None} for w in ws]


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
            comm = await pool.managed_commission(db, s, p)
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
    s.start_at = datetime.utcnow()
    s.end_at = datetime.utcnow() + timedelta(days=days)
    db.commit()
    # برای پلن managed: به ازای مبلغ واریزی، واحدِ استخر صادر کن
    if plan and plan.plan_type == "managed" and (req.deposit_toman or 0) > 0:
        await pool.issue_units(db, s, float(req.deposit_toman))
    else:
        s.deposit_toman = req.deposit_toman or s.deposit_toman or 0
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


# ───────────────────────── حساب استخر مدیریت‌شده ─────────────────────────

@router.get("/admin/pool")
async def admin_pool(db: Session = Depends(get_db), current_user: models.User = Depends(get_superadmin)):
    """خلاصهٔ استخر + لیست صرافی‌های قابل انتخاب به‌عنوان استخر."""
    summary = await pool.pool_summary(db)
    exchanges = db.query(models.ExchangeAPI).filter(models.ExchangeAPI.is_active == True).all()
    return {
        "summary": summary,
        "exchanges": [{"id": e.id, "name": e.exchange_name, "user_id": e.user_id, "is_pool": bool(e.is_pool)} for e in exchanges],
    }


class SetPoolRequest(BaseModel):
    exchange_id: int


@router.post("/admin/pool/set")
async def admin_set_pool(req: SetPoolRequest, db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_superadmin)):
    """یک حساب صرافی را به‌عنوان حساب استخر علامت می‌زند (بقیه از حالت استخر خارج می‌شوند)."""
    db.query(models.ExchangeAPI).update({models.ExchangeAPI.is_pool: False})
    ex = db.query(models.ExchangeAPI).filter(models.ExchangeAPI.id == req.exchange_id).first()
    if not ex:
        raise HTTPException(status_code=404, detail="صرافی یافت نشد")
    ex.is_pool = True
    db.commit()
    return {"message": "حساب استخر تنظیم شد"}


@router.get("/admin/withdrawals")
async def admin_list_withdrawals(db: Session = Depends(get_db),
                                 current_user: models.User = Depends(get_superadmin)):
    ws = db.query(models.PoolWithdrawal).order_by(models.PoolWithdrawal.id.desc()).all()
    out = []
    for w in ws:
        u = db.query(models.User).filter(models.User.id == w.user_id).first()
        sub = db.query(models.TradingSubscription).filter(models.TradingSubscription.id == w.subscription_id).first()
        cur_value = None
        if w.status == "pending" and sub:
            cur_value = round(await pool.user_value_toman(db, sub))
        out.append({
            "id": w.id, "user_name": u.full_name if u else "—",
            "user_phone": (u.phone or u.email) if u else "—",
            "amount_toman": w.amount_toman,
            "gross_toman": w.gross_toman,            # ارزش قفل‌شدهٔ لحظهٔ درخواست
            "current_value": cur_value,              # ارزش زندهٔ فعلی (برای مقایسه)
            "payout_toman": w.payout_toman, "commission_toman": w.commission_toman,
            "units_redeemed": w.units_redeemed, "status": w.status,
            "created_at": w.created_at.isoformat() if w.created_at else None,
        })
    return out


@router.post("/admin/withdrawals/{wid}/approve")
async def admin_approve_withdrawal(wid: int, db: Session = Depends(get_db),
                                   current_user: models.User = Depends(get_superadmin)):
    """تأیید برداشت: واحدها بازخرید و حساب‌داری به‌روزرسانی می‌شود.

    انتقال واقعی پول به کاربر را خودِ ادمین در نوبیتکس انجام می‌دهد (مبلغ payout).
    """
    w = db.query(models.PoolWithdrawal).filter(models.PoolWithdrawal.id == wid).first()
    if not w or w.status != "pending":
        raise HTTPException(status_code=404, detail="درخواست یافت نشد یا قبلاً پردازش شده")
    sub = db.query(models.TradingSubscription).filter(models.TradingSubscription.id == w.subscription_id).first()
    if not sub:
        raise HTTPException(status_code=400, detail="اشتراک مرتبط یافت نشد")
    # اعمال مقادیرِ قفل‌شده در لحظهٔ درخواست (بدون محاسبهٔ مجدد با قیمت روز)
    frozen = {
        "units_redeemed": w.units_redeemed or 0.0,
        "deposit_removed": w.deposit_removed_toman or 0,
        "commission": w.commission_toman or 0,
    }
    pool.apply_redemption(db, sub, frozen)
    w.status = "approved"
    w.processed_at = datetime.utcnow()
    db.commit()
    if sub.status == "expired":
        stop_user_bot(sub.user_id)
    return {"message": f"تأیید شد. مبلغ پرداختی به کاربر: {(w.payout_toman or 0):,} تومان "
                       f"(کارمزد کسرشده: {(w.commission_toman or 0):,}) — مطابق لحظهٔ درخواست",
            "payout": w.payout_toman, "commission": w.commission_toman}


@router.post("/admin/withdrawals/{wid}/reject")
async def admin_reject_withdrawal(wid: int, db: Session = Depends(get_db),
                                  current_user: models.User = Depends(get_superadmin)):
    w = db.query(models.PoolWithdrawal).filter(models.PoolWithdrawal.id == wid).first()
    if w and w.status == "pending":
        w.status = "rejected"
        w.processed_at = datetime.utcnow()
        db.commit()
    return {"message": "رد شد"}
