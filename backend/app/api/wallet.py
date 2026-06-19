"""کیف پول: واریز کارت‌به‌کارت، برداشت، تاریخچه (کاربر + سوپر ادمین)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, get_superadmin
from ..trading import access, pool
from ..notifications import notify_admin, notify_user

router = APIRouter(prefix="/wallet", tags=["wallet"])


def _fmt(n) -> int:
    return int(round(n or 0))


@router.get("/")
async def get_wallet(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """موجودی کیف پول + اطلاعات واریز + تاریخچهٔ واریز/برداشت."""
    s = db.query(models.SystemSettings).first()
    ms = await pool.managed_share(db, current_user)

    if ms:
        balance = _fmt(ms["value"])
        invested = _fmt(ms["deposit"])
        profit = _fmt(ms["value"] - ms["deposit"])
        wtype = "managed"
    else:
        balance = _fmt(current_user.wallet_balance_toman)
        invested = 0
        profit = 0
        wtype = "wallet"

    # واریزها
    deps = db.query(models.Deposit).filter(models.Deposit.user_id == current_user.id).order_by(
        models.Deposit.id.desc()).limit(50).all()
    deposits = [{
        "id": d.id, "kind": "deposit" if d.purpose != "withdraw" else "withdraw",
        "amount_toman": d.amount_toman, "purpose": d.purpose, "status": d.status,
        "reference": d.reference, "note": d.note,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    } for d in deps]

    # برداشت‌های استخر (managed)
    withdrawals = []
    if ms:
        ws = db.query(models.PoolWithdrawal).filter(
            models.PoolWithdrawal.user_id == current_user.id).order_by(models.PoolWithdrawal.id.desc()).limit(50).all()
        withdrawals = [{
            "id": w.id, "kind": "withdraw", "amount_toman": w.gross_toman or w.amount_toman,
            "payout_toman": w.payout_toman, "commission_toman": w.commission_toman,
            "status": w.status, "created_at": w.created_at.isoformat() if w.created_at else None,
        } for w in ws]

    return {
        "type": wtype,
        "balance_toman": balance,
        "invested_toman": invested,
        "profit_toman": profit,
        "kyc_status": current_user.kyc_status or "none",
        "payment_info": {
            "card_number": (s.card_number if s else "") or "",
            "card_holder": (s.card_holder if s else "") or "",
            "account_number": (s.account_number if s else "") or "",
            "support_contact": (s.support_contact if s else "") or "",
        },
        "history": sorted(deposits + withdrawals, key=lambda x: x.get("created_at") or "", reverse=True),
    }


@router.get("/trades")
async def wallet_trades(limit: int = 100, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    """دفترچهٔ معاملات: برای هر معامله، پولِ خارج‌شده (خرید)، پولِ واردشده (فروش)،
    کارمزد و سود/زیان خالص. کاربرِ managed سهمِ خودش را می‌بیند."""
    ms = await pool.managed_share(db, current_user)
    if ms:
        oid = ms["pool_owner_id"] or current_user.id
        frac = ms["fraction"]
    else:
        oid = current_user.id
        frac = 1.0

    trades = db.query(models.Trade).filter(
        models.Trade.user_id == oid,
        models.Trade.status == "closed",
    ).order_by(models.Trade.closed_at.desc().nullslast(), models.Trade.id.desc()).limit(limit).all()

    # کارمزدِ مالکِ معاملات (برای محاسبهٔ معاملات قدیمی که مبلغشان ذخیره نشده)
    owner = db.query(models.User).filter(models.User.id == oid).first()
    fee_pct = (getattr(owner, "fee_pct", 0.25) or 0.25)

    def quote_div(pair: str) -> float:
        q = (pair.split("/")[-1] if pair and "/" in pair else "").upper()
        return 10.0 if q in ("RLS", "IRR", "IRT") else 1.0  # ریال → تومان

    rows = []
    tot_cost = tot_proceeds = tot_fee = tot_net = 0.0
    for t in trades:
        # مقادیر ذخیره‌شده؛ اگر نبود (معاملات قدیمی) از قیمت ورود/خروج × مقدار محاسبه کن
        if t.cost_toman or t.proceeds_toman or t.fee_toman:
            cost = t.cost_toman or 0
            proceeds = t.proceeds_toman or 0
            fee = t.fee_toman or 0
            net = (t.pnl or 0)
        else:
            d = quote_div(t.pair)
            amt = t.amount or 0
            cost = (t.entry_price or 0) * amt / d
            proceeds = (t.exit_price or 0) * amt / d
            fee = (cost + proceeds) * fee_pct / 100.0
            net = proceeds - cost - fee   # سود/زیان خالصِ بازمحاسبه‌شده (شاملِ کمیسیون)
        cost *= frac; proceeds *= frac; fee *= frac; net *= frac
        pct = (net / cost * 100.0) if cost else 0
        tot_cost += cost; tot_proceeds += proceeds; tot_fee += fee; tot_net += net
        rows.append({
            "id": t.id, "pair": t.pair,
            "cost_toman": round(cost), "proceeds_toman": round(proceeds),
            "fee_toman": round(fee), "net_pnl": round(net), "pnl_pct": round(pct, 3),
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        })
    return {
        "share_based": frac != 1.0,
        "trades": rows,
        "totals": {"cost": round(tot_cost), "proceeds": round(tot_proceeds),
                   "fee": round(tot_fee), "net": round(tot_net)},
    }


class DepositRequest(BaseModel):
    amount_toman: int
    reference: str = ""
    receipt_image: str = ""
    purpose: str = "wallet"   # wallet | invest


@router.post("/deposit")
async def request_deposit(req: DepositRequest, db: Session = Depends(get_db),
                          current_user: models.User = Depends(get_current_user)):
    """ثبت واریز کارت‌به‌کارت — در انتظار تأیید سوپر ادمین (با نوتیف)."""
    if req.amount_toman <= 0:
        raise HTTPException(status_code=400, detail="مبلغ نامعتبر است")
    # برای سرمایه‌گذاری در استخر، احراز هویت لازم است
    purpose = req.purpose
    plan = access.active_plan(db, current_user)
    if plan and plan.plan_type == "managed":
        purpose = "invest"
    if purpose == "invest" and current_user.kyc_status != "verified" and not current_user.is_superadmin:
        raise HTTPException(status_code=403, detail="برای سرمایه‌گذاری ابتدا باید احراز هویت شوید")

    d = models.Deposit(user_id=current_user.id, amount_toman=req.amount_toman,
                       reference=req.reference, receipt_image=req.receipt_image,
                       purpose=purpose, status="pending")
    db.add(d)
    db.commit()
    notify_admin(db, "deposit", "واریز جدید (کارت‌به‌کارت)",
                 f"{current_user.full_name} مبلغ {req.amount_toman:,} تومان واریز کرد و منتظر تأیید است.",
                 ref_user_id=current_user.id, link="/admin/wallet")
    return {"message": "واریز شما ثبت شد و پس از تأیید سوپر ادمین به حساب شما اعمال می‌شود."}


class WithdrawRequest(BaseModel):
    amount_toman: int


@router.post("/withdraw")
async def request_wallet_withdraw(req: WithdrawRequest, db: Session = Depends(get_db),
                                  current_user: models.User = Depends(get_current_user)):
    """برداشت از کیف پول (برای پلن‌های غیر-managed). برداشت managed از مسیر استخر است."""
    if await pool.managed_share(db, current_user):
        raise HTTPException(status_code=400, detail="برداشت این حساب از بخش استخر/پلن انجام می‌شود")
    if req.amount_toman <= 0 or req.amount_toman > (current_user.wallet_balance_toman or 0):
        raise HTTPException(status_code=400, detail="مبلغ بیش از موجودی کیف پول است")
    d = models.Deposit(user_id=current_user.id, amount_toman=req.amount_toman,
                       purpose="withdraw", status="pending")
    db.add(d)
    db.commit()
    notify_admin(db, "withdrawal", "درخواست برداشت از کیف پول",
                 f"{current_user.full_name} درخواست برداشت {req.amount_toman:,} تومان از کیف پول دارد.",
                 ref_user_id=current_user.id, link="/admin/wallet")
    return {"message": "درخواست برداشت ثبت شد و پس از تأیید پرداخت می‌شود."}


# ───────────────────────── سوپر ادمین ─────────────────────────

@router.get("/admin/deposits")
async def admin_deposits(status: str = "", db: Session = Depends(get_db),
                         current_user: models.User = Depends(get_superadmin)):
    q = db.query(models.Deposit)
    if status:
        q = q.filter(models.Deposit.status == status)
    rows = q.order_by(models.Deposit.id.desc()).limit(200).all()
    out = []
    for d in rows:
        u = db.query(models.User).filter(models.User.id == d.user_id).first()
        out.append({
            "id": d.id, "user_id": d.user_id, "user_name": u.full_name if u else "—",
            "user_phone": (u.phone or u.email) if u else "—",
            "amount_toman": d.amount_toman, "purpose": d.purpose, "reference": d.reference,
            "has_receipt": bool(d.receipt_image), "status": d.status, "note": d.note,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })
    return out


@router.get("/admin/deposits/{dep_id}/receipt")
async def admin_deposit_receipt(dep_id: int, db: Session = Depends(get_db),
                                current_user: models.User = Depends(get_superadmin)):
    d = db.query(models.Deposit).filter(models.Deposit.id == dep_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="یافت نشد")
    return {"receipt_image": d.receipt_image or ""}


class DepositDecision(BaseModel):
    approve: bool
    note: str = ""


@router.post("/admin/deposits/{dep_id}/decide")
async def admin_decide_deposit(dep_id: int, req: DepositDecision, db: Session = Depends(get_db),
                               current_user: models.User = Depends(get_superadmin)):
    d = db.query(models.Deposit).filter(models.Deposit.id == dep_id).first()
    if not d or d.status != "pending":
        raise HTTPException(status_code=404, detail="درخواست یافت نشد یا قبلاً پردازش شده")
    u = db.query(models.User).filter(models.User.id == d.user_id).first()
    if req.note:
        d.note = req.note
    d.processed_at = datetime.utcnow()

    if not req.approve:
        d.status = "rejected"
        db.commit()
        if u:
            notify_user(db, u.id, d.purpose == "withdraw" and "withdrawal" or "deposit",
                        "درخواست رد شد", f"درخواست شما تأیید نشد. {req.note}")
        return {"message": "رد شد"}

    d.status = "approved"
    if d.purpose == "withdraw":
        # کسر از کیف پول
        u.wallet_balance_toman = max(0, (u.wallet_balance_toman or 0) - d.amount_toman)
        db.commit()
        notify_user(db, u.id, "withdrawal", "برداشت تأیید شد",
                    f"برداشت {d.amount_toman:,} تومان تأیید و پرداخت شد.")
    elif d.purpose == "invest":
        # سرمایه‌گذاری در استخر managed → صدور واحد
        sub = access.get_active_subscription(db, u.id)
        plan = access.get_plan(db, sub.plan_id) if sub else None
        if sub and plan and plan.plan_type == "managed":
            await pool.issue_units(db, sub, float(d.amount_toman))
        else:
            u.wallet_balance_toman = (u.wallet_balance_toman or 0) + d.amount_toman
        db.commit()
        notify_user(db, u.id, "deposit", "واریز تأیید شد",
                    f"واریز {d.amount_toman:,} تومان تأیید و به سرمایه‌گذاری شما اضافه شد.")
    else:
        # شارژ کیف پول
        u.wallet_balance_toman = (u.wallet_balance_toman or 0) + d.amount_toman
        db.commit()
        notify_user(db, u.id, "deposit", "واریز تأیید شد",
                    f"واریز {d.amount_toman:,} تومان به کیف پول شما اضافه شد.")
    return {"message": "تأیید و اعمال شد"}
