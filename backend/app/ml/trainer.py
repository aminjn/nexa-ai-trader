import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score
import joblib
import os
import asyncio
from datetime import datetime
from typing import Optional, Callable
from .data_fetcher import fetch_5year_data

MODEL_PATH = "ml_model.joblib"
SCALER_PATH = "ml_scaler.joblib"
THRESHOLD_PATH = "ml_threshold.txt"  # آستانه اطمینان تنظیم‌شده توسط هوش مصنوعی
ACCUM_PATH = "training_data.csv"  # مجموعه داده انباشته (بازار + آپلودی کاربر)

# پارامترهای تریپل‌بَریر (هدفِ آموزش): رسیدن به +TB_TP قبل از −TB_SL در TB_H کندلِ ساعتی
TB_TP = 0.02    # +۲٪ هدف سود
TB_SL = 0.015   # −۱.۵٪ حد ضرر
TB_H = 48       # افق ۴۸ ساعته (۲ روز)

_OHLCV_COLS = ["timestamp", "symbol", "open", "high", "low", "close", "volume"]

# نام‌های رایج معادل برای هر ستون (تا فایل با هر قالبی شناخته شود)
_COL_ALIASES = {
    "timestamp": ["timestamp", "time", "date", "datetime", "tarikh", "زمان", "تاریخ", "t"],
    "open": ["open", "o", "open_price", "baz", "قیمت_باز"],
    "high": ["high", "h", "max", "بیشترین", "بالا"],
    "low": ["low", "l", "min", "کمترین", "پایین"],
    "close": ["close", "c", "price", "last", "closing", "بسته", "قیمت"],
    "volume": ["volume", "vol", "v", "amount", "حجم"],
    "symbol": ["symbol", "pair", "ticker", "market", "نماد", "بازار"],
}


def _normalize_ohlcv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """نام ستون‌ها را به فرمت استاندارد تبدیل می‌کند (مستقل از بزرگی/کوچکی و نام)."""
    df = df.copy()
    lower_map = {str(col).strip().lower(): col for col in df.columns}
    rename = {}
    for std, aliases in _COL_ALIASES.items():
        for a in aliases:
            if a in lower_map:
                rename[lower_map[a]] = std
                break
    return df.rename(columns=rename)


def accum_load() -> pd.DataFrame:
    """بارگذاری مجموعه داده انباشته."""
    if os.path.exists(ACCUM_PATH):
        try:
            return pd.read_csv(ACCUM_PATH, parse_dates=["timestamp"])
        except Exception:
            return pd.DataFrame()
    return pd.DataFrame()


def accum_merge_save(new_df: pd.DataFrame) -> pd.DataFrame:
    """داده جدید را با داده انباشته ادغام، تکراری‌زدایی و ذخیره می‌کند."""
    if new_df is None or new_df.empty:
        return accum_load()
    new_df = _normalize_ohlcv_columns(new_df)
    if "symbol" not in new_df.columns:
        new_df["symbol"] = "CUSTOM"
    required = ["timestamp", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in new_df.columns]
    if missing:
        raise ValueError(
            "ستون‌های لازم پیدا نشد: " + "، ".join(missing) +
            " — فایل باید ستون‌های قیمت (open/high/low/close)، حجم (volume) و زمان (timestamp/date) داشته باشد."
        )
    new_df = new_df[_OHLCV_COLS]
    base = accum_load()
    merged = pd.concat([base, new_df], ignore_index=True) if not base.empty else new_df
    merged["timestamp"] = pd.to_datetime(merged["timestamp"])
    merged = (merged.drop_duplicates(subset=["symbol", "timestamp"])
              .sort_values(["symbol", "timestamp"]).reset_index(drop=True))
    merged.to_csv(ACCUM_PATH, index=False)
    return merged


def accum_count() -> int:
    df = accum_load()
    return 0 if df.empty else len(df)


