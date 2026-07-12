"""بک‌تستِ صادقانه با کارمزد روی دادهٔ out-of-sample.

شبیه‌سازی: روی سیگنال‌های پراطمینانِ مدل وارد می‌شود، در هدف/حد ضرر/تایم‌اوت خارج می‌شود،
کارمزد رفت‌وبرگشت کسر می‌شود، و سود/زیانِ خالص گزارش می‌شود.
"""
import numpy as np
import pandas as pd
from .trainer import get_trainer, add_features, get_feature_columns, accum_load, TB_TP, TB_SL, TB_H


def _simulate(hi, lo, cl, proba, thr, tp, sl, horizon, fee, adx=None, adx_min=0, invert=False):
    """شبیه‌سازی روی یک سری: فهرستِ سود/زیانِ خالصِ هر معامله را برمی‌گرداند.

    invert=False : ورود وقتی proba ≥ thr (سیگنالِ صعودیِ مدل).
    invert=True  : ورود وقتی proba ≤ 1-thr (مدل کمترین اطمینان به صعود دارد — شرطِ معکوس).
    اگر adx_min>0 باشد، فقط وقتی قدرتِ روند (ADX) بالاتر از حد است وارد می‌شود.
    """
    n = len(cl)
    rets = []
    i = 0
    while i < n - 1:
        sig = (proba[i] <= 1 - thr) if invert else (proba[i] >= thr)
        if (not sig) or (adx_min > 0 and adx is not None and adx[i] < adx_min):
            i += 1
            continue
        entry = cl[i]
        tp_price = entry * (1 + tp)
        sl_price = entry * (1 - sl)
        exit_ret = None
        exit_idx = min(i + horizon, n - 1)
        for k in range(1, horizon + 1):
            j = i + k
            if j >= n:
                exit_idx = n - 1
                exit_ret = cl[exit_idx] / entry - 1
                break
            if lo[j] <= sl_price:
                exit_ret = -sl; exit_idx = j; break
            if hi[j] >= tp_price:
                exit_ret = tp; exit_idx = j; break
        if exit_ret is None:
            exit_idx = min(i + horizon, n - 1)
            exit_ret = cl[exit_idx] / entry - 1
        net = (1 + exit_ret) * (1 - fee) / (1 + fee) - 1
        rets.append(net)
        i = exit_idx + 1
    return rets


def _directional_conf(model, X_scaled):
    """اطمینانِ مؤثرِ خرید برای هر ردیف — سازگار با مدلِ سه‌کلاسهٔ جدید و دوکلاسهٔ قدیمی.

    سه‌کلاسه: conf = p_up/(p_up+p_down) با وتوی خنثی (p_flat≥0.6 ⇒ صفر = سیگنال نده).
    دوکلاسه: همان proba کلاسِ مثبت.
    """
    proba = model.predict_proba(X_scaled)
    cls = list(model.classes_)
    if 2.0 in cls:
        p_up = proba[:, cls.index(2.0)]
        p_dn = proba[:, cls.index(0.0)] if 0.0 in cls else np.zeros(len(proba))
        p_fl = proba[:, cls.index(1.0)] if 1.0 in cls else np.zeros(len(proba))
        conf = p_up / (p_up + p_dn + 1e-9)
        conf[p_fl >= 0.60] = 0.0
        return conf
    return proba[:, 1]


