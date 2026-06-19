"""منطق دسترسی به ربات معامله‌گر: اشتراک فعال، انقضا، سقف معاملهٔ روزانه و کارمزد سود.

دو نوع پلن:
- self_api: کاربر API خودش را وصل می‌کند؛ سقف معاملهٔ روزانه دارد؛ هزینهٔ ثابت.
- managed: کاربر به حساب ما واریز می‌کند؛ کارمزد سود پله‌ای بر اساس مبلغ واریزی.
"""
from datetime import datetime, timedelta
from .. import models


def get_active_subscription(db, user_id: int):
    """اشتراک فعال و منقضی‌نشدهٔ کاربر را برمی‌گرداند (یا None).

    اشتراک‌های منقضی‌شده را همین‌جا به status=expired به‌روزرسانی می‌کند.
    """
    now = datetime.utcnow()
    subs = db.query(models.TradingSubscription).filter(
        models.TradingSubscription.user_id == user_id,
        models.TradingSubscription.status == "active",
    ).all()
    active = None
    changed = False
    for s in subs:
        if s.end_at and s.end_at < now:
            s.status = "expired"
            changed = True
        else:
            active = s
    if changed:
        db.commit()
    return active


def get_plan(db, plan_id: int):
    return db.query(models.TradingPlan).filter(models.TradingPlan.id == plan_id).first()


def has_access(db, user) -> bool:
    """آیا کاربر اجازهٔ استفاده از پنل/ربات را دارد؟

    شرط: احراز هویت شده باشد و اشتراک فعال داشته باشد (سوپر ادمین همیشه دارد).
    """
    if getattr(user, "is_superadmin", False):
        return True
    if not is_verified(user):
        return False
    return get_active_subscription(db, user.id) is not None


def is_verified(user) -> bool:
    """آیا حساب کاربر احراز هویت شده (یا سوپر ادمین) است؟"""
    return bool(getattr(user, "is_superadmin", False)) or (getattr(user, "kyc_status", "none") == "verified")


def active_plan(db, user):
    """پلن فعالِ کاربر را برمی‌گرداند (یا None). سوپر ادمین → None (نامحدود)."""
    sub = get_active_subscription(db, user.id)
    if not sub:
        return None
    return get_plan(db, sub.plan_id)


def can_use_own_api(db, user) -> bool:
    """آیا کاربر اجازهٔ اتصال API شخصی دارد؟ (پلن فعال از نوع self_api یا allow_own_api)"""
    if getattr(user, "is_superadmin", False):
        return True
    sub = get_active_subscription(db, user.id)
    if not sub:
        return False
    plan = get_plan(db, sub.plan_id)
    return bool(plan and plan.allow_own_api)


def commission_rate_for(plan, deposit_toman: float) -> float:
    """درصد کارمزد سود را بر اساس پله‌های مبلغ واریزی برمی‌گرداند (برای پلن managed)."""
    tiers = plan.commission_tiers or []
    if not tiers:
        return 0.0
    # پله‌ها را از بزرگ‌ترین آستانه به کوچک‌ترین مرتب کن و اولین تطبیق را بردار
    for t in sorted(tiers, key=lambda x: x.get("min_toman", 0), reverse=True):
        if deposit_toman >= (t.get("min_toman", 0) or 0):
            return float(t.get("pct", 0) or 0)
    return float(sorted(tiers, key=lambda x: x.get("min_toman", 0))[0].get("pct", 0) or 0)


def realized_profit_toman(db, user_id: int) -> float:
    """مجموع سود محقق‌شدهٔ کاربر از معاملات بسته‌شده (تومان)."""
    trades = db.query(models.Trade).filter(
        models.Trade.user_id == user_id,
        models.Trade.status == "closed",
    ).all()
    return sum((t.pnl or 0) for t in trades)


def commission_summary(db, user) -> dict:
    """خلاصهٔ کارمزد سودِ پلتفرم برای کاربر (فقط پلن managed)."""
    sub = get_active_subscription(db, user.id)
    empty = {"applicable": False, "rate": 0.0, "deposit": 0, "profit": 0,
             "owed": 0, "settled": 0, "remaining": 0}
    if not sub:
        return empty
    plan = get_plan(db, sub.plan_id)
    if not plan or plan.plan_type != "managed":
        return empty
    deposit = sub.deposit_toman or 0
    rate = commission_rate_for(plan, deposit)
    profit = realized_profit_toman(db, user.id)
    owed = max(0.0, profit) * rate / 100.0   # کارمزد فقط از سود مثبت
    settled = sub.commission_settled_toman or 0
    return {
        "applicable": True,
        "rate": rate,
        "deposit": round(deposit),
        "profit": round(profit),
        "owed": round(owed),
        "settled": round(settled),
        "remaining": round(max(0.0, owed - settled)),
    }


def trades_today(db, user_id: int) -> int:
    start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    return db.query(models.Trade).filter(
        models.Trade.user_id == user_id,
        models.Trade.opened_at >= start,
    ).count()


def trade_owner_id(db, user) -> int:
    """شناسهٔ کاربری که معاملاتِ نمایش‌دادنی به این کاربر تعلق دارد.

    کاربر managed معاملاتِ حساب استخر را می‌بیند (معامله روی همان حساب انجام می‌شود)؛
    بقیه معاملات خودشان را.
    """
    if getattr(user, "is_superadmin", False):
        return user.id
    sub = get_active_subscription(db, user.id)
    if sub:
        plan = get_plan(db, sub.plan_id)
        if plan and plan.plan_type == "managed":
            from .pool import get_pool_exchange
            pool_ex = get_pool_exchange(db)
            if pool_ex:
                return pool_ex.user_id
    return user.id


def can_open_new_trade(db, user) -> bool:
    """آیا با توجه به سقف معاملهٔ روزانهٔ پلن، اجازهٔ باز کردن معاملهٔ جدید هست؟"""
    if getattr(user, "is_superadmin", False):
        return True  # سوپر ادمین هیچ محدودیتی ندارد
    sub = get_active_subscription(db, user.id)
    if not sub:
        return False
    plan = get_plan(db, sub.plan_id)
    if not plan:
        return False
    limit = plan.max_trades_per_day or 0
    if limit <= 0:
        return True  # نامحدود
    return trades_today(db, user.id) < limit
