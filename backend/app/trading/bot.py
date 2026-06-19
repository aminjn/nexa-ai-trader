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
        "time": datetime.utcnow().isoformat() + "Z",  # UTC با علامت Z برای تبدیل صحیح به زمان تهران
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


def _pairs_and_quote(user, balances: dict):
    """جفت‌ارزها (از لیست تنظیم‌شده‌ی کاربر) و ارز پایه را بر اساس موجودی انتخاب می‌کند."""
    coins_raw = getattr(user, "trading_coins", "") or "BTC,ETH"
    coins = [c.strip().upper() for c in coins_raw.split(",") if c.strip()]
    if not coins:
        coins = ["BTC", "ETH"]
    rls = balances.get("RLS")
    usdt = balances.get("USDT")
    quote = "RLS" if (rls and rls.free > 0) else ("USDT" if (usdt and usdt.free > 0) else "RLS")
    pairs = [f"{c}/{quote}" for c in coins if c != quote]
    return pairs, quote


async def run_trading_cycle(db: Session, user: models.User, exch: models.ExchangeAPI):
    """یک چرخه معاملاتی: بستن معاملات باز در سود/ضرر/سیگنال فروش، و باز کردن معامله جدید."""
    try:
        from ..exchanges.nobitex import NobitexExchange
        import pandas as pd

        exchange = get_exchange(exch.exchange_name, exch.api_key, exch.api_secret)
        balances = await exchange.get_balance()
        pairs, quote = _pairs_and_quote(user, balances)
        quote_free = balances[quote].free if balances.get(quote) else 0.0
        min_value = MIN_ORDER_VALUE.get(quote, 0.0)
        trainer = get_trainer()

        # همه‌ی معاملات باز کاربر را یک‌بار می‌گیریم و بر اساس «ارز پایه» تطبیق می‌دهیم
        # (مقاوم در برابر هر شکل ذخیره‌شده‌ی جفت‌ارز مثل BTC/RLS یا BTC/ریال)
        open_trades = db.query(models.Trade).filter(
            models.Trade.user_id == user.id,
            models.Trade.status == "open",
        ).all()

        def base_of(p: str) -> str:
            return NobitexExchange._code((p or "").split("/")[0])

        def find_open(base_code: str):
            for ot in open_trades:
                if ot.status == "open" and base_of(ot.pair) == base_code:
                    return ot
            return None

        # جفت‌ارزهای موردبررسی = جفت‌های تنظیم‌شده + هر ارزی که پوزیشن باز دارد
        pair_list = list(pairs)
        for ot in open_trades:
            p = f"{base_of(ot.pair).upper()}/{quote}"
            if p not in pair_list:
                pair_list.append(p)

        log_bot_event(f"🔍 بررسی بازار {' و '.join(pair_list)} | موجودی قابل‌معامله: {quote_free:,.0f} {quote}")

        for pair in pair_list:
            base_code = base_of(pair)
            ticker = await exchange.get_ticker(pair)
            current_price = ticker.get("last", 0)
            if not current_price:
                continue

            # سیگنال ML را یک‌بار محاسبه می‌کنیم (هم برای خروج، هم برای ورود)
            ml_signal = None
            ml_conf = 0.0
            if trainer.is_trained:
                ohlcv = await exchange.get_ohlcv(pair, "1h", 300)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    ml_signal = trainer.predict(df)
                    ml_conf = ml_signal.get("confidence", 0)

            # ── معامله باز موجود؟ بررسی شرایط خروج ──
            open_trade = find_open(base_code)
            if open_trade:
                gross_pct = (current_price - open_trade.entry_price) / open_trade.entry_price * 100
                # کارمزد رفت‌وبرگشت نوبیتکس (خرید + فروش) از سود/زیان کم می‌شود
                round_trip_fee = 2 * (getattr(user, "fee_pct", 0.2) or 0.0)
                change_pct = gross_pct - round_trip_fee  # سود/زیان خالص پس از کارمزد
                reason = None
                if change_pct >= user.target_profit:
                    reason = f"هدف سود (خالص {change_pct:+.2f}٪ پس از کارمزد)"
                elif change_pct <= -user.stop_loss:
                    reason = f"حد ضرر (خالص {change_pct:+.2f}٪)"
                elif (getattr(user, "ml_exit_enabled", False) and ml_signal
                      and ml_signal["signal"] == "SELL" and ml_conf >= trainer.confidence_threshold
                      and change_pct > 0):
                    # خروج با سیگنال ML فقط وقتی پس از کارمزد همچنان سودده است
                    reason = f"سیگنال فروش ML (سود خالص {change_pct:+.2f}٪)"

                if reason:
                    # مقدار قابل‌فروش = کمینه‌ی مقدار ثبت‌شده و موجودی واقعی کیف‌پول.
                    # (هنگام خرید، کارمزد از مقدار سکه کم می‌شود، پس موجودی واقعی کمی کمتر است؛
                    #  تلاش برای فروش بیشتر از موجودی باعث «Order Validation Failed» می‌شود.)
                    import math
                    coin_bal = balances.get(base_code.upper())
                    free_coin = coin_bal.free if coin_bal else 0.0
                    sell_amount = min(open_trade.amount, free_coin) if free_coin > 0 else open_trade.amount
                    # کوتاه‌سازی به ۶ رقم اعشار برای جلوگیری از خطای دقت/کمبود موجودی
                    sell_amount = math.floor(sell_amount * 1e6) / 1e6
                    if sell_amount <= 0:
                        log_bot_event(
                            f"⚠️ {pair}: موجودی {base_code.upper()} برای فروش کافی نیست "
                            f"(ثبت‌شده {open_trade.amount} / در کیف‌پول {free_coin}) — احتمالاً قبلاً فروخته شده",
                            "error",
                        )
                        continue
                    try:
                        await exchange.create_market_order(pair, "sell", sell_amount)
                        open_trade.exit_price = current_price
                        # سود/زیان خالص (پس از کسر کارمزد رفت‌وبرگشت)
                        open_trade.pnl_pct = round(change_pct, 3)
                        open_trade.pnl = round((change_pct / 100.0) * open_trade.entry_price * sell_amount, 2)
                        open_trade.status = "closed"
                        open_trade.closed_at = datetime.utcnow()
                        db.commit()
                        log_bot_event(f"🔴 فروش {pair} | مقدار {sell_amount} | دلیل: {reason}")
                    except Exception as e:
                        log_bot_event(f"خطا در فروش {pair} (مقدار {sell_amount}): {str(e)[:120]}", "error")
                else:
                    sig_txt = ml_signal["signal"] if ml_signal else "—"
                    log_bot_event(
                        f"📉 {pair}: پوزیشن باز | سود/زیان {change_pct:+.2f}٪ | سیگنال ML={sig_txt} "
                        f"| هنوز شرط فروش محقق نشده (هدف {user.target_profit}٪ / حد ضرر {user.stop_loss}٪)"
                    )
                continue  # تا وقتی معامله باز است، معامله جدید باز نمی‌کنیم

            # ── سیگنال برای باز کردن معامله جدید ──
            if not trainer.is_trained:
                log_bot_event(f"⚠️ {pair}: مدل هنوز آموزش ندیده — ابتدا مدل را آموزش بده", "error")
                continue
            if not ml_signal:
                log_bot_event(f"⚠️ {pair}: داده قیمتی دریافت نشد")
                continue

            # ── تصمیم با ML است؛ هوش مصنوعی فقط با تحلیل فاندامنتال کمک می‌کند ──
            fund_score = 0.0
            if user.ai_trading_enabled:
                try:
                    from ..ai.fundamental import get_fundamental
                    fund = await get_fundamental(db, exchange)
                    fund_score = fund.get("score", 0.0)
                except Exception:
                    fund_score = 0.0

            # اطمینان نهایی = اطمینان ML + تقویت/تضعیف فاندامنتال (حداکثر ±۰.۰۵)
            adj_conf = ml_conf + (fund_score * 0.05)
            log_bot_event(
                f"📊 {pair}: تصمیم ML = {ml_signal['signal']} (اطمینان {ml_conf*100:.0f}٪)"
                + (f" | فاندامنتال AI: {fund_score:+.2f}" if user.ai_trading_enabled else "")
            )

            # جهت را ML تعیین می‌کند
            if ml_signal["signal"] != "BUY":
                continue
            # آستانه نهایی روی اطمینان تعدیل‌شده اعمال می‌شود
            if adj_conf < trainer.confidence_threshold:
                log_bot_event(f"⏳ {pair}: اطمینان نهایی ({adj_conf*100:.0f}٪) کمتر از آستانه — صبر")
                continue

            # بررسی موجودی و حداقل سفارش
            if quote_free <= min_value:
                log_bot_event(f"💰 {pair}: موجودی ({quote_free:,.0f}) کمتر از حداقل سفارش ({min_value:,.0f} {quote})")
                continue

            # بافر امن: نوبیتکس برای سفارش بازار بیش از مبلغ خام رزرو می‌کند (کارمزد + لغزش).
            # پس حداکثر ۹۰٪ موجودی را در نظر می‌گیریم تا خطای OverValueOrder ندهد.
            import math
            budget = quote_free * 0.90
            spend = budget * (user.capital_pct / 100)
            if spend < min_value:
                spend = min(budget, min_value)
            if spend < min_value:
                log_bot_event(f"💰 {pair}: مبلغ معامله کمتر از حداقل سفارش است")
                continue
            # کف‌گرد به ۶ رقم اعشار تا مقدار از بودجه بالا نزند
            amount = math.floor((spend / current_price) * 1e6) / 1e6
            if amount <= 0:
                continue
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
                open_trades.append(trade)
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