def _prep_symbol_arrays(test_only=True):
    """برای هر نماد: high/low/close، ADX و احتمالِ مدل را یک‌بار محاسبه و کش می‌کند."""
    trainer = get_trainer()
    raw = accum_load()
    feature_cols = get_feature_columns()
    out = []
    if raw is None or raw.empty:
        return out, trainer
    symbols = raw["symbol"].unique().tolist() if "symbol" in raw.columns else ["?"]
    btc_ref = None
    try:
        btc_syms = [s for s in symbols if str(s).upper().startswith("BTC")]
        if btc_syms:
            btc_ref = raw[raw["symbol"] == btc_syms[0]].sort_values("timestamp")
    except Exception:
        btc_ref = None
    for sym in symbols:
        g = raw[raw["symbol"] == sym] if "symbol" in raw.columns else raw
        g = g.sort_values("timestamp") if "timestamp" in g.columns else g
        f = add_features(g, btc_df=btc_ref).dropna(subset=feature_cols)
        if len(f) < 100:
            continue
        if test_only:
            f = f.tail(int(len(f) * 0.2))
        if len(f) < 50:
            continue
        try:
            proba = _directional_conf(trainer.model, trainer.scaler.transform(f[feature_cols].values))
        except Exception:
            continue
        adx = f["adx"].values if "adx" in f.columns else np.zeros(len(f))
        out.append((sym, f["high"].values, f["low"].values, f["close"].values, proba, adx))
    return out, trainer


def _agg(rets):
    arr = np.array(rets) if rets else np.array([])
    if len(arr) == 0:
        return None
    wins = arr[arr > 0]; losses = arr[arr < 0]
    gl = float(-losses.sum())
    equity = np.cumprod(1 + arr)
    peak = np.maximum.accumulate(equity)
    return {
        "trades": int(len(arr)),
        "win_rate": round(float((arr > 0).mean()) * 100, 1),
        "avg_net_pct": round(float(arr.mean()) * 100, 3),
        "total_compound_pct": round((float(equity[-1]) - 1) * 100, 1),
        "profit_factor": round(float(wins.sum()) / gl, 2) if gl > 0 else None,
        "max_drawdown_pct": round(float(((equity - peak) / peak).min()) * 100, 1),
    }


def run_backtest_sweep_sync(fee_pct: float = 0.25, test_only: bool = True) -> dict:
    """چند ترکیبِ آستانه × هدف/حدضرر را بک‌تست می‌کند تا سوددهی هر کدام مشخص شود.

    proba هر نماد یک‌بار محاسبه می‌شود؛ سپس ترکیب‌ها سریع روی همان داده ارزیابی می‌شوند.
    """
    fee = fee_pct / 100.0
    data, _ = _prep_symbol_arrays(test_only=test_only)
    if not data:
        return {"error": "داده/مدل برای بک‌تست آماده نیست."}

    # آستانه‌ها × (هدف٪، حدضرر٪، افق ساعت) × حالت (عادی / معکوس)
    # شاملِ هدف‌های کوچکِ اسکالپ (~۱–۱.۵٪) که بات واقعاً استفاده می‌کرد + هدف‌های بزرگ‌تر
    thresholds = [0.55, 0.62, 0.70, 0.78]
    barriers = [
        (1.0, 0.8, 12), (1.3, 1.0, 24), (1.5, 1.2, 24), (1.5, 1.5, 36),   # اسکالپِ هدف‌کوچک
        (2, 1.5, 48), (3, 2, 72), (5, 3, 120), (8, 5, 168),                # هدف‌های بزرگ‌تر
    ]
    modes = [("عادی", False), ("معکوس", True)]
    combos = []
    for thr in thresholds:
        for tp, sl, hz in barriers:
            for mode_name, inv in modes:
                rets = []
                for (_sym, hi, lo, cl, proba, adx) in data:
                    rets.extend(_simulate(hi, lo, cl, proba, thr, tp / 100.0, sl / 100.0,
                                          hz, fee, invert=inv))
                a = _agg(rets)
                if a and a["trades"] >= 10:
                    combos.append({"threshold": round(thr * 100), "tp_pct": tp, "sl_pct": sl,
                                   "horizon_h": hz, "mode": mode_name, "invert": inv, **a})
    # مرتب بر اساس ضریب سود (سوددهی)
    combos.sort(key=lambda x: (x["profit_factor"] or 0, x["avg_net_pct"]), reverse=True)
    profitable = [c for c in combos if (c["profit_factor"] or 0) >= 1.0 and c["avg_net_pct"] > 0]
    return {"fee_pct": fee_pct, "combos": combos, "best": combos[0] if combos else None,
            "any_profitable": len(profitable) > 0}


