"""بک‌تستِ صادقانه با کارمزد روی دادهٔ out-of-sample.

شبیه‌سازی: روی سیگنال‌های پراطمینانِ مدل وارد می‌شود، در هدف/حد ضرر/تایم‌اوت خارج می‌شود،
کارمزد رفت‌وبرگشت کسر می‌شود، و سود/زیانِ خالص گزارش می‌شود.
"""
import numpy as np
import pandas as pd
from .trainer import get_trainer, add_features, get_feature_columns, accum_load, TB_TP, TB_SL, TB_H


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

    for sym in symbols:
        g = raw[raw["symbol"] == sym] if "symbol" in raw.columns else raw
        g = g.sort_values("timestamp") if "timestamp" in g.columns else g
        f = add_features(g)
        f = f.dropna(subset=feature_cols)
        if len(f) < 100:
            continue
        if test_only:
            f = f.tail(int(len(f) * 0.2))   # همان بخشِ تستِ out-of-sample
        if len(f) < 50:
            continue
        try:
            proba = trainer.model.predict_proba(
                trainer.scaler.transform(f[feature_cols].values))[:, 1]
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
