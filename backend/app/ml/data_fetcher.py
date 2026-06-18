import httpx
import pandas as pd
import time
from datetime import datetime
from typing import List
from ..config import settings


async def fetch_binance_5y(pairs: List[str]) -> pd.DataFrame:
    """۵ سال داده روزانه از بایننس (از طریق پروکسی، چون بین‌المللی است)."""
    proxy = settings.GAPGPT_PROXY or None
    all_frames = []
    for symbol in pairs:
        frames = []
        end_time = int(datetime.utcnow().timestamp() * 1000)
        for _ in range(2):  # ~۲۰۰۰ کندل روزانه
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": "1d", "limit": 1000, "endTime": end_time}
            async with httpx.AsyncClient(timeout=30, proxy=proxy) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if not data:
                break
            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_volume", "trades", "taker_buy_base",
                "taker_buy_quote", "ignore"
            ])
            df["symbol"] = symbol
            frames.append(df)
            end_time = int(data[0][0]) - 1
        if frames:
            combined = pd.concat(frames).drop_duplicates("timestamp").sort_values("timestamp")
            all_frames.append(combined)

    if not all_frames:
        return pd.DataFrame()
    result = pd.concat(all_frames, ignore_index=True)
    for col in ["open", "high", "low", "close", "volume"]:
        result[col] = result[col].astype(float)
    result["timestamp"] = pd.to_datetime(result["timestamp"], unit="ms")
    return result[["timestamp", "symbol", "open", "high", "low", "close", "volume"]]


async def fetch_nobitex_5y(symbols: List[str]) -> pd.DataFrame:
    """داده روزانه از نوبیتکس (مستقیم، بدون پروکسی). symbols مثل BTCUSDT یا BTCIRT."""
    base = settings.NOBITEX_BASE_URL
    to_t = int(time.time())
    from_t = to_t - 1825 * 86400  # ۵ سال
    all_frames = []
    for symbol in symbols:
        url = f"{base}/market/udf/history"
        params = {"symbol": symbol, "resolution": "D", "from": from_t, "to": to_t}
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
                resp = await client.get(url, params=params)
                resp.raise_for_status()
                data = resp.json()
            if data.get("s") != "ok" or not data.get("t"):
                continue
            df = pd.DataFrame({
                "timestamp": pd.to_datetime(data["t"], unit="s"),
                "open": [float(x) for x in data["o"]],
                "high": [float(x) for x in data["h"]],
                "low": [float(x) for x in data["l"]],
                "close": [float(x) for x in data["c"]],
                "volume": [float(x) for x in data["v"]],
            })
            df["symbol"] = symbol
            all_frames.append(df)
        except Exception:
            continue
    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


# بازارهای ریالی نوبیتکس برای آموزش (همان بازارهایی که ربات معامله می‌کند)
NOBITEX_TRAIN_SYMBOLS = ["BTCIRT", "ETHIRT", "USDTIRT", "LTCIRT", "XRPIRT", "ADAIRT", "DOGEIRT", "BNBIRT"]


async def fetch_5year_data(pairs: List[str] = None):
    """داده ۵ ساله را برمی‌گرداند. اولویت با نوبیتکس (مستقیم) است.

    خروجی: (DataFrame, نام منبع)
    """
    # تلاش اول: نوبیتکس مستقیم (داده‌ی همان بازاری که معامله می‌شود)
    try:
        df = await fetch_nobitex_5y(NOBITEX_TRAIN_SYMBOLS)
        if not df.empty and len(df) > 300:
            return df, "نوبیتکس"
    except Exception:
        pass

    # تلاش دوم: بایننس از طریق پروکسی
    try:
        df = await fetch_binance_5y(["BTCUSDT", "ETHUSDT"])
        if not df.empty and len(df) > 300:
            return df, "بایننس"
    except Exception:
        pass

    return pd.DataFrame(), ""
