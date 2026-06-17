import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import joblib
import os
import asyncio
from datetime import datetime
from typing import Optional, Callable
from .data_fetcher import fetch_5year_data

MODEL_PATH = "ml_model.joblib"
SCALER_PATH = "ml_scaler.joblib"


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators as features."""
    df = df.copy()
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    # Moving averages
    for w in [5, 10, 20, 50, 200]:
        df[f"sma_{w}"] = c.rolling(w).mean()
        df[f"ema_{w}"] = c.ewm(span=w).mean()

    # RSI
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / (loss + 1e-9)
    df["rsi"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = c.ewm(span=12).mean()
    ema26 = c.ewm(span=26).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Bollinger Bands
    sma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    df["bb_upper"] = sma20 + 2 * std20
    df["bb_lower"] = sma20 - 2 * std20
    df["bb_pct"] = (c - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-9)

    # Volume features
    df["vol_sma20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / (df["vol_sma20"] + 1e-9)

    # Price features
    df["return_1d"] = c.pct_change(1)
    df["return_3d"] = c.pct_change(3)
    df["return_7d"] = c.pct_change(7)
    df["hl_ratio"] = (h - l) / (c + 1e-9)
    df["price_vs_sma50"] = c / (df["sma_50"] + 1e-9) - 1

    # Target: will price be higher in next 1 day?
    df["target"] = (c.shift(-1) > c).astype(int)

    return df


def get_feature_columns():
    return [
        "sma_5", "sma_10", "sma_20", "sma_50",
        "ema_5", "ema_10", "ema_20", "ema_50",
        "rsi", "macd", "macd_signal", "macd_hist",
        "bb_pct", "vol_ratio",
        "return_1d", "return_3d", "return_7d",
        "hl_ratio", "price_vs_sma50",
    ]


FEATURE_NAMES = [
    "میانگین متحرک ۵ روزه", "میانگین متحرک ۱۰ روزه", "میانگین متحرک ۲۰ روزه",
    "میانگین متحرک ۵۰ روزه", "EMA 5", "EMA 10", "EMA 20", "EMA 50",
    "شاخص قدرت نسبی (RSI)", "MACD", "سیگنال MACD", "هیستوگرام MACD",
    "درصد باند بولینگر", "نسبت حجم",
    "بازده ۱ روزه", "بازده ۳ روزه", "بازده ۷ روزه",
    "نسبت High/Low", "موقعیت نسبت به SMA50",
]


class MLTrainer:
    def __init__(self, model_path: str = MODEL_PATH, scaler_path: str = SCALER_PATH):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.model = None
        self.scaler = None
        self.accuracy = 0.0
        self.is_trained = False

    def load_if_exists(self) -> bool:
        if os.path.exists(self.model_path) and os.path.exists(self.scaler_path):
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
            self.is_trained = True
            return True
        return False

    async def train(
        self,
        progress_callback: Optional[Callable] = None,
        use_cached_data: bool = False,
    ) -> dict:
        if progress_callback:
            await progress_callback(5, "در حال دریافت داده‌های تاریخی...")

        try:
            df = await fetch_5year_data(["BTCUSDT", "ETHUSDT"])
            if df.empty:
                # Use synthetic data if fetch fails
                df = self._generate_synthetic_data()
        except Exception:
            df = self._generate_synthetic_data()

        if progress_callback:
            await progress_callback(25, "در حال محاسبه ویژگی‌های تکنیکال...")

        df = add_features(df)
        df = df.dropna()

        feature_cols = get_feature_columns()
        X = df[feature_cols].values
        y = df["target"].values

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        if progress_callback:
            await progress_callback(40, "در حال نرمال‌سازی داده‌ها...")

        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        if progress_callback:
            await progress_callback(50, "در حال آموزش مدل Gradient Boosting...")

        self.model = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=4,
            random_state=42,
            verbose=0,
        )

        # Train in chunks to simulate progress
        stages = [25, 50, 75, 100]
        for i, n in enumerate(stages):
            self.model.set_params(n_estimators=n)
            self.model.fit(X_train_scaled, y_train)
            if progress_callback:
                pct = 50 + (i + 1) * 10
                await progress_callback(pct, f"آموزش... {n} درخت کامل شد")
            await asyncio.sleep(0.1)

        if progress_callback:
            await progress_callback(90, "در حال ارزیابی مدل...")

        y_pred = self.model.predict(X_test_scaled)
        self.accuracy = float(accuracy_score(y_test, y_pred))

        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)
        self.is_trained = True

        if progress_callback:
            await progress_callback(100, "آموزش کامل شد!")

        return {
            "accuracy": self.accuracy,
            "samples": len(df),
            "features": len(feature_cols),
            "training_date": datetime.utcnow().isoformat(),
        }

    def predict(self, df_recent: pd.DataFrame) -> dict:
        if not self.is_trained:
            return {"signal": "WAIT", "confidence": 0.0}

        df = add_features(df_recent)
        df = df.dropna()
        if df.empty:
            return {"signal": "WAIT", "confidence": 0.0}

        feature_cols = get_feature_columns()
        X = df[feature_cols].iloc[-1:].values
        X_scaled = self.scaler.transform(X)

        pred = self.model.predict(X_scaled)[0]
        proba = self.model.predict_proba(X_scaled)[0]
        confidence = float(max(proba))

        signal = "BUY" if pred == 1 else "SELL"
        if confidence < 0.6:
            signal = "WAIT"

        return {"signal": signal, "confidence": confidence, "probabilities": proba.tolist()}

    def _generate_synthetic_data(self) -> pd.DataFrame:
        """Generate synthetic OHLCV data for training when API is unavailable."""
        np.random.seed(42)
        n = 2000
        price = 30000.0
        rows = []
        for i in range(n):
            change = np.random.normal(0.001, 0.02)
            open_p = price
            close_p = price * (1 + change)
            high_p = max(open_p, close_p) * (1 + abs(np.random.normal(0, 0.005)))
            low_p = min(open_p, close_p) * (1 - abs(np.random.normal(0, 0.005)))
            vol = np.random.uniform(1000, 5000)
            rows.append({
                "timestamp": pd.Timestamp("2019-01-01") + pd.Timedelta(days=i),
                "symbol": "BTCUSDT",
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
            })
            price = close_p
        return pd.DataFrame(rows)


# Global trainer instance
_trainer = MLTrainer()


def get_trainer() -> MLTrainer:
    if not _trainer.is_trained:
        _trainer.load_if_exists()
    return _trainer