# فهرست ویژگی‌ها: (نام ستون، نام فارسی) — همه مستقل از مقیاس قیمت
FEATURES = [
    ("sma_5", "نسبت قیمت به میانگین ۵ روزه"),
    ("sma_10", "نسبت قیمت به میانگین ۱۰ روزه"),
    ("sma_20", "نسبت قیمت به میانگین ۲۰ روزه"),
    ("sma_50", "نسبت قیمت به میانگین ۵۰ روزه"),
    ("sma_200", "نسبت قیمت به میانگین ۲۰۰ روزه"),
    ("ema_12", "نسبت قیمت به EMA 12"),
    ("ema_26", "نسبت قیمت به EMA 26"),
    ("rsi_7", "RSI کوتاه‌مدت (۷)"),
    ("rsi_14", "RSI استاندارد (۱۴)"),
    ("rsi_21", "RSI بلندمدت (۲۱)"),
    ("macd", "MACD"),
    ("macd_signal", "خط سیگنال MACD"),
    ("macd_hist", "هیستوگرام MACD"),
    ("stoch_k", "استوکستیک %K"),
    ("stoch_d", "استوکستیک %D"),
    ("williams_r", "ویلیامز %R"),
    ("cci", "شاخص کانال کالا (CCI)"),
    ("roc_10", "نرخ تغییر ۱۰ روزه (ROC)"),
    ("momentum_10", "مومنتوم ۱۰ روزه"),
    ("atr_pct", "میانگین دامنه واقعی (ATR٪)"),
    ("adx", "شاخص قدرت روند (ADX)"),
    ("mfi", "شاخص جریان نقدینگی (MFI)"),
    ("obv_ratio", "نسبت حجم متوازن (OBV)"),
    ("cmf", "جریان نقدینگی چایکین (CMF)"),
    ("bb_pct", "موقعیت در باند بولینگر"),
    ("bb_width", "پهنای باند بولینگر (نوسان)"),
    ("vol_ratio", "نسبت حجم به میانگین"),
    ("vol_change", "تغییر حجم"),
    ("return_1d", "بازده ۱ روزه"),
    ("return_3d", "بازده ۳ روزه"),
    ("return_7d", "بازده ۷ روزه"),
    ("return_14d", "بازده ۱۴ روزه"),
    ("return_30d", "بازده ۳۰ روزه"),
    ("hl_ratio", "نسبت دامنه روزانه"),
    ("close_pos", "موقعیت بسته‌شدن در کندل"),
    # مولتی‌تایم‌فریم (روند/مومنتومِ تایم‌فریم بالاتر — بدون نشت)
    ("htf_d_trend", "روند تایم‌فریم روزانه"),
    ("htf_d_rsi", "RSI تایم‌فریم روزانه"),
    ("htf_d_ret", "بازده روز قبل (روزانه)"),
    ("htf_d_dist20", "فاصله تا میانگین ۲۰ روزه"),
]


def get_feature_columns():
    return [f[0] for f in FEATURES]


FEATURE_NAMES = [f[1] for f in FEATURES]