def run_auto_optimize_sync(fee_pct: float = 0.25) -> dict:
    """خودبهینه‌ساز: همهٔ ترکیب‌ها (عادی/معکوس × آستانه × هدف/حدضرر) را بک‌تست می‌کند،
    سوددهترین ترکیبِ معتبر را برمی‌گزیند و به‌طور خودکار روی استراتژیِ زندهٔ بات اعمال می‌کند.

    معیارِ پذیرش (برای کاهشِ بیش‌برازش): PF ≥ ۱.۱ و میانگینِ خالص > ۰ و دستِ‌کم ۳۰ معامله.
    اگر هیچ ترکیبی واجد نباشد، استراتژی غیرفعال می‌شود و بات معاملهٔ واقعی نمی‌کند.
    """
    from ..trading.strategy import set_strategy
    from ..trading.guard import set_expectancy
    res = run_backtest_sweep_sync(fee_pct=fee_pct)
    if res.get("error"):
        return {"applied": False, "error": res["error"]}
    combos = res.get("combos", [])
    good = [c for c in combos
            if (c.get("profit_factor") or 0) >= 1.1
            and c.get("avg_net_pct", 0) > 0
            and c.get("trades", 0) >= 30]
    if good:
        b = good[0]
        strat = set_strategy({
            "active": True, "mode": b["mode"], "invert": bool(b["invert"]),
            "threshold": b["threshold"] / 100.0, "tp_pct": b["tp_pct"], "sl_pct": b["sl_pct"],
            "horizon_h": b["horizon_h"], "expectancy_pct": b["avg_net_pct"],
            "profit_factor": b["profit_factor"], "trades": b["trades"],
        })
        set_expectancy(b["avg_net_pct"], b["trades"])     # مثبت ⇒ محافظ اجازه می‌دهد
        return {"applied": True, "strategy": strat, "best": b, "combos": combos}
    # هیچ ترکیبِ سودده‌ای نبود ⇒ بات معامله نکند
    set_strategy({"active": False})
    best = combos[0] if combos else None
    set_expectancy(best["avg_net_pct"] if best else -1.0, best["trades"] if best else 0)
    return {"applied": False, "best": best, "combos": combos}


