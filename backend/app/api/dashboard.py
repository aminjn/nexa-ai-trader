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

    # موجودی زنده از صرافی (و به‌روزرسانی مقدار ذخیره‌شده)
    total_balance = 0
    exchanges = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).all()
    for exch in exchanges:
        try:
            ex = get_exchange(exch.exchange_name, exch.api_key, exch.api_secret)
            if hasattr(ex, "get_portfolio_value_toman"):
                live = await ex.get_portfolio_value_toman()
                exch.balance = live
        except Exception:
            pass
        total_balance += exch.balance or 0
    db.commit()

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


@router.get("/holdings")
async def get_holdings(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """دارایی‌های واقعی کاربر در صرافی."""
    out = []
    exchanges = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).all()
    for exch in exchanges:
        try:
            ex = get_exchange(exch.exchange_name, exch.api_key, exch.api_secret)
            if hasattr(ex, "get_holdings"):
                for h in await ex.get_holdings():
                    out.append({**h, "exchange": exch.exchange_name})
        except Exception:
            continue
    return {"holdings": out}


@router.get("/positions")
async def get_positions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """معاملات باز با قیمت فروش هدف و حد ضرر."""
    open_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "open",
    ).all()
    if not open_trades:
        return {"positions": []}

    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    ex = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret) if exch_rec else None

    tp = current_user.target_profit
    sl = current_user.stop_loss
    out = []
    for t in open_trades:
        cur = 0.0
        if ex:
            try:
                cur = (await ex.get_ticker(t.pair)).get("last", 0)
            except Exception:
                cur = 0.0
        entry = t.entry_price or 0
        pnl_pct = ((cur - entry) / entry * 100) if (entry and cur) else 0
        out.append({
            "id": t.id,
            "pair": t.pair,
            "amount": t.amount,
            "entry_price": entry,
            "current_price": cur,
            "target_sell_price": round(entry * (1 + tp / 100), 2),
            "stop_price": round(entry * (1 - sl / 100), 2),
            "pnl_pct": round(pnl_pct, 2),
            "target_profit": tp,
            "stop_loss": sl,
            "opened_at": t.opened_at,
        })
    return {"positions": out}


@router.get("/signals")
async def get_signals(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """سیگنال واقعی فعلی مدل برای جفت‌ارزهای اصلی."""
    from ..ml.trainer import get_trainer
    import pandas as pd
    trainer = get_trainer()
    out = {"trained": trainer.is_trained, "signals": []}
    if not trainer.is_trained:
        return out

    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    if not exch_rec:
        return out

    exchange = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
    label = {"BUY": "خرید", "SELL": "فروش", "WAIT": "صبر"}
    for pair in ["BTC/RLS", "ETH/RLS"]:
        try:
            ohlcv = await exchange.get_ohlcv(pair, "1h", 300)
            if not ohlcv:
                continue
            dfp = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
            dfp["timestamp"] = pd.to_datetime(dfp["timestamp"], unit="ms")
            sig = trainer.predict(dfp)
            out["signals"].append({
                "pair": pair,
                "signal": sig["signal"],
                "signal_fa": label.get(sig["signal"], sig["signal"]),
                "confidence": round(sig.get("confidence", 0) * 100, 1),
            })
        except Exception:
            continue
    return out


@router.get("/btc-price")
async def get_btc_price():
    # از نوبیتکس (مستقیم) قیمت بیت‌کوین به دلار را می‌گیریم
    from ..config import settings
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            resp = await client.get(f"{settings.NOBITEX_BASE_URL}/v3/orderbook/BTCUSDT")
            data = resp.json()
            price = float(data.get("lastTradePrice", 0))
            return {"price": price}
    except Exception:
        return {"price": 0}