def _rsi(c, period):
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """افزودن ۳۵+ اندیکاتور تکنیکال به‌صورت مستقل از مقیاس قیمت."""
    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    # میانگین‌های متحرک (نسبت قیمت به میانگین)
    for w in [5, 10, 20, 50, 200]:
        df[f"sma_{w}"] = c / (c.rolling(w).mean() + 1e-9) - 1
    df["ema_12"] = c / (c.ewm(span=12).mean() + 1e-9) - 1
    df["ema_26"] = c / (c.ewm(span=26).mean() + 1e-9) - 1

    # RSI چنددوره
    df["rsi_7"] = _rsi(c, 7)
    df["rsi_14"] = _rsi(c, 14)
    df["rsi_21"] = _rsi(c, 21)

    # MACD (نرمال نسبت به قیمت)
    ema12 = c.ewm(span=12).mean()
    ema26 = c.ewm(span=26).mean()
    df["macd"] = (ema12 - ema26) / (c + 1e-9)
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # استوکستیک
    low14 = l.rolling(14).min()
    high14 = h.rolling(14).max()
    df["stoch_k"] = (c - low14) / (high14 - low14 + 1e-9) * 100
    df["stoch_d"] = df["stoch_k"].rolling(3).mean()

    # ویلیامز %R
    df["williams_r"] = (high14 - c) / (high14 - low14 + 1e-9) * -100

    # CCI
    tp = (h + l + c) / 3
    sma_tp = tp.rolling(20).mean()
    mad = (tp - sma_tp).abs().rolling(20).mean()
    df["cci"] = (tp - sma_tp) / (0.015 * mad + 1e-9)

    # ROC و مومنتوم
    df["roc_10"] = c.pct_change(10) * 100
    df["momentum_10"] = c / (c.shift(10) + 1e-9) - 1

    # ATR (نرمال نسبت به قیمت)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    df["atr_pct"] = tr.rolling(14).mean() / (c + 1e-9)

    # ADX (قدرت روند)
    up_move = h.diff()
    down_move = -l.diff()
    plus_dm = ((up_move > down_move) & (up_move > 0)) * up_move
    minus_dm = ((down_move > up_move) & (down_move > 0)) * down_move
    atr14 = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / (atr14 + 1e-9))
    minus_di = 100 * (minus_dm.rolling(14).mean() / (atr14 + 1e-9))
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
    df["adx"] = dx.rolling(14).mean()

    # MFI (جریان نقدینگی)
    mf = tp * v
    pos_mf = (mf.where(tp > tp.shift(), 0)).rolling(14).sum()
    neg_mf = (mf.where(tp < tp.shift(), 0)).rolling(14).sum()
    df["mfi"] = 100 - (100 / (1 + pos_mf / (neg_mf + 1e-9)))

    # OBV (نسبی)
    obv = (np.sign(c.diff()) * v).fillna(0).cumsum()
    df["obv_ratio"] = obv / (obv.rolling(20).mean().abs() + 1e-9)

    # CMF (چایکین)
    mfm = ((c - l) - (h - c)) / (h - l + 1e-9)
    df["cmf"] = (mfm * v).rolling(20).sum() / (v.rolling(20).sum() + 1e-9)

    # باند بولینگر
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["bb_pct"] = (c - (sma20 - 2 * std20)) / (4 * std20 + 1e-9)
    df["bb_width"] = (4 * std20) / (sma20 + 1e-9)

    # حجم
    df["vol_ratio"] = v / (v.rolling(20).mean() + 1e-9)
    df["vol_change"] = v.pct_change(1)

    # بازده‌ها
    df["return_1d"] = c.pct_change(1)
    df["return_3d"] = c.pct_change(3)
    df["return_7d"] = c.pct_change(7)
    df["return_14d"] = c.pct_change(14)
    df["return_30d"] = c.pct_change(30)

    # ساختار کندل
    df["hl_ratio"] = (h - l) / (c + 1e-9)
    df["close_pos"] = (c - l) / (h - l + 1e-9)

    # ── مولتی‌تایم‌فریم: روند/مومنتومِ تایم‌فریم بالاتر (روزانه و هفتگی) ──
    # بدون نشت: مقادیر با یک دوره شیفت (تایم‌فریمِ کامل‌شدهٔ قبلی) به کندل‌های جاری نگاشت می‌شوند.
    df["htf_d_trend"] = 0.0
    df["htf_d_rsi"] = 50.0
    df["htf_d_ret"] = 0.0
    df["htf_d_dist20"] = 0.0
    if "timestamp" in df.columns:
        try:
            ts = pd.to_datetime(df["timestamp"])
            s = pd.Series(c.values, index=ts.values)
            d = s.resample("1D").last().dropna()       # کندل‌های روزانه
            if len(d) >= 6:
                d_trend = (d / (d.rolling(10).mean() + 1e-9) - 1).shift(1)   # روند ۱۰روزه
                d_rsi = _rsi(d, 14).shift(1)                                  # RSI روزانه
                d_ret = d.pct_change().shift(1)                              # بازده روز قبل
                d_dist20 = (d / (d.rolling(20).mean() + 1e-9) - 1).shift(1)   # فاصله تا SMA20 روزانه
                day_key = ts.dt.floor("D")
                df["htf_d_trend"] = day_key.map(d_trend).to_numpy()
                df["htf_d_rsi"] = day_key.map(d_rsi).to_numpy()
                df["htf_d_ret"] = day_key.map(d_ret).to_numpy()
                df["htf_d_dist20"] = day_key.map(d_dist20).to_numpy()
        except Exception:
            pass
    # پیش‌فرضِ خنثی اگر تاریخچهٔ کافی نبود (برای پیش‌بینی با دادهٔ کوتاه — جلوگیری از NaN)
    df["htf_d_trend"] = pd.to_numeric(df["htf_d_trend"], errors="coerce").fillna(0.0)
    df["htf_d_rsi"] = pd.to_numeric(df["htf_d_rsi"], errors="coerce").fillna(50.0)
    df["htf_d_ret"] = pd.to_numeric(df["htf_d_ret"], errors="coerce").fillna(0.0)
    df["htf_d_dist20"] = pd.to_numeric(df["htf_d_dist20"], errors="coerce").fillna(0.0)

    # ── هدف (تریپل‌بَریر): آیا قیمت قبل از افتِ TB_SL به سودِ TB_TP می‌رسد؟ ──
    # برچسب ۱ = ستاپِ سوددهِ تمیز (به هدف می‌رسد بدون خوردنِ حد ضرر در بازه)؛ ۰ = غیر آن.
    # این هدف با نحوهٔ معاملهٔ ربات (ورود → خروج در هدف/حد ضرر) هم‌راستاست.
    hi = h.values
    lo = l.values
    cl = c.values
    n = len(cl)
    up = cl * (1 + TB_TP)
    dn = cl * (1 - TB_SL)
    label = np.zeros(n, dtype=float)
    resolved = np.zeros(n, dtype=bool)
    idx = np.arange(n)
    for k in range(1, TB_H + 1):
        j = idx + k
        valid = j < n
        jj = np.clip(j, 0, n - 1)
        hh = hi[jj]
        ll = lo[jj]
        up_hit = valid & ~resolved & (hh >= up)
        dn_hit = valid & ~resolved & (ll <= dn)
        only_up = up_hit & ~dn_hit          # فقط هدف خورد → برد
        close_first = up_hit | dn_hit        # هر چه اول رخ داد (اگر هر دو در یک کندل → محتاطانه ضرر)
        label[only_up] = 1.0
        resolved[close_first] = True
    # ردیف‌های انتهایی که پنجرهٔ آیندهٔ کامل ندارند و حل‌نشده‌اند → NaN (حذف در آموزش)
    incomplete = (idx + TB_H) >= n
    label[incomplete & ~resolved] = np.nan
    df["target"] = label

    return df.replace([np.inf, -np.inf], np.nan)


