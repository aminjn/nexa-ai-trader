from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, get_superadmin
from ..auth.service import create_user, get_password_hash
from ..trading.bot import start_user_bot, stop_user_bot, get_active_bot_count
from ..exchanges.nobitex import get_exchange

router = APIRouter(prefix="/admin", tags=["admin"])


async def _live_balance_toman(exchanges) -> float:
    """مجموع موجودی واقعی کیف‌پول‌های کاربر را به تومان از صرافی می‌گیرد."""
    total = 0.0
    for e in exchanges:
        if not e.is_active:
            continue
        try:
            ex = get_exchange(e.exchange_name, e.api_key, e.api_secret)
            total += await ex.get_portfolio_value_toman()
        except Exception:
            total += (e.balance or 0)
    return total


class CreateUserRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    password: str = "User@12345"
    full_name: str = "کاربر جدید"


class SystemSettingsUpdate(BaseModel):
    # Accept both frontend names (short) and backend names (long)
    max_profit: Optional[float] = None
    max_profit_per_trade: Optional[float] = None
    max_trades_per_day: int = 120
    max_leverage: int = 10
    platform_fee: Optional[float] = None
    platform_fee_pct: Optional[float] = None
    auto_approve: Optional[bool] = None
    auto_approve_users: Optional[bool] = None
    require_kyc: bool = False
    allow_short: bool = True
    allow_futures: bool = True
    maintenance_mode: bool = False


