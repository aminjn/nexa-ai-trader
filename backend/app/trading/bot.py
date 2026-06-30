import asyncio
from collections import deque, defaultdict
from contextvars import ContextVar
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

# لاگ فعالیت به تفکیک کاربر (آخرین ۱۵۰ رویداد هر کاربر). کلید ۰ = رویدادهای سیستمی/سراسری
_activity_logs: Dict[int, deque] = defaultdict(lambda: deque(maxlen=150))

# شناسهٔ کاربرِ جاری در تسک ربات (برای آن‌که log_bot_event بداند رویداد برای کیست)
_ctx_user_id: ContextVar[int] = ContextVar("bot_user_id", default=0)


def log_bot_event(message: str, level: str = "info", user_id: Optional[int] = None):
    """ثبت یک رویداد در لاگ فعالیتِ همان کاربر (per-user)."""
    uid = user_id if user_id is not None else _ctx_user_id.get()
    _activity_logs[uid].appendleft({
        "time": datetime.utcnow().isoformat() + "Z",  # UTC با علامت Z برای تبدیل صحیح به زمان تهران
        "message": message,
        "level": level,
    })
    logger.info(f"[user {uid}] {message}")


def get_activity_log(user_id: int, limit: int = 50, include_global: bool = False) -> List[dict]:
    """لاگ فعالیتِ یک کاربر. اگر include_global باشد، رویدادهای سیستمی (کلید ۰) هم ادغام می‌شود."""
    events = list(_activity_logs.get(user_id, []))
    if include_global and user_id != 0:
        events = events + list(_activity_logs.get(0, []))
        events.sort(key=lambda e: e["time"], reverse=True)
    return events[:limit]


async def run_user_bot(user_id: int):
    """Main trading bot loop for a single user."""
    _ctx_user_id.set(user_id)  # همهٔ رویدادهای این تسک به لاگ همین کاربر می‌رود
    while True:
        db = SessionLocal()
        try:
            user = db.query(models.User).filter(models.User.id == user_id).first()
            if not user or not user.bot_active:
                break

            # دروازه‌بانی پلن: اگر اشتراک فعال نباشد (یا منقضی شده باشد) ربات خاموش می‌شود
            from .access import has_access
            if not has_access(db, user):
                user.bot_active = False
                db.commit()
                log_bot_event("⛔ ربات متوقف شد: اشتراک فعالی وجود ندارد یا منقضی شده است", "error")
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

        # بازار را مکرر بررسی می‌کنیم (هر ۲ دقیقه) تا فرصت‌ها از دست نرود.
        # تعدادِ معاملهٔ روزانه جداگانه با سقفِ پلن (can_open_new_trade) محدود می‌شود،
        # نه با فاصله‌انداختنِ بررسی‌ها — وگرنه بات بیشترِ وقت «خواب» می‌ماند.
        await asyncio.sleep(120)


# حداقل ارزش سفارش بر اساس ارز پایه (تقریبی طبق قوانین نوبیتکس)
MIN_ORDER_VALUE = {
    "RLS": 1_100_000.0,   # ~۱۱۰ هزار تومان
    "USDT": 11.0,
}