class MLTrainer:
    def __init__(self, model_path: str = MODEL_PATH, scaler_path: str = SCALER_PATH):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.model = None
        self.scaler = None
        self.accuracy = 0.0
        self.is_trained = False
        self.feature_importances = []
        self.metrics = {}
        self.confidence_threshold = 0.53  # توسط هوش مصنوعی تنظیم می‌شود

    def set_threshold(self, t: float):
        """آستانه اطمینان را تنظیم و ذخیره می‌کند (پیشنهاد هوش مصنوعی)."""
        self.confidence_threshold = max(0.5, min(0.75, float(t)))
        try:
            with open(THRESHOLD_PATH, "w") as f:
                f.write(str(self.confidence_threshold))
        except Exception:
            pass

    def load_if_exists(self) -> bool:
        if os.path.exists(THRESHOLD_PATH):
            try:
                with open(THRESHOLD_PATH) as f:
                    self.confidence_threshold = float(f.read().strip())
            except Exception:
                pass
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            self.is_trained = True
            return True
        return False

    async def train(
        self,
        progress_callback: Optional[Callable] = None,
        progress_sync: Optional[Callable] = None,
        use_cached_data: bool = False,
    ) -> dict:
        if progress_callback:
            await progress_callback(5, "در حال دریافت داده ۵ ساله از نوبیتکس...")

        raw, source = await fetch_5year_data()

        if progress_callback:
            await progress_callback(12, "ادغام با داده‌های انباشته (آموزش تجمعی)...")

        # داده جدید را به مجموعه انباشته اضافه می‌کنیم و روی همه‌ی داده‌ها آموزش می‌دهیم
        merged = accum_merge_save(raw if not raw.empty else None)
        if merged.empty or len(merged) < 300:
            raise RuntimeError(
                "داده کافی برای آموزش وجود ندارد. دسترسی نوبیتکس را بررسی کنید یا داده آپلود کنید."
            )
        raw = merged
        if not source:
            source = "داده انباشته"

        symbols = sorted(raw["symbol"].unique().tolist()) if "symbol" in raw.columns else []
        date_from = str(raw["timestamp"].min())[:10] if "timestamp" in raw.columns else ""
        date_to = str(raw["timestamp"].max())[:10] if "timestamp" in raw.columns else ""

        if progress_callback:
            await progress_callback(20, f"محاسبه ۳۵+ اندیکاتور روی {len(symbols)} بازار...")

        # ── کلِ کارِ سنگینِ CPU (اندیکاتور + آموزش + ارزیابی) در یک thread جدا اجرا می‌شود
        #    تا event loop و کل سرور قفل نشود (جلوگیری از 504). ──
        feature_cols = get_feature_columns()
        result = await asyncio.to_thread(
            self._fit_model_sync, raw, feature_cols, symbols, date_from, date_to, source, progress_sync
        )

        if progress_callback:
            await progress_callback(100, "آموزش کامل شد!")
        return result

    def _fit_model_sync(self, raw, feature_cols, symbols, date_from, date_to, source, progress=None) -> dict:
        """بخش همگامِ سنگین: محاسبهٔ اندیکاتورها، آموزش و ارزیابی (در thread اجرا می‌شود)."""
        def _p(pct, msg):
            try:
                if progress:
                    progress(pct, msg)
            except Exception:
                pass
        # ویژگی‌ها را برای هر نماد جداگانه محاسبه می‌کنیم تا مرز نمادها قاطی نشود
        frames = []
        total = len(list(raw.groupby("symbol"))) if "symbol" in raw.columns else 1
        if "symbol" in raw.columns:
            for i, (sym, g) in enumerate(raw.groupby("symbol")):
                g = g.sort_values("timestamp")
                frames.append(add_features(g))
                _p(20 + int((i + 1) / max(1, total) * 30), f"محاسبه اندیکاتورها... {i+1}/{total} بازار")
            df = pd.concat(frames, ignore_index=True)
        else:
            df = add_features(raw)
        df = df.dropna()

        if len(df) < 200:
            raise RuntimeError("داده کافی پس از محاسبه اندیکاتورها باقی نماند.")

        # سقفِ امن برای حجم داده تا آموزش در زمان معقول تمام شود.
        # برای ارزیابیِ صادقانه (out-of-sample) داده را بر اساس زمان مرتب می‌کنیم
        # و جدیدترین بخش را به‌عنوان تست کنار می‌گذاریم (جلوگیری از نشت زمانی).
        MAX_ROWS = 150_000
        time_based = "timestamp" in df.columns
        if time_based:
            df = df.sort_values("timestamp")
            if len(df) > MAX_ROWS:
                df = df.tail(MAX_ROWS)   # جدیدترین داده‌ها (مرتبط‌تر با رژیم فعلی)
        else:
            if len(df) > MAX_ROWS:
                df = df.sample(MAX_ROWS, random_state=42)

        X = df[feature_cols].values
        y = df["target"].values
        if time_based:
            # تقسیم زمانی: ۸۰٪ قدیمی‌تر = آموزش، ۲۰٪ جدیدتر = تست
            n_test = max(1, int(len(df) * 0.2))
            X_train, X_test = X[:-n_test], X[-n_test:]
            y_train, y_test = y[:-n_test], y[-n_test:]
        else:
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        _p(55, "نرمال‌سازی داده‌ها...")
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # RandomForest چندهسته‌ای (n_jobs=-1) — روی چند CPU موازی و بسیار سریع‌تر از GradientBoosting
        _p(60, f"آموزش مدل روی {len(X_train):,} نمونه (موازی)...")
        self.model = RandomForestClassifier(
            n_estimators=200, max_depth=14, min_samples_leaf=3,
            n_jobs=-1, random_state=42, class_weight="balanced_subsample",
        )
        self.model.fit(X_train_scaled, y_train)
        _p(88, "ارزیابی مدل...")

        y_pred = self.model.predict(X_test_scaled)
        self.accuracy = float(accuracy_score(y_test, y_pred))
        precision = float(precision_score(y_test, y_pred, zero_division=0))
        recall = float(recall_score(y_test, y_pred, zero_division=0))

        importances = self.model.feature_importances_
        self.feature_importances = sorted(
            [{"name": FEATURE_NAMES[i], "key": feature_cols[i], "importance": round(float(importances[i]) * 100, 2)}
             for i in range(len(feature_cols))],
            key=lambda x: x["importance"], reverse=True,
        )

        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        self.is_trained = True

        self.metrics = {
            "accuracy": round(self.accuracy * 100, 2),
            "precision": round(precision * 100, 2),
            "recall": round(recall * 100, 2),
            "accumulated_rows": int(len(raw)),
            "total_samples": int(len(df)),
            "train_samples": int(len(X_train)),
            "test_samples": int(len(X_test)),
            "num_features": len(feature_cols),
            "symbols": symbols,
            "date_from": date_from,
            "date_to": date_to,
            "source": source,
            "split": "زمانی (out-of-sample)" if time_based else "تصادفی",
        }

        return {
            "accuracy": self.accuracy,
            "samples": len(df),
            "features": len(feature_cols),
            "feature_importances": self.feature_importances,
            "metrics": self.metrics,
            "source": source,
            "training_date": datetime.utcnow().isoformat(),
        }

    def predict(self, df_recent: pd.DataFrame) -> dict:
        if not self.is_trained:
            return {"signal": "WAIT", "confidence": 0.0}

        df = add_features(df_recent)
        feature_cols = get_feature_columns()
        # فقط روی فیچرها dropna می‌کنیم نه target — وگرنه کندلِ جاری (که target=NaN دارد) حذف می‌شد
        df = df.dropna(subset=feature_cols)
        if df.empty:
            return {"signal": "WAIT", "confidence": 0.0}
        try:
            X = df[feature_cols].iloc[-1:].values
            X_scaled = self.scaler.transform(X)
            pred = self.model.predict(X_scaled)[0]
            proba = self.model.predict_proba(X_scaled)[0]
        except Exception:
            # ناسازگاری مدلِ قدیمی با فیچرهای جدید → تا آموزش مجدد، صبر
            return {"signal": "WAIT", "confidence": 0.0}
        confidence = float(max(proba))

        signal = "BUY" if pred == 1 else "SELL"
        # آستانه اطمینان که توسط هوش مصنوعی تنظیم شده است
        if confidence < self.confidence_threshold:
            signal = "WAIT"

        return {"signal": signal, "confidence": confidence, "probabilities": proba.tolist()}


# Global trainer instance
_trainer = MLTrainer()


def get_trainer() -> MLTrainer:
    if not _trainer.is_trained:
        _trainer.load_if_exists()
    return _trainer
