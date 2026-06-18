from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from .. import models
from ..database import get_db
from ..auth.router import get_current_user
from ..trading.bot import start_user_bot, stop_user_bot, get_activity_log, run_trading_cycle
from ..exchanges.nobitex import get_exchange

router = APIRouter(prefix="/strategy", tags=["strategy"])


class StrategyUpdate(BaseModel):
    target_profit: float = 3.5
    trades_per_day: int = 30
    capital_pct: float = 80.0
    stop_loss: float = 1.5
    market_type: str = "spot"
    short_enabled: bool = False
    leverage: int = 3
    ai_trading_enabled: bool = True


@router.get("/")
async def get_strategy(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    return {
        "target_profit": current_user.target_profit,
        "trades_per_day": current_user.trades_per_day,
        "capital_pct": current_user.capital_pct,
        "stop_loss": current_user.stop_loss,
        "market_type": current_user.market_type,
        "short_enabled": current_user.short_enabled,
        "leverage": current_user.leverage,
        "ai_trading_enabled": current_user.ai_trading_enabled,
        "bot_active": current_user.bot_active,
    }


@router.put("/")
async def update_strategy(
    data: StrategyUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.target_profit = data.target_profit
    current_user.trades_per_day = data.trades_per_day
    current_user.capital_pct = data.capital_pct
    current_user.stop_loss = data.stop_loss
    current_user.market_type = data.market_type
    current_user.short_enabled = data.short_enabled
    current_user.leverage = data.leverage
    current_user.ai_trading_enabled = data.ai_trading_enabled
    db.commit()
    return {"message": "استراتژی با موفقیت ذخیره شد"}


@router.post("/bot/toggle")
async def toggle_bot(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    current_user.bot_active = not current_user.bot_active
    db.commit()
    if current_user.bot_active:
        start_user_bot(current_user.id)
    else:
        stop_user_bot(current_user.id)
    return {"bot_active": current_user.bot_active}


@router.get("/activity")
async def get_activity(
    current_user: models.User = Depends(get_current_user)
):
    """لاگ فعالیت ربات برای نمایش در پنل."""
    return {"events": get_activity_log(50)}


@router.post("/bot/run-now")
async def run_now(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """اجرای فوری یک چرخه معامله (برای تست بدون انتظار)."""
    exchanges = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).all()
    if not exchanges:
        return {"message": "هیچ صرافی متصلی وجود ندارد"}
    for exch in exchanges:
        await run_trading_cycle(db, current_user, exch)
    return {"message": "بررسی بازار انجام شد"}
