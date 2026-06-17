import asyncio
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from ..database import SessionLocal
from .. import models
from ..exchanges.nobitex import get_exchange
from ..ml.trainer import get_trainer
from ..ai.gapgpt import analyze_market_for_trade
import logging

logger = logging.getLogger(__name__)

# Active bot tasks per user
_active_bots: Dict[int, asyncio.Task] = {}


async def run_user_bot(user_id: int):
    """Main trading bot loop for a single user."""
    while True:
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user or not user.bot_active:
                break

            exchanges = db.query(models.ExchangeAPI).filter(
                models.ExchangeAPI.user_id == user_id,
                models.ExchangeAPI.is_active == True,
            ).all()

            if not exchanges:
                await asyncio.sleep(60)
                continue

            for exch in exchanges:
                await run_trading_cycle(db, user, exch)

        except Exception as e:
            logger.error(f"Bot error for user {user_id}: {e}")
        finally:
            db.close()

        # Wait between cycles based on trades_per_day setting
        db2 = SessionLocal()
        try:
            u = db2.query(models.User).filter(models.User.id == user_id).first()
            if u:
                interval = max(60, int(86400 / max(1, u.trades_per_day)))
            else:
                interval = 300
        finally:
            db2.close()

        await asyncio.sleep(interval)


async def run_trading_cycle(db: Session, user: models.User, exch: models.ExchangeAPI):
    """Execute one trading cycle for a user on an exchange."""
    try:
        exchange = get_exchange(exch.exchange_name, exch.api_key, exch.api_secret)
        pairs = ["BTC/USDT", "ETH/USDT"]

        for pair in pairs:
            ohlcv = await exchange.get_ohlcv(pair, "1h", 200)
            if not ohlcv:
                continue

            ticker = await exchange.get_ticker(pair)
            current_price = ticker.get("last", 0)
            if not current_price:
                continue

            # Get ML signal
            trainer = get_trainer()
            ml_signal = {"signal": "WAIT", "confidence": 0.0}
            if trainer.is_trained:
                import pandas as pd
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                ml_signal = trainer.predict(df)

            # Optionally get AI signal
            strategy = {
                "target_profit": user.target_profit,
                "stop_loss": user.stop_loss,
                "market_type": user.market_type,
            }

            final_signal = ml_signal["signal"]

            if user.ai_trading_enabled and ml_signal["signal"] != "WAIT":
                try:
                    ai_result = await analyze_market_for_trade(pair, current_price, ohlcv, strategy)
                    if ai_result["signal"] == ml_signal["signal"]:
                        final_signal = ai_result["signal"]
                    else:
                        final_signal = "WAIT"
                except Exception:
                    pass

            if final_signal == "BUY":
                balance = await exchange.get_balance()
                usdt_balance = balance.get("USDT", None)
                if usdt_balance and usdt_balance.free > 10:
                    trade_amount_usdt = usdt_balance.free * (user.capital_pct / 100) * 0.1
                    amount = trade_amount_usdt / current_price

                    order = await exchange.create_market_order(pair, "buy", round(amount, 6))
                    trade = models.Trade(
                        user_id=user.id,
                        exchange=exch.exchange_name,
                        pair=pair,
                        side="buy",
                        entry_price=current_price,
                        amount=amount,
                        status="open",
                        trade_type=user.market_type,
                        ai_assisted=user.ai_trading_enabled,
                        order_id=order.order_id,
                    )
                    db.add(trade)
                    db.commit()

    except Exception as e:
        logger.error(f"Trading cycle error: {e}")


def start_user_bot(user_id: int):
    if user_id not in _active_bots or _active_bots[user_id].done():
        task = asyncio.create_task(run_user_bot(user_id))
        _active_bots[user_id] = task


def stop_user_bot(user_id: int):
    if user_id in _active_bots:
        _active_bots[user_id].cancel()
        del _active_bots[user_id]


def get_active_bot_count() -> int:
    return sum(1 for t in _active_bots.values() if not t.done())
