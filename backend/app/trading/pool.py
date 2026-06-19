"""حساب استخر مدیریت‌شده (managed pool) — حسابداری واحد/سهم.

یک حساب نوبیتکس به‌عنوان «استخر» علامت‌گذاری می‌شود؛ پول واریزی همهٔ کاربرانِ
پلن managed در همان است و ربات روی همان معامله می‌کند.

هر کاربر به نسبت واریزی‌اش «واحد» می‌گیرد:
    قیمت هر واحد = ارزش کل استخر (تومان) ÷ مجموع واحدها
    ارزش کاربر    = واحدهای کاربر × قیمت واحد
    سود کاربر     = ارزش کاربر − واریزی

قیمت اولیهٔ هر واحد ۱ تومان است (۱ واحد = ۱ تومان) تا اولین واریز.
"""
from .. import models
from ..exchanges.nobitex import get_exchange


def get_pool_exchange(db):
    """حساب صرافیِ علامت‌خوردهٔ استخر را برمی‌گرداند (یا None)."""
    return db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.is_pool == True,
        models.ExchangeAPI.is_active == True,
    ).first()


async def pool_value_toman(db) -> float:
    """ارزش زندهٔ کل استخر به تومان (از حساب نوبیتکس استخر)."""
    ex_rec = get_pool_exchange(db)
    if not ex_rec:
        return 0.0
    try:
        ex = get_exchange(ex_rec.exchange_name, ex_rec.api_key, ex_rec.api_secret)
        return await ex.get_portfolio_value_toman()
    except Exception:
        return 0.0


def _active_managed_subs(db):
    subs = db.query(models.TradingSubscription).filter(
        models.TradingSubscription.status == "active",
    ).all()
    out = []
    for s in subs:
        p = db.query(models.TradingPlan).filter(models.TradingPlan.id == s.plan_id).first()
        if p and p.plan_type == "managed":
            out.append(s)
    return out


def total_units(db) -> float:
    return sum((s.units or 0.0) for s in _active_managed_subs(db))


async def unit_price(db) -> float:
    """قیمت هر واحد به تومان. اگر هنوز واحدی صادر نشده، ۱.۰."""
    u = total_units(db)
    if u <= 0:
        return 1.0
    val = await pool_value_toman(db)
    if val <= 0:
        return 1.0  # اگر ارزش قابل‌خواندن نبود، از تغییر قیمت واحد پرهیز کن
    return val / u


async def issue_units(db, sub, deposit_toman: float):
    """به ازای واریزی، واحد صادر می‌کند (با قیمت فعلی واحد)."""
    price = await unit_price(db)
    if price <= 0:
        price = 1.0
    sub.units = (sub.units or 0.0) + (deposit_toman / price)
    sub.deposit_toman = (sub.deposit_toman or 0) + int(deposit_toman)
    db.commit()
    return sub.units


async def user_value_toman(db, sub) -> float:
    price = await unit_price(db)
    return (sub.units or 0.0) * price


async def managed_commission(db, sub, plan) -> dict:
    """خلاصهٔ ارزش و کارمزد سود یک عضو استخر (بر پایهٔ واحد)."""
    from . import access
    deposit = sub.deposit_toman or 0
    value = await user_value_toman(db, sub)
    profit = value - deposit
    rate = access.commission_rate_for(plan, deposit)
    owed = max(0.0, profit) * rate / 100.0
    settled = sub.commission_settled_toman or 0
    return {
        "applicable": True,
        "rate": rate,
        "deposit": round(deposit),
        "value": round(value),
        "units": round(sub.units or 0.0, 4),
        "profit": round(profit),
        "owed": round(owed),
        "settled": round(settled),
        "remaining": round(max(0.0, owed - settled)),
    }


async def redeem_units(db, sub, plan, amount_toman: float) -> dict:
    """بازخرید واحد به ازای مبلغ درخواستی (۰ = کل موجودی).

    سهم اصل و سود به نسبت واحدهای بازخریدشده جدا می‌شود؛ کارمزد سودِ همان بخش
    کسر و ثبت می‌شود (چون در زمان برداشت محقق شده است).
    """
    from . import access
    price = await unit_price(db)
    if price <= 0:
        price = 1.0
    value = (sub.units or 0.0) * price
    amount = value if (amount_toman <= 0 or amount_toman >= value) else amount_toman
    units_to_redeem = min(sub.units or 0.0, amount / price)
    fraction = (units_to_redeem / sub.units) if (sub.units or 0) > 0 else 1.0
    deposit_removed = (sub.deposit_toman or 0) * fraction
    profit_realized = amount - deposit_removed
    rate = access.commission_rate_for(plan, sub.deposit_toman or 0)
    commission = max(0.0, profit_realized) * rate / 100.0
    payout = amount - commission

    # به‌روزرسانی اشتراک
    sub.units = max(0.0, (sub.units or 0.0) - units_to_redeem)
    sub.deposit_toman = max(0, int((sub.deposit_toman or 0) - deposit_removed))
    sub.commission_settled_toman = (sub.commission_settled_toman or 0) + int(commission)
    if sub.units <= 1e-6:
        sub.status = "expired"
    db.commit()
    return {
        "units_redeemed": round(units_to_redeem, 6),
        "amount": round(amount),
        "commission": round(commission),
        "payout": round(payout),
        "profit_realized": round(profit_realized),
    }


async def pool_summary(db) -> dict:
    ex_rec = get_pool_exchange(db)
    val = await pool_value_toman(db)
    u = total_units(db)
    price = await unit_price(db)
    subs = _active_managed_subs(db)
    deposits = sum((s.deposit_toman or 0) for s in subs)
    return {
        "connected": ex_rec is not None,
        "exchange_id": ex_rec.id if ex_rec else None,
        "value_toman": round(val),
        "total_units": round(u, 4),
        "unit_price": round(price, 6),
        "total_deposits": round(deposits),
        "profit": round(val - deposits),
        "members": len(subs),
    }