def run_backtest_sync(threshold: float = None, fee_pct: float = 0.25,
                      tp: float = TB_TP, sl: float = TB_SL, horizon: int = TB_H,
                      test_only: bool = True) -> dict:
    """بک‌تست را روی دادهٔ انباشته اجرا می‌کند (پیش‌فرض: فقط بخشِ تستِ out-of-sample).

    خروجی: آمار معاملات شامل سود/زیان خالصِ پس از کمیسیون.
    """
    trainer = get_trainer()
    if not trainer.is_trained or trainer.model is None or trainer.scaler is None:
        return {"error": "مدل آموزش ندیده است."}
    raw = accum_load()
    if raw is None or raw.empty:
        return {"error": "داده‌ای برای بک‌تست نیست."}

    thr = float(threshold if threshold is not None else trainer.confidence_threshold)
    fee = fee_pct / 100.0
    feature_cols = get_feature_columns()

    all_returns = []        # سود/زیان خالصِ هر معامله (نسبتی)
    per_symbol = {}
    symbols = raw["symbol"].unique().tolist() if "symbol" in raw.columns else ["?"]

    btc_ref = None
    try:
        btc_syms = [s for s in symbols if str(s).upper().startswith("BTC")]
        if btc_syms:
            btc_ref = raw[raw["symbol"] == btc_syms[0]].sort_values("timestamp")
    except Exception:
        btc_ref = None
    for sym in symbols:
        g = raw[raw["symbol"] == sym] if "symbol" in raw.columns else raw
        g = g.sort_values("timestamp") if "timestamp" in g.columns else g
        f = add_features(g, btc_df=btc_ref)
        f = f.dropna(subset=feature_cols)
        if len(f) < 100:
            continue
        if test_only:
            f = f.tail(int(len(f) * 0.2))   # همان بخشِ تستِ out-of-sample
        if len(f) < 50:
            continue
        try:
            proba = _directional_conf(trainer.model,
                                      trainer.scaler.transform(f[feature_cols].values))
        except Exception:
            continue
        hi = f["high"].values
        lo = f["low"].values
        cl = f["close"].values
        n = len(cl)
        i = 0
        sym_rets = []
        while i < n - 1:
            if proba[i] < thr:
                i += 1
                continue
            entry = cl[i]
            tp_price = entry * (1 + tp)
            sl_price = entry * (1 - sl)
            exit_ret = None
            exit_idx = min(i + horizon, n - 1)
            for k in range(1, horizon + 1):
                j = i + k
                if j >= n:
                    exit_idx = n - 1
                    exit_ret = cl[exit_idx] / entry - 1
                    break
                # محتاطانه: اول حد ضرر، بعد هدف (اگر هر دو در یک کندل)
                if lo[j] <= sl_price:
                    exit_ret = -sl; exit_idx = j; break
                if hi[j] >= tp_price:
                    exit_ret = tp; exit_idx = j; break
            if exit_ret is None:
                exit_idx = min(i + horizon, n - 1)
                exit_ret = cl[exit_idx] / entry - 1
            # سود/زیانِ خالص پس از کارمزدِ خرید و فروش
            net = (1 + exit_ret) * (1 - fee) / (1 + fee) - 1
            sym_rets.append(net)
            all_returns.append(net)
            i = exit_idx + 1   # بدون پوزیشن هم‌پوشان
        if sym_rets:
            per_symbol[sym] = {
                "trades": len(sym_rets),
                "net_pct": round(float(np.sum(sym_rets)) * 100, 2),
                "win_rate": round(float(np.mean([r > 0 for r in sym_rets])) * 100, 1),
            }

    if not all_returns:
        return {"error": "هیچ سیگنالی بالاتر از آستانه پیدا نشد (آستانه را پایین‌تر بیاورید).",
                "threshold": round(thr * 100, 1)}

    arr = np.array(all_returns)
    wins = arr[arr > 0]
    losses = arr[arr < 0]
    gross_win = float(wins.sum())
    gross_loss = float(-losses.sum())
    equity = np.cumprod(1 + arr)        # رشد سرمایه با معاملاتِ پیاپیِ هم‌وزن
    peak = np.maximum.accumulate(equity)
    max_dd = float(((equity - peak) / peak).min() * 100) if len(equity) else 0.0

    # محافظِ سوددهی: انتظارِ سودِ هر معامله را ثبت کن تا بات قبل از ورود چک کند
    try:
        from ..trading.guard import set_expectancy
        set_expectancy(float(arr.mean()) * 100, int(len(arr)))
    except Exception:
        pass

    return {
        "threshold": round(thr * 100, 1),
        "fee_pct": fee_pct,
        "tp_pct": round(tp * 100, 2),
        "sl_pct": round(sl * 100, 2),
        "horizon_h": horizon,
        "trades": int(len(arr)),
        "win_rate": round(float((arr > 0).mean()) * 100, 1),
        "avg_net_pct": round(float(arr.mean()) * 100, 3),       # میانگین سود هر معامله (٪)
        "expectancy_pct": round(float(arr.mean()) * 100, 3),
        "total_compound_pct": round((float(equity[-1]) - 1) * 100, 1),  # بازده مرکبِ پیاپی
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss > 0 else None,
        "max_drawdown_pct": round(max_dd, 1),
        "test_only": test_only,
        "per_symbol": dict(sorted(per_symbol.items(), key=lambda x: x[1]["net_pct"], reverse=True)),
    }
