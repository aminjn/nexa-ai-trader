from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from .. import models
from ..database import get_db
from ..auth.router import get_current_user

router = APIRouter(prefix="/history", tags=["history"])


@router.get("/")
async def get_history(
    page: int = 1,
    limit: int = 20,
    side: Optional[str] = None,
    profit_only: bool = False,
    loss_only: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    query = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "closed",
    )
    if side:
        query = query.filter(models.Trade.side == side)
    if profit_only:
        query = query.filter(models.Trade.pnl > 0)
    if loss_only:
        query = query.filter(models.Trade.pnl < 0)

    total = query.count()
    trades = query.order_by(models.Trade.opened_at.desc()).offset((page - 1) * limit).limit(limit).all()

    return {
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
        "trades": [{
            "id": t.id,
            "pair": t.pair,
            "side": t.side,
            "entry": t.entry_price,
            "exit": t.exit_price,
            "amount": t.amount,
            "pnl": t.pnl,
            "pnl_pct": t.pnl_pct,
            "exchange": t.exchange,
            "trade_type": t.trade_type,
            "leverage": t.leverage,
            "ai_assisted": t.ai_assisted,
            "opened_at": t.opened_at,
            "closed_at": t.closed_at,
        } for t in trades]
    }


@router.get("/summary")
async def get_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "closed",
    ).all()

    if not trades:
        return {"total": 0, "profitable": 0, "loss": 0, "win_rate": 0, "total_pnl": 0}

    profitable = [t for t in trades if (t.pnl or 0) > 0]
    return {
        "total": len(trades),
        "profitable": len(profitable),
        "loss": len(trades) - len(profitable),
        "win_rate": round(len(profitable) / len(trades) * 100, 1),
        "total_pnl": round(sum(t.pnl or 0 for t in trades), 4),
        "avg_pnl": round(sum(t.pnl or 0 for t in trades) / len(trades), 4),
    }
