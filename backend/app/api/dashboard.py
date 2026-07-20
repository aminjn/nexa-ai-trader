from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from .. import models
from ..database import get_db
from ..auth.router import get_current_user, require_active_plan
from ..trading.access import trade_owner_id
from ..exchanges.nobitex import get_exchange
import httpx

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _compute_technical(df):
    """تحلیل تکنیکال متنی بر اساس اندیکاتورها."""
    from ..ml.trainer import add_features
    f = add_features(df).dropna()
    if f.empty:
        return None
    r = f.iloc[-1]
    rsi = float(r["rsi_14"])
    macd_hist = float(r["macd_hist"])
    above_sma50 = float(r["sma_50"]) > 0   # close/sma50 - 1
    above_sma200 = float(r["sma_200"]) > 0
    adx = float(r["adx"])
    stoch = float(r["stoch_k"])
    bb = float(r["bb_pct"])

    signals, score = [], 0
    if rsi < 30:
        signals.append(f"RSI={rsi:.0f} در ناحیه اشباع فروش (سیگنال خرید)"); score += 1
    elif rsi > 70:
        signals.append(f"RSI={rsi:.0f} در ناحیه اشباع خرید (سیگنال فروش)"); score -= 1
    else:
        signals.append(f"RSI={rsi:.0f} خنثی")

    if macd_hist > 0:
        signals.append("MACD صعودی (مومنتوم مثبت)"); score += 1
    else:
        signals.append("MACD نزولی (مومنتوم منفی)"); score -= 1

    if above_sma50:
        signals.append("قیمت بالای میانگین ۵۰ روزه (روند کوتاه‌مدت صعودی)"); score += 1
    else:
        signals.append("قیمت زیر میانگین ۵۰ روزه (روند کوتاه‌مدت نزولی)"); score -= 1

    if above_sma200:
        signals.append("قیمت بالای میانگین ۲۰۰ روزه (روند بلندمدت صعودی)"); score += 1
    else:
        signals.append("قیمت زیر میانگین ۲۰۰ روزه (روند بلندمدت نزولی)"); score -= 1

    if adx > 25:
        signals.append(f"روند قدرتمند است (ADX={adx:.0f})")
    else:
        signals.append(f"روند ضعیف/خنثی (ADX={adx:.0f})")

    if bb < 0.1:
        signals.append("نزدیک باند پایین بولینگر (احتمال برگشت صعودی)"); score += 1
    elif bb > 0.9:
        signals.append("نزدیک باند بالای بولینگر (احتمال برگشت نزولی)"); score -= 1

    conclusion = "صعودی" if score >= 2 else ("نزولی" if score <= -2 else "خنثی")
    return {
        "text": "؛ ".join(signals),
        "conclusion": conclusion,
        "score": score,
        "rsi": round(rsi, 1),
        "adx": round(adx, 1),
    }


