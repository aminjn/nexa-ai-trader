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
    ml_exit_enabled: bool = False
    trading_coins: str = "BTC,ETH"
    fee_pct: float = 0.2


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
        "ml_exit_enabled": current_user.ml_exit_enabled,
        "trading_coins": current_user.trading_coins,
        "fee_pct": current_user.fee_pct,
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
    current_user.ml_exit_enabled = data.ml_exit_enabled
    if data.trading_coins is not None:
        current_user.trading_coins = data.trading_coins
    # توجه: fee_pct دستی ذخیره نمی‌شود؛ سیستم هوشمند کمیسیون آن را خودکار از حجم معاملات تنظیم می‌کند
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """لاگ فعالیت ربات — هر کاربر فقط فعالیت خودش را می‌بیند؛ سوپر ادمین همه را."""
    include_global = bool(current_user.is_superadmin)
    return {"events": get_activity_log(current_user.id, 50, include_global=include_global)}


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


@router.post("/import-positions")
async def import_positions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """خریدهای انجام‌شده در نوبیتکس را که در سیستم ثبت نشده‌اند، به‌عنوان معامله باز وارد می‌کند."""
    from ..trading.bot import log_bot_event
    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    if not exch_rec:
        return {"imported": 0, "message": "صرافی متصل نیست"}

    exchange = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
    if not hasattr(exchange, "get_recent_orders"):
        return {"imported": 0, "message": "پشتیبانی نمی‌شود"}

    orders = await exchange.get_recent_orders(only_buy=True)
    existing_ids = {t.order_id for t in db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id).all() if t.order_id}

    imported = 0
    for o in orders:
        oid = str(o.get("id", ""))
        if not oid or oid in existing_ids:
            continue
        from ..exchanges.nobitex import NobitexExchange
        src = NobitexExchange._code(o.get("srcCurrency", "")).upper()
        dst = NobitexExchange._code(o.get("dstCurrency", "")).upper()
        if dst in ("RLS", "IRR"):
            dst = "RLS"
        pair = f"{src}/{dst}"
        try:
            entry = float(o.get("averagePrice") or o.get("price") or 0)
            amount = float(o.get("matchedAmount") or o.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        if entry <= 0 or amount <= 0:
            continue
        trade = models.Trade(
            user_id=current_user.id,
            exchange=exch_rec.exchange_name,
            pair=pair, side="buy",
            entry_price=entry, amount=amount,
            status="open", trade_type="spot",
            ai_assisted=False, order_id=oid,
        )
        db.add(trade)
        imported += 1
    db.commit()
    if imported:
        log_bot_event(f"📥 {imported} معامله از نوبیتکس وارد سیستم شد")
    return {"imported": imported, "message": f"{imported} معامله وارد شد"}


class TestTradeRequest(BaseModel):
    pair: str = "BTC/RLS"


@router.post("/close-trade/{trade_id}")
async def close_trade(
    trade_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """بستنِ دستیِ یک معاملهٔ باز (فروشِ فوریِ بازار) — مثلِ خروجِ خودکارِ ربات حساب می‌شود."""
    import math
    from datetime import datetime
    from ..trading.bot import log_bot_event
    from ..exchanges.nobitex import NobitexExchange

    trade = db.query(models.Trade).filter(
        models.Trade.id == trade_id,
        models.Trade.user_id == current_user.id,
        models.Trade.status == "open",
    ).first()
    if not trade:
        return {"ok": False, "message": "معاملهٔ بازی با این شناسه پیدا نشد"}

    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    if not exch_rec:
        return {"ok": False, "message": "هیچ صرافی متصلی وجود ندارد"}

    exchange = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
    pair = trade.pair or ""
    quote = pair.split("/")[1].upper() if "/" in pair else "RLS"
    base = pair.split("/")[0] if "/" in pair else pair
    base_code = NobitexExchange._code(base)

    # مقدارِ قابلِ فروش = کمینهٔ ثبت‌شده و موجودیِ واقعی
    try:
        balances = await exchange.get_balance()
        coin_bal = balances.get(base_code.upper())
        free_coin = coin_bal.free if coin_bal else 0.0
    except Exception as e:
        return {"ok": False, "message": f"خطا در دریافت موجودی: {str(e)[:120]}"}
    sell_amount = min(trade.amount, free_coin) if free_coin > 0 else trade.amount
    sell_amount = math.floor(sell_amount * 1e6) / 1e6
    if sell_amount <= 0:
        return {"ok": False, "message": "موجودی سکه برای فروش کافی نیست (شاید قبلاً فروخته شده)"}

    ticker = await exchange.get_ticker(pair)
    cur = ticker.get("last", 0) or 0
    try:
        await exchange.create_market_order(pair, "sell", sell_amount)
    except Exception as e:
        return {"ok": False, "message": f"فروش ناموفق بود: {str(e)[:150]}"}

    # حساب‌داریِ پولیِ دقیق — دقیقاً مثل خروجِ خودکارِ ربات
    fee_pct = (getattr(current_user, "fee_pct", 0.25) or 0.25)
    rial_to_toman = 10.0 if quote in ("RLS", "IRT", "IRR") else 1.0
    cost_toman = (trade.entry_price * sell_amount) / rial_to_toman
    proceeds_toman = (cur * sell_amount) / rial_to_toman
    fee_toman = (cost_toman + proceeds_toman) * fee_pct / 100.0
    net_pnl = proceeds_toman - cost_toman - fee_toman
    trade.exit_price = cur
    trade.cost_toman = round(cost_toman, 2)
    trade.proceeds_toman = round(proceeds_toman, 2)
    trade.fee_toman = round(fee_toman, 2)
    trade.pnl = round(net_pnl, 2)
    trade.pnl_pct = round((net_pnl / cost_toman * 100.0) if cost_toman else 0, 3)
    trade.status = "closed"
    trade.closed_at = datetime.utcnow()
    db.commit()
    log_bot_event(f"🟠 بستنِ دستی {pair} | مقدار {sell_amount} | خالص {net_pnl:+,.0f} ت",
                  user_id=current_user.id)
    return {"ok": True, "message": f"معامله بسته شد — سود/زیان خالص {net_pnl:+,.0f} تومان",
            "pnl": round(net_pnl, 2)}


@router.post("/bot/test-trade")
async def test_trade(
    req: TestTradeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """یک سفارش خرید واقعی با حداقل مبلغ ثبت می‌کند تا سفارش‌گذاری تست شود.

    ⚠️ این یک سفارش واقعی با پول واقعی است.
    """
    from ..trading.bot import MIN_ORDER_VALUE, log_bot_event
    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    if not exch_rec:
        return {"ok": False, "message": "هیچ صرافی متصلی وجود ندارد"}

    exchange = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
    pair = req.pair
    quote = pair.split("/")[1].upper()
    min_value = MIN_ORDER_VALUE.get(quote, 0.0)

    # موجودی
    try:
        balances = await exchange.get_balance()
        qbal = balances.get(quote)
        free = qbal.free if qbal else 0.0
    except Exception as e:
        return {"ok": False, "message": f"خطا در دریافت موجودی: {e}"}

    if free < min_value:
        return {"ok": False, "message": f"موجودی {quote} ({free:,.0f}) کمتر از حداقل سفارش ({min_value:,.0f}) است"}

    ticker = await exchange.get_ticker(pair)
    price = ticker.get("last", 0)
    if not price:
        return {"ok": False, "message": "قیمت لحظه‌ای دریافت نشد"}

    spend = min_value * 1.05  # کمی بالاتر از حداقل
    amount = round(spend / price, 6)
    try:
        order = await exchange.create_market_order(pair, "buy", amount)
        trade = models.Trade(
            user_id=current_user.id,
            exchange=exch_rec.exchange_name,
            pair=pair, side="buy",
            entry_price=price, amount=amount,
            status="open", trade_type="spot",
            ai_assisted=False, order_id=order.order_id,
        )
        db.add(trade)
        db.commit()
        log_bot_event(f"🧪 تست معامله موفق: خرید {pair} | مقدار {amount} | قیمت {price:,.0f}")
        return {"ok": True, "message": f"سفارش خرید واقعی ثبت شد ✓ | مقدار: {amount} {pair.split('/')[0]} | شناسه: {order.order_id}"}
    except Exception as e:
        log_bot_event(f"🧪 تست معامله ناموفق: {str(e)[:100]}", "error")
        return {"ok": False, "message": f"ثبت سفارش ناموفق بود: {str(e)[:150]}"}
