from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..exchanges.nobitex import get_exchange
import httpx

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    total_trades = db.query(models.Trade).filter(models.Trade.user_id == current_user.id).count()
    closed_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "closed"
    ).all()

    total_pnl = sum(t.pnl or 0 for t in closed_trades)
    profitable = sum(1 for t in closed_trades if (t.pnl or 0) > 0)
    win_rate = (profitable / len(closed_trades) * 100) if closed_trades else 0

    today = datetime.utcnow().replace(hour=0, minute=0, second=0)
    today_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.opened_at >= today
    ).count()

    today_pnl = sum(
        t.pnl or 0 for t in closed_trades
        if t.closed_at and t.closed_at >= today
    )

    # Get exchange balance
    total_balance = 0
    exchanges = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).all()
    for exch in exchanges:
        total_balance += exch.balance or 0

    return {
        "total_equity": round(total_balance, 2),
        "today_pnl": round(today_pnl, 4),
        "today_pnl_pct": round(today_pnl / max(total_balance, 1) * 100, 2),
        "total_trades_24h": today_trades,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 4),
        "total_trades": total_trades,
        "bot_active": current_user.bot_active,
    }


@router.get("/equity-curve")
async def get_equity_curve(
    days: int = 90,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    start = datetime.utcnow() - timedelta(days=days)
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "closed",
        models.Trade.closed_at >= start,
    ).order_by(models.Trade.closed_at).all()

    # Build cumulative equity curve
    equity = 1000.0
    points = [{"date": start.strftime("%Y-%m-%d"), "value": equity}]
    for trade in trades:
        equity += trade.pnl or 0
        points.append({
            "date": trade.closed_at.strftime("%Y-%m-%d"),
            "value": round(equity, 2)
        })
    return {"data": points}


@router.get("/recent-trades")
async def get_recent_trades(
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id
    ).order_by(models.Trade.opened_at.desc()).limit(limit).all()

    return [{
        "id": t.id,
        "pair": t.pair,
        "side": t.side,
        "entry": t.entry_price,
        "exit": t.exit_price,
        "pnl": t.pnl,
        "pnl_pct": t.pnl_pct,
        "status": t.status,
        "opened_at": t.opened_at,
        "exchange": t.exchange,
        "ai_assisted": t.ai_assisted,
    } for t in trades]


@router.get("/btc-price")
async def get_btc_price():
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.binance.com/api/v3/ticker/price",
                params={"symbol": "BTCUSDT"}
            )
            data = resp.json()
            return {"price": float(data.get("price", 0))}
    except Exception:
        return {"price": 0}