@router.get("/stats")
async def get_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    from ..trading import pool
    ms = await pool.managed_share(db, current_user)

    # ── کاربر managed: فقط سهمِ شخصیِ او از استخر ──
    if ms:
        frac = ms["fraction"]
        oid = ms["pool_owner_id"] or current_user.id
        today = datetime.utcnow().replace(hour=0, minute=0, second=0)
        pool_today_pnl = sum(
            (t.pnl or 0) for t in db.query(models.Trade).filter(
                models.Trade.user_id == oid, models.Trade.status == "closed",
                models.Trade.closed_at >= today).all()
        )
        my_value = ms["value"]
        today_pnl = pool_today_pnl * frac
        return {
            "total_equity": round(my_value, 2),
            "free_cash_toman": 0,
            "today_pnl": round(today_pnl, 2),
            "today_pnl_pct": round(today_pnl / max(my_value, 1) * 100, 2),
            "total_trades_24h": 0,
            "win_rate": 0,
            "total_pnl": round(my_value - ms["deposit"], 2),  # سود کل = ارزش − واریزی
            "total_trades": 0,
            "bot_active": current_user.bot_active,
            "managed": True,
        }

    # ── self_api / سوپر ادمین: معاملات خودش ──
    oid = current_user.id
    total_trades = db.query(models.Trade).filter(models.Trade.user_id == oid).count()
    closed_trades = db.query(models.Trade).filter(
        models.Trade.user_id == oid,
        models.Trade.status == "closed"
    ).all()

    total_pnl = sum(t.pnl or 0 for t in closed_trades)
    profitable = sum(1 for t in closed_trades if (t.pnl or 0) > 0)
    win_rate = (profitable / len(closed_trades) * 100) if closed_trades else 0

    today = datetime.utcnow().replace(hour=0, minute=0, second=0)
    today_trades = db.query(models.Trade).filter(
        models.Trade.user_id == oid,
        models.Trade.opened_at >= today
    ).count()

    today_pnl = sum(
        t.pnl or 0 for t in closed_trades
        if t.closed_at and t.closed_at >= today
    )

    # موجودی زنده از صرافی (و به‌روزرسانی مقدار ذخیره‌شده)
    total_balance = 0
    free_cash_toman = 0  # نقد ریالی قابل‌معامله
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
            bals = await ex.get_balance()
            rls = bals.get("RLS")
            if rls:
                free_cash_toman += rls.free / 10.0
        except Exception:
            pass
        total_balance += exch.balance or 0
    db.commit()

    return {
        "total_equity": round(total_balance, 2),
        "free_cash_toman": round(free_cash_toman, 2),
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
    from ..trading import pool
    ms = await pool.managed_share(db, current_user)

    if ms:
        # نمودار دارایی شخصیِ کاربر managed: از واریزی شروع و سهمِ سود استخر اضافه می‌شود
        oid = ms["pool_owner_id"] or current_user.id
        frac = ms["fraction"]
        trades = db.query(models.Trade).filter(
            models.Trade.user_id == oid, models.Trade.status == "closed",
            models.Trade.closed_at >= start,
        ).order_by(models.Trade.closed_at).all()
        equity = float(ms["deposit"])
        points = [{"date": start.strftime("%Y-%m-%d"), "value": round(equity, 2)}]
        for trade in trades:
            equity += (trade.pnl or 0) * frac
            points.append({"date": trade.closed_at.strftime("%Y-%m-%d"), "value": round(equity, 2)})
        return {"data": points}

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
    # کاربر managed معاملات خام استخر را نمی‌بیند (آن‌ها برای همهٔ اعضاست) — فقط سهمِ شخصی‌اش در گزارش
    from ..trading import pool
    if await pool.managed_share(db, current_user):
        return []
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


@router.get("/daily-pnl")
async def daily_pnl(
    days: int = 30,
    start: str = "",
    end: str = "",
    user_id: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """گزارش سود/زیان دقیق روزانه (به وقت تهران) برای بازهٔ دلخواه.

    - days: تعداد روز اخیر (پیش‌فرض ۳۰) — اگر start/end داده شود نادیده گرفته می‌شود.
    - start/end: تاریخ میلادی YYYY-MM-DD برای بازهٔ مشخص.
    - user_id: فقط سوپر ادمین می‌تواند گزارش یک کاربر خاص را بگیرد.
    """
    TEHRAN = timedelta(hours=3, minutes=30)
    from ..trading import pool
    # تعیین صاحبِ گزارش و ضریب سهم:
    #  - سوپر ادمین با user_id → همان کاربر (اگر managed باشد، سهمِ او اعمال می‌شود)
    #  - کاربر managed → سهمِ شخصی از استخر
    #  - بقیه → معاملات خودشان (ضریب ۱)
    if user_id and current_user.is_superadmin:
        target = db.query(models.User).filter(models.User.id == user_id).first() or current_user
    else:
        target = current_user
    oid, frac = await pool.report_scope(db, target)

    # بازهٔ زمانی (به UTC) — ورودی‌ها بر اساس روز تهران تفسیر می‌شوند
    def parse_day(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None
    if start and end:
        s_teh = parse_day(start); e_teh = parse_day(end)
        if not s_teh or not e_teh:
            return {"days": [], "total_pnl": 0, "error": "تاریخ نامعتبر است"}
        start_utc = s_teh - TEHRAN
        end_utc = (e_teh + timedelta(days=1)) - TEHRAN
    else:
        days = max(1, min(days, 365))
        now_teh = datetime.utcnow() + TEHRAN
        e_teh = now_teh.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        s_teh = e_teh - timedelta(days=days)
        start_utc = s_teh - TEHRAN
        end_utc = e_teh - TEHRAN

    trades = db.query(models.Trade).filter(
        models.Trade.user_id == oid,
        models.Trade.status == "closed",
        models.Trade.closed_at >= start_utc,
        models.Trade.closed_at < end_utc,
    ).all()

    is_share = frac != 1.0 or (await pool.managed_share(db, target) is not None)
    buckets: dict = {}
    for t in trades:
        if not t.closed_at:
            continue
        day = (t.closed_at + TEHRAN).strftime("%Y-%m-%d")  # روز تهران
        b = buckets.setdefault(day, {"date": day, "pnl": 0.0, "trades": 0, "wins": 0, "losses": 0})
        pnl = (t.pnl or 0) * frac   # سهمِ کاربر از سود/زیان آن معامله
        b["pnl"] += pnl
        b["trades"] += 1
        if pnl > 0:
            b["wins"] += 1
        elif pnl < 0:
            b["losses"] += 1

    rows = sorted(buckets.values(), key=lambda x: x["date"], reverse=True)
    for r in rows:
        r["pnl"] = round(r["pnl"], 2)
        if is_share:
            # برای عضو استخر، تعداد معاملهٔ شخصی معنا ندارد — فقط سهمِ سود/زیان نمایش داده می‌شود
            r["trades"] = r["wins"] = r["losses"] = None
    return {
        "days": rows,
        "total_pnl": round(sum(r["pnl"] for r in rows), 2),
        "total_trades": sum((r["trades"] or 0) for r in rows),
        "share_based": is_share,
    }


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
    from ..trading import pool
    if await pool.managed_share(db, current_user):
        return {"positions": []}  # کاربر managed پوزیشن‌های خام استخر را نمی‌بیند
    open_trades = db.query(models.Trade).filter(
        models.Trade.user_id == current_user.id,
        models.Trade.status == "open",
    ).all()
    if not open_trades:
        return {"positions": []}

    from ..config import settings
    from ..exchanges.nobitex import NobitexExchange
    base_url = settings.NOBITEX_BASE_URL

    # قیمت لحظه‌ای بازار ریالی را مستقیم از orderbook می‌گیریم — دقیقاً همان مسیری که
    # باکس «قیمت لحظه‌ای ارزها» استفاده می‌کند و مطمئناً کار می‌کند. به رشته‌ی ذخیره‌شده
    # وابسته نیستیم؛ فقط ارز پایه (BTC/ETH/...) را برمی‌داریم.
    async def rial_price(base_code: str) -> float:
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                r = await c.get(f"{base_url}/v3/orderbook/{base_code.upper()}IRT")
                d = r.json()
                if d.get("status") == "ok":
                    last = float(d.get("lastTradePrice", 0) or 0)
                    if not last:
                        bids = d.get("bids") or []
                        asks = d.get("asks") or []
                        bid = float(bids[0][0]) if bids else 0
                        ask = float(asks[0][0]) if asks else 0
                        last = (bid + ask) / 2 if (bid and ask) else (bid or ask)
                    return last
        except Exception:
            return 0.0
        return 0.0

    tp = current_user.target_profit
    sl = current_user.stop_loss
    trail_pct = max(0.8, sl * 0.6)   # همان فرمولِ حد ضررِ متحرک در ربات
    out = []
    for t in open_trades:
        raw = t.pair or ""
        base = raw.split("/")[0] if "/" in raw else raw
        base_code = NobitexExchange._code(base)        # → btc / eth / ...
        rial = await rial_price(base_code)
        cur = rial / 10.0                              # ریال → تومان
        entry = (t.entry_price or 0) / 10.0            # قیمت ورود هم به ریال ذخیره شده بود
        pnl_pct = ((cur - entry) / entry * 100) if (entry and cur) else 0
        # ── قیمتِ واقعیِ ماشهٔ فروش ──
        # تا قبل از رسیدن به هدف: entry*(1+tp). بعد از عبور از هدف، حد ضررِ متحرک فعال است:
        # ماشه = قله × (1 − trail)؛ با بالا رفتنِ قیمت، ماشه هم بالا می‌آید (قفلِ سودِ بیشتر).
        peak = max((t.peak_price or 0) / 10.0, cur)    # قله هم به ریال ذخیره شده
        peak_pct = ((peak - entry) / entry * 100) if entry else 0
        trailing_active = peak_pct >= tp
        if trailing_active:
            sell_trigger = peak * (1 - trail_pct / 100)
        else:
            sell_trigger = entry * (1 + tp / 100)
        out.append({
            "id": t.id,
            "pair": f"{base_code.upper()}/تومان",
            "amount": t.amount,
            "entry_price": round(entry, 2),
            "current_price": round(cur, 2),
            "target_sell_price": round(sell_trigger, 2),
            "trailing": trailing_active,               # سود از هدف رد شده و در حال دنبال‌کردنِ قله است
            "peak_pct": round(peak_pct, 2),
            "stop_price": round(entry * (1 - sl / 100), 2),
            "pnl_pct": round(pnl_pct, 2),
            "target_profit": tp,
            "stop_loss": sl,
            "opened_at": t.opened_at,
        })
    return {"positions": out}


@router.get("/signals")
async def get_signals(db: Session = Depends(get_db), current_user: models.User = Depends(require_active_plan)):
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
            ohlcv = await exchange.get_ohlcv(pair, "1h", 720)
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


@router.get("/analysis")
async def full_analysis(db: Session = Depends(get_db), current_user: models.User = Depends(require_active_plan)):
    """تحلیل فاندامنتال + تکنیکال + نتیجه‌گیری نهایی (متنی)."""
    import pandas as pd
    from ..ml.trainer import get_trainer

    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()

    technical = {"text": "داده کافی نیست", "conclusion": "خنثی", "score": 0, "ml_signal": "—", "ml_conf": 0}
    fundamental = {"text": "در دسترس نیست", "conclusion": "خنثی", "score": 0}

    if exch_rec:
        ex = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
        # تکنیکال روی BTC
        try:
            ohlcv = await ex.get_ohlcv("BTC/RLS", "1h", 720)
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                t = _compute_technical(df)
                if t:
                    technical.update(t)
                trainer = get_trainer()
                if trainer.is_trained:
                    ml = trainer.predict(df)
                    technical["ml_signal"] = ml["signal"]
                    technical["ml_conf"] = round(ml.get("confidence", 0) * 100, 1)
        except Exception:
            pass
        # فاندامنتال
        try:
            from ..ai.fundamental import get_fundamental
            fund = await get_fundamental(db, ex)
            sc = fund.get("score", 0)
            fundamental = {
                "text": fund.get("summary") or f"روند دلار ۷روزه: {fund.get('usd_trend_7d')}% | بیت‌کوین ۷روزه: {fund.get('btc_trend_7d')}%",
                "conclusion": "صعودی" if sc > 0.1 else ("نزولی" if sc < -0.1 else "خنثی"),
                "score": sc,
            }
        except Exception:
            pass

    # ── نتیجه‌گیری نهایی ──
    tech_c = technical["conclusion"]
    fund_c = fundamental["conclusion"]
    ml_sig = technical.get("ml_signal", "—")

    def sign(c):
        return 1 if c == "صعودی" else (-1 if c == "نزولی" else 0)
    total = sign(tech_c) + sign(fund_c) + (1 if ml_sig == "BUY" else (-1 if ml_sig == "SELL" else 0))

    if total >= 2:
        rec, color = "خرید", "buy"
        ctext = "هم تحلیل تکنیکال و هم فاندامنتال صعودی هستند و مدل سیگنال خرید می‌دهد — شرایط مساعد خرید."
    elif total <= -2:
        rec, color = "فروش / خروج", "sell"
        ctext = "تکنیکال و فاندامنتال نزولی هستند — بهتر است از معامله خرید پرهیز شود."
    else:
        rec, color = "صبر", "wait"
        ctext = "سیگنال‌های تکنیکال و فاندامنتال هم‌جهت نیستند — بهتر است صبر کنید تا تأیید واضح‌تری شکل بگیرد."

    return {
        "fundamental": fundamental,
        "technical": technical,
        "combined": {"recommendation": rec, "color": color, "text": ctext},
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/fundamental")
async def get_fundamental_analysis(db: Session = Depends(get_db), current_user: models.User = Depends(require_active_plan)):
    """تحلیل فاندامنتال هوش مصنوعی (روند دلار، بیت‌کوین، احساسات بازار)."""
    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    if not exch_rec:
        return {"score": 0, "summary": "", "usd_trend_7d": 0, "btc_trend_7d": 0}
    from ..ai.fundamental import get_fundamental
    ex = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
    try:
        return await get_fundamental(db, ex)
    except Exception:
        return {"score": 0, "summary": "", "usd_trend_7d": 0, "btc_trend_7d": 0}


@router.get("/prices")
async def get_prices(current_user: models.User = Depends(get_current_user)):
    """قیمت لحظه‌ای ارزهای اصلی به تومان و دلار (از نوبیتکس، مستقیم)."""
    from ..config import settings
    coins = ["BTC", "ETH", "USDT", "XRP", "ADA", "DOGE", "LTC", "TRX", "BNB", "SOL"]
    out = []
    base = settings.NOBITEX_BASE_URL

    async def ob(sym):
        try:
            async with httpx.AsyncClient(timeout=10, trust_env=False) as c:
                r = await c.get(f"{base}/v3/orderbook/{sym}")
                d = r.json()
                if d.get("status") == "ok":
                    return float(d.get("lastTradePrice", 0) or 0)
        except Exception:
            return 0.0
        return 0.0

    usdt_irt = await ob("USDTIRT")  # ریال به ازای هر تتر
    for coin in coins:
        rial = await ob(f"{coin}IRT")
        if rial <= 0:
            continue
        toman = rial / 10.0
        usd = 1.0 if coin == "USDT" else (rial / usdt_irt if usdt_irt else 0)
        out.append({"coin": coin, "toman": round(toman), "usd": round(usd, 2)})
    return {"prices": out}


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


def _fee_tier(volume_toman: float):
    """پله‌ی کارمزد نوبیتکس (تیکر بازار تومانی) بر اساس حجم ۳۰ روزه."""
    M = 1_000_000
    B = 1000 * M
    if volume_toman < 100 * M:
        return ("پایه", 0.25)
    if volume_toman < 300 * M:
        return ("VIP1", 0.2)
    if volume_toman < 1 * B:
        return ("VIP2", 0.19)
    if volume_toman < 5 * B:
        return ("VIP3", 0.175)
    if volume_toman < 20 * B:
        return ("VIP4", 0.155)
    if volume_toman < 80 * B:
        return ("VIP5", 0.145)
    return ("VIP6", 0.135)


@router.get("/commission")
async def get_commission(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """سیستم هوشمند کمیسیون: حجم ۳۰روزه، پله و کارمزد را خودکار از نوبیتکس تشخیص می‌دهد
    و کمیسیون پرداختی را روزانه/هفتگی/ماهانه نشان می‌دهد."""
    from datetime import timezone
    empty = {"volume_30d": 0, "tier": "پایه", "fee_pct": current_user.fee_pct or 0.25,
             "fee_today": 0, "fee_week": 0, "fee_month": 0, "orders_count": 0, "connected": False}
    exch_rec = db.query(models.ExchangeAPI).filter(
        models.ExchangeAPI.user_id == current_user.id,
        models.ExchangeAPI.is_active == True,
    ).first()
    if not exch_rec:
        return empty
    ex = get_exchange(exch_rec.exchange_name, exch_rec.api_key, exch_rec.api_secret)
    try:
        orders = await ex.get_recent_orders(only_buy=False)
    except Exception:
        orders = []

    # قیمت تتر به تومان برای تبدیل حجم/کارمزدِ بازارهای تتری
    usdt_toman = 0.0
    try:
        t = await ex.get_ticker("USDT/RLS")
        usdt_toman = (t.get("last", 0) or 0) / 10.0
    except Exception:
        usdt_toman = 0.0

    now = datetime.utcnow()

    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    def _is_rial(o) -> bool:
        market = (o.get("market") or "").upper()
        dst = (o.get("dstCurrency") or "")
        return (dst in ("﷼", "rls", "irt", "irr", "RLS", "IRT", "IRR")
                or market.endswith(("-RLS", "-IRT", "-IRR")))

    def parse_ts(o):
        s = o.get("created_at") or o.get("createdAt") or ""
        try:
            dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except Exception:
            return None

    def val_toman(o):
        """ارزش معاملهٔ انجام‌شده به تومان (از totalPrice که مقدار واقعی تطبیق‌یافته است)."""
        total = _f(o.get("totalPrice"))
        if total <= 0:
            total = _f(o.get("matchedAmount") or o.get("amount")) * _f(o.get("averagePrice"))
        if total <= 0:
            return 0.0
        if _is_rial(o):
            return total / 10.0  # ریال → تومان
        # بازار تتری: totalPrice به تتر است → تبدیل به تومان
        return total * usdt_toman if usdt_toman else 0.0

    def fee_toman(o):
        """کارمزد واقعی پرداخت‌شده به تومان (نوبیتکس مقدار دقیق را در فیلد fee می‌دهد).

        کارمزد در ارز دریافتی گرفته می‌شود: در فروش = ریال؛ در خرید = ارز خریداری‌شده.
        """
        fee = _f(o.get("fee"))
        if fee <= 0:
            return 0.0
        typ = (o.get("type") or "").lower()
        if _is_rial(o):
            if typ == "sell":
                return fee / 10.0  # کارمزد به ریال
            # خرید: کارمزد به ارز خریداری‌شده → با قیمت میانگین به تومان
            return fee * _f(o.get("averagePrice")) / 10.0
        # بازار تتری: کارمزد معمولاً به تتر یا ارز خریداری‌شده؛ تخمین با درصد
        v = val_toman(o)
        return v * (current_user.fee_pct or 0.25) / 100.0

    rows = []  # (ts, value_toman, fee_toman)
    vol30 = 0.0
    for o in orders:
        ts = parse_ts(o)
        v = val_toman(o)
        if ts is None or v <= 0:
            continue
        rows.append((ts, v, fee_toman(o)))
        if (now - ts).total_seconds() <= 30 * 86400:
            vol30 += v

    tier, fee = _fee_tier(vol30)
    # کارمزد تشخیص‌داده‌شده را خودکار روی حساب کاربر تنظیم کن (برای ربات)
    current_user.fee_pct = fee
    db.commit()

    def fees_since(seconds):
        cutoff = now - timedelta(seconds=seconds)
        return sum(ft for ts, v, ft in rows if ts >= cutoff)

    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fee_today = sum(ft for ts, v, ft in rows if ts >= start_today)

    return {
        "volume_30d": round(vol30),
        "tier": tier,
        "fee_pct": fee,
        "fee_today": round(fee_today),
        "fee_week": round(fees_since(7 * 86400)),
        "fee_month": round(fees_since(30 * 86400)),
        "orders_count": len(rows),
        "connected": True,
    }