@router.get("/stats")
async def get_admin_stats(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    total_users = db.query(models.User).filter(models.User.is_superadmin == False).count()
    active_bots = get_active_bot_count()
    total_trades = db.query(models.Trade).count()
    closed_trades = db.query(models.Trade).filter(models.Trade.status == "closed").all()
    total_pnl = sum(t.pnl or 0 for t in closed_trades)

    # موجودی کل پلتفرم = مجموع موجودی واقعی همهٔ صرافی‌های فعال (تومان)
    exchanges = db.query(models.ExchangeAPI).filter(models.ExchangeAPI.is_active == True).all()
    platform_balance = await _live_balance_toman(exchanges)

    return {
        "total_users": total_users,
        "active_bots": active_bots,
        "total_trades": total_trades,
        "platform_pnl": round(total_pnl, 2),
        "platform_balance": round(platform_balance, 2),
    }


@router.get("/users")
async def list_users(
    page: int = 1,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    query = db.query(models.User).filter(models.User.is_superadmin == False)
    total = query.count()
    users = query.order_by(models.User.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    result = []
    for u in users:
        trades = db.query(models.Trade).filter(
            models.Trade.user_id == u.id,
            models.Trade.status == "closed"
        ).all()
        pnl = sum(t.pnl or 0 for t in trades)

        exchanges = db.query(models.ExchangeAPI).filter(
            models.ExchangeAPI.user_id == u.id
        ).all()
        balance = await _live_balance_toman(exchanges)

        result.append({
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email or u.phone,
            "phone": u.phone,
            "is_active": u.is_active,
            "bot_active": u.bot_active,
            "balance": round(balance, 2),
            "pnl": round(pnl, 2),
            "exchanges_count": len(exchanges),
            "created_at": u.created_at,
        })
    return result


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")

    trades = db.query(models.Trade).filter(
        models.Trade.user_id == user_id,
        models.Trade.status == "closed"
    ).all()
    total_pnl = sum(t.pnl or 0 for t in trades)
    profitable = sum(1 for t in trades if (t.pnl or 0) > 0)
    win_rate = (profitable / len(trades) * 100) if trades else 0

    # Today's PnL
    today = datetime.utcnow().date()
    today_trades = [t for t in trades if t.closed_at and t.closed_at.date() == today]
    today_pnl = sum(t.pnl or 0 for t in today_trades)

    exchanges = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == user_id
    ).all()
    balance = await _live_balance_toman(exchanges)

    recent_trades = db.query(models.Trade).filter(
        models.Trade.user_id == user_id
    ).order_by(models.Trade.opened_at.desc()).limit(10).all()

    # Build simple equity curve from cumulative PnL over last 30 days
    from datetime import timedelta
    equity_points = []
    running = balance - total_pnl
    sorted_trades = sorted([t for t in trades if t.closed_at], key=lambda t: t.closed_at)
    trade_idx = 0
    for i in range(30, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        while trade_idx < len(sorted_trades) and sorted_trades[trade_idx].closed_at and sorted_trades[trade_idx].closed_at.date() <= day:
            running += sorted_trades[trade_idx].pnl or 0
            trade_idx += 1
        equity_points.append({"date": day.strftime("%b %d"), "value": round(running, 2)})

    status = "active" if user.bot_active else ("paused" if user.is_active else "inactive")

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email or user.phone,
        "phone": user.phone,
        "status": status,
        "is_active": user.is_active,
        "bot_active": user.bot_active,
        "balance": round(balance, 2),
        "pnl": round(total_pnl, 4),
        "today_pnl": round(today_pnl, 4),
        "total_trades": len(trades),
        "win_rate": round(win_rate, 1),
        "created_at": user.created_at,
        "equity_curve": equity_points,
        "exchanges": [{
            "id": str(e.id),
            "name": e.exchange_name,
            "api_key": e.api_key,
            "status": "connected" if e.is_active else "disconnected",
            "balance": e.balance,
        } for e in exchanges],
        "recent_trades": [{
            "id": str(t.id),
            "pair": t.pair,
            "side": t.side.upper() if t.side else "BUY",
            "pnl": t.pnl or 0,
            "created_at": t.opened_at.isoformat() if t.opened_at else None,
        } for t in recent_trades],
    }


@router.post("/users")
async def create_new_user(
    req: CreateUserRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    user = create_user(
        db,
        email=req.email,
        phone=req.phone,
        password=req.password,
        full_name=req.full_name,
    )
    return {"id": user.id, "message": "کاربر ایجاد شد"}


@router.put("/users/{user_id}/toggle-bot")
async def toggle_user_bot(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    user.bot_active = not user.bot_active
    db.commit()
    if user.bot_active:
        start_user_bot(user_id)
    else:
        stop_user_bot(user_id)
    return {"bot_active": user.bot_active}


@router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="کاربر یافت نشد")
    user.is_active = not user.is_active
    if not user.is_active:
        user.bot_active = False
        stop_user_bot(user_id)
    db.commit()
    return {"is_active": user.is_active}


@router.get("/settings")
async def get_settings(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    settings_obj = db.query(models.SystemSettings).first()
    if not settings_obj:
        settings_obj = models.SystemSettings()
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return {
        "max_profit": settings_obj.max_profit_per_trade,
        "max_profit_per_trade": settings_obj.max_profit_per_trade,
        "max_trades_per_day": settings_obj.max_trades_per_day,
        "max_leverage": settings_obj.max_leverage,
        "platform_fee": settings_obj.platform_fee_pct,
        "platform_fee_pct": settings_obj.platform_fee_pct,
        "auto_approve": settings_obj.auto_approve_users,
        "auto_approve_users": settings_obj.auto_approve_users,
        "require_kyc": settings_obj.require_kyc,
        "allow_short": settings_obj.allow_short,
        "allow_futures": settings_obj.allow_futures,
        "maintenance_mode": settings_obj.maintenance_mode,
    }


@router.put("/settings")
async def update_settings(
    req: SystemSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_superadmin)
):
    settings_obj = db.query(models.SystemSettings).first()
    if not settings_obj:
        settings_obj = models.SystemSettings()
        db.add(settings_obj)

    settings_obj.max_profit_per_trade = req.max_profit or req.max_profit_per_trade or settings_obj.max_profit_per_trade
    settings_obj.max_trades_per_day = req.max_trades_per_day
    settings_obj.max_leverage = req.max_leverage
    settings_obj.platform_fee_pct = req.platform_fee or req.platform_fee_pct or settings_obj.platform_fee_pct
    settings_obj.auto_approve_users = req.auto_approve if req.auto_approve is not None else (req.auto_approve_users if req.auto_approve_users is not None else settings_obj.auto_approve_users)
    settings_obj.require_kyc = req.require_kyc
    settings_obj.allow_short = req.allow_short
    settings_obj.allow_futures = req.allow_futures
    settings_obj.maintenance_mode = req.maintenance_mode
    settings_obj.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "تنظیمات ذخیره شد"}