def _pairs_and_quote(user, balances: dict, coins_override=None):
    """جفت‌ارزها و ارز پایه را انتخاب می‌کند.

    coins_override: اگر داده شود (حالتِ «همهٔ ارزها»)، جایگزینِ لیستِ دستیِ کاربر می‌شود.
    """
    if coins_override:
        coins = [c.upper() for c in coins_override]
    else:
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
    _ctx_user_id.set(user.id)  # رویدادهای این چرخه به لاگ همین کاربر می‌رود
    try:
        from ..exchanges.nobitex import NobitexExchange
        import pandas as pd

        exchange = get_exchange(exch.exchange_name, exch.api_key, exch.api_secret)
        balances = await exchange.get_balance()
        # حالتِ «همهٔ ارزها»: لیستِ کاملِ بازارهای نوبیتکس را پویا بگیر (ارزِ جدید خودکار اضافه می‌شود)
        coins_override = None
        from .markets import wants_all, get_all_nobitex_coins
        if wants_all(getattr(user, "trading_coins", "")):
            coins_override = await get_all_nobitex_coins("IRT")
        pairs, quote = _pairs_and_quote(user, balances, coins_override=coins_override)
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
            df = None
            if trainer.is_trained:
                ohlcv = await exchange.get_ohlcv(pair, "1h", 720)
                if ohlcv:
                    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    ml_signal = trainer.predict(df)
                    ml_conf = ml_signal.get("confidence", 0)

            # ── معامله باز موجود؟ بررسی شرایط خروج ──
            open_trade = find_open(base_code)
            if open_trade:
                gross_pct = (current_price - open_trade.entry_price) / open_trade.entry_price * 100
                # کارمزد رفت‌وبرگشت نوبیتکس (خرید + فروش) از سود/زیان کم می‌شود (اگر صفر بود، حداقل ۰.۲۵٪ پایه)
                fee_pct = (getattr(user, "fee_pct", 0.25) or 0.25)
                round_trip_fee = 2 * fee_pct
                change_pct = gross_pct - round_trip_fee  # سود/زیان خالص پس از کارمزد
                # حداقل سود خالصِ لازم برای خروجِ سوددهانه (پوشش لغزش بازارِ سفارش market)
                min_exit = max(0.5, round_trip_fee + 0.3)

                # ── حد ضررِ متحرک (trailing): بیشترین قیمت را دنبال کن تا برنده‌ها بدوند ──
                if open_trade.peak_price is None or current_price > open_trade.peak_price:
                    open_trade.peak_price = current_price
                    db.commit()
                peak = open_trade.peak_price or open_trade.entry_price
                peak_pct = (peak - open_trade.entry_price) / open_trade.entry_price * 100  # اوجِ سودِ ناخالص
                drop_from_peak = ((peak - current_price) / peak * 100) if peak else 0.0
                trail_pct = max(0.8, user.stop_loss * 0.6)   # فاصلهٔ دنبال‌کننده از قله

                reason = None
                if change_pct <= -user.stop_loss:
                    reason = f"حد ضرر (خالص {change_pct:+.2f}٪)"
                elif peak_pct >= user.target_profit and drop_from_peak >= trail_pct and change_pct >= min_exit:
                    # به هدف رسید و حالا با عقب‌نشینی از قله، سودِ بزرگ‌تر را قفل می‌کند
                    reason = f"حد ضررِ متحرک (قله {peak_pct:.1f}٪ → خروجِ خالص {change_pct:+.2f}٪)"
                elif (getattr(user, "ml_exit_enabled", False) and ml_signal
                      and ml_signal["signal"] == "SELL" and ml_conf >= trainer.confidence_threshold
                      and change_pct >= max(min_exit, user.stop_loss)):
                    # خروجِ ML فقط وقتی سودِ خالص دستِ‌کم به‌اندازهٔ فاصلهٔ حد ضرر باشد.
                    # (وگرنه برنده‌ها کوچک بسته می‌شوند و بازنده‌ها کامل ضرر می‌کنند →
                    #  با وجودِ نرخِ بردِ بالا، حساب آب می‌رود. این تقارن را تضمین می‌کند.)
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
                        # ── حساب‌داری پولیِ دقیق (قیمت‌ها ریال؛ به تومان تبدیل می‌شود) ──
                        rial_to_toman = 10.0 if quote == "RLS" else 1.0  # بازار RLS ریال است
                        cost_toman = (open_trade.entry_price * sell_amount) / rial_to_toman
                        proceeds_toman = (current_price * sell_amount) / rial_to_toman
                        fee_toman = (cost_toman + proceeds_toman) * fee_pct / 100.0
                        net_pnl = proceeds_toman - cost_toman - fee_toman   # سود/زیان خالصِ پولی (تومان)
                        open_trade.cost_toman = round(cost_toman, 2)
                        open_trade.proceeds_toman = round(proceeds_toman, 2)
                        open_trade.fee_toman = round(fee_toman, 2)
                        open_trade.pnl = round(net_pnl, 2)
                        open_trade.pnl_pct = round((net_pnl / cost_toman * 100.0) if cost_toman else change_pct, 3)
                        open_trade.status = "closed"
                        open_trade.closed_at = datetime.utcnow()
                        db.commit()
                        log_bot_event(
                            f"🔴 فروش {pair} | مقدار {sell_amount} | دلیل: {reason} | "
                            f"خالص {net_pnl:+,.0f} ت (کارمزد {fee_toman:,.0f} ت)"
                        )
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

            # ── جهت را ML تعیین می‌کند: ورودِ ساده و پرتکرار روی سیگنالِ خرید ──
            # (بدون گِیتِ خودبهینه‌ساز/محافظ/فیلترِ سخت‌گیرانه — معاملهٔ کوچک و زیاد در روز)
            if ml_signal["signal"] != "BUY":
                continue

            # سقف معاملهٔ روزانهٔ پلن (مثلاً پلن ۳ روزه: ۵ معامله در روز)
            from .access import can_open_new_trade
            if not can_open_new_trade(db, user):
                log_bot_event(f"🚦 {pair}: به سقف معاملهٔ روزانهٔ پلن رسیده‌اید — معاملهٔ جدید باز نمی‌شود")
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
                rial_to_toman = 10.0 if quote == "RLS" else 1.0
                trade = models.Trade(
                    user_id=user.id,
                    exchange=exch.exchange_name,
                    pair=pair,
                    side="buy",
                    entry_price=current_price,
                    peak_price=current_price,
                    amount=amount,
                    cost_toman=round((current_price * amount) / rial_to_toman, 2),
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
