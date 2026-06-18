import asyncio
from collections import deque
from datetime import datetime
from typing import Dict, Optional, List
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

# لاگ فعالیت برای نمایش داخل پنل (آخرین ۱۵۰ رویداد)
_activity_log: deque = deque(maxlen=150)


def log_bot_event(message: str, level: str = "info"):
    """ثبت یک رویداد در لاگ فعالیت قابل‌مشاهده در پنل."""
    _activity_log.appendleft({
        "time": datetime.utcnow().isoformat(),
        "message": message,
        "level": level,
    })
    logger.info(message)


def get_activity_log(limit: int = 50) -> List[dict]:
    return list(_activity_log)[:limit]


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


# حداقل ارزش سفارش بر اساس ارز پایه (تقریبی طبق قوانین نوبیتکس)
MIN_ORDER_VALUE = {
    "RLS": 1_100_000.0,   # ~۱۱۰ هزار تومان
    "USDT": 11.0,
}


def _pairs_and_quote(market_type: str, balances: dict):
    """جفت‌ارزها و ارز پایه را بر اساس موجودی انتخاب می‌کند."""
    rls = balances.get("RLS")
    usdt = balances.get("USDT")
    if rls and rls.free > 0:
        return ["BTC/RLS", "ETH/RLS"], "RLS"
    if usdt and usdt.free > 0:
        return ["BTC/USDT", "ETH/USDT"], "USDT"
    # پیش‌فرض ریالی
    return ["BTC/RLS", "ETH/RLS"], "RLS"


async def run_trading_cycle(db: Session, user: models.User, exch: models.ExchangeAPI):
    """یک چرخه معاملاتی: بستن معاملات باز در سود/ضرر، و باز کردن معامله جدید."""
    try:
        exchange = get_exchange(exch.exchange_name, exch.api_key, exch.api_secret)
        balances = await exchange.get_balance()
        pairs, quote = _pairs_and_quote(user.market_type, balances)
        quote_free = balances[quote].free if balances.get(quote) else 0.0
        min_value = MIN_ORDER_VALUE.get(quote, 0.0)
        trainer = get_trainer()
        log_bot_event(f"🔍 بررسی بازار {' و '.join(pairs)} | موجودی قابل‌معامله: {quote_free:,.0f} {quote}")

        for pair in pairs:
            ticker = await exchange.get_ticker(pair)
            current_price = ticker.get("last", 0)
            if not current_price:
                continue

            # ── معامله باز موجود؟ بررسی سود/ضرر برای بستن ──
            open_trade = db.query(models.Trade).filter(
                models.Trade.user_id == user.id,
                models.Trade.pair == pair,
                models.Trade.status == "open",
            ).first()

            if open_trade:
                change_pct = (current_price - open_trade.entry_price) / open_trade.entry_price * 100
                if change_pct >= user.target_profit or change_pct <= -user.stop_loss:
                    try:
                        order = await exchange.create_market_order(pair, "sell", open_trade.amount)
                        open_trade.exit_price = current_price
                        open_trade.pnl_pct = round(change_pct, 3)
                        open_trade.pnl = round((current_price - open_trade.entry_price) * open_trade.amount, 2)
                        open_trade.status = "closed"
                        open_trade.closed_at = datetime.utcnow()
                        db.commit()
                        log_bot_event(f"🔴 فروش {pair} | سود/زیان: {change_pct:.2f}٪")
                    except Exception as e:
                        log_bot_event(f"خطا در فروش {pair}: {str(e)[:80]}", "error")
                continue  # تا وقتی معامله باز است، معامله جدید باز نمی‌کنیم

            # ── سیگنال برای باز کردن معامله جدید ──
            ohlcv = await exchange.get_ohlcv(pair, "1h", 200)
            if not ohlcv:
                continue

            ml_signal = {"signal": "WAIT", "confidence": 0.0}
            if trainer.is_trained:
                import pandas as pd
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                ml_signal = trainer.predict(df)

            final_signal = ml_signal["signal"]

            if user.ai_trading_enabled and final_signal == "BUY":
                try:
                    strategy = {
                        "target_profit": user.target_profit,
                        "stop_loss": user.stop_loss,
                        "market_type": user.market_type,
                    }
                    ai_result = await analyze_market_for_trade(pair, current_price, ohlcv, strategy, db=db)
                    if ai_result["signal"] != "BUY":
                        final_signal = "WAIT"
                except Exception:
                    pass

            if final_signal == "BUY" and quote_free > min_value:
                spend = quote_free * (user.capital_pct / 100) / len(pairs)
                if spend < min_value:
                    spend = min(quote_free, min_value)
                if spend < min_value:
                    continue  # موجودی کافی نیست
                amount = round(spend / current_price, 6)
                try:
                    order = await exchange.create_market_order(pair, "buy", amount)
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
                    quote_free -= spend
                    log_bot_event(f"🟢 خرید {pair} | مقدار: {amount} | قیمت: {current_price:,.0f}")
                except Exception as e:
                    log_bot_event(f"خطا در خرید {pair}: {str(e)[:80]}", "error")

    except Exception as e:
        logger.error(f"Trading cycle error: {e}")


def start_user_bot(user_id: int):
    if user_id not in _active_bots or _active_bots[user_id].done():
        task = asyncio.create_task(run_user_bot(user_id))
        _active_bots[user_id] = task
        log_bot_event("✅ ربات فعال شد")


def stop_user_bot(user_id: int):
    if user_id in _active_bots:
        _active_bots[user_id].cancel()
        del _active_bots[user_id]
        log_bot_event("⏸ ربات متوقف شد")


def get_active_bot_count() -> int:
    return sum(1 for t in _active_bots.values() if not t.done())
