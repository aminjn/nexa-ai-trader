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


async def fetch_nobitex_history(symbols: List[str], resolution: str = "60",
                                days: int = 720) -> pd.DataFrame:
    """داده تاریخی از نوبیتکس (مستقیم). resolution: "60"=ساعتی، "D"=روزانه.

    نمادها هم‌زمان (موازی) و هر نماد در پنجره‌های زمانی صفحه‌بندی می‌شود
    (نوبیتکس داده از ~۲۰۲۵ دارد، پس بازهٔ پیش‌فرض کوتاه است تا سریع باشد).
    """
    import asyncio
    base = settings.NOBITEX_BASE_URL
    to_t = int(time.time())
    from_t = to_t - days * 86400
    window = 60 * 86400 if resolution not in ("D", "1D") else days * 86400

    async def fetch_symbol(symbol: str) -> pd.DataFrame:
        frames = []
        start = from_t
        async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
            while start < to_t:
                end = min(start + window, to_t)
                url = f"{base}/market/udf/history"
                params = {"symbol": symbol, "resolution": resolution, "from": start, "to": end}
                try:
                    resp = await client.get(url, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    if data.get("s") == "ok" and data.get("t"):
                        frames.append(pd.DataFrame({
                            "timestamp": pd.to_datetime(data["t"], unit="s"),
                            "open": [float(x) for x in data["o"]],
                            "high": [float(x) for x in data["h"]],
                            "low": [float(x) for x in data["l"]],
                            "close": [float(x) for x in data["c"]],
                            "volume": [float(x) for x in data["v"]],
                        }))
                except Exception:
                    pass
                start = end
        if not frames:
            return pd.DataFrame()
        g = pd.concat(frames).drop_duplicates("timestamp").sort_values("timestamp")
        g["symbol"] = symbol
        return g

    results = await asyncio.gather(*[fetch_symbol(s) for s in symbols], return_exceptions=True)
    all_frames = [r for r in results if isinstance(r, pd.DataFrame) and not r.empty]
    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


# بازارهای ریالی نوبیتکس برای آموزش (هم‌راستا با ارزهایی که ربات معامله می‌کند)
NOBITEX_TRAIN_SYMBOLS = [
    "BTCIRT", "ETHIRT", "USDTIRT", "LTCIRT", "XRPIRT", "ADAIRT", "DOGEIRT", "BNBIRT",
    "SOLIRT", "TRXIRT", "BCHIRT", "DOTIRT", "AVAXIRT", "MATICIRT", "LINKIRT",
    "UNIIRT", "ATOMIRT", "FILIRT", "ETCIRT", "XLMIRT", "SHIBIRT", "AAVEIRT",
]


async def fetch_5year_data(pairs: List[str] = None, resolution: str = "60"):
    """داده تاریخی را برمی‌گرداند. اولویت با نوبیتکسِ ساعتی (هم‌تایم‌فریمِ ربات).

    خروجی: (DataFrame, نام منبع)
    """
    # تلاش اول: نوبیتکس ساعتی (بیشترین داده + هماهنگ با تایم‌فریم ۱ساعتهٔ معامله)
    try:
        df = await fetch_nobitex_history(NOBITEX_TRAIN_SYMBOLS, resolution=resolution)
        if not df.empty and len(df) > 300:
            return df, "نوبیتکس"
    except Exception:
        pass

    # تلاش دوم: نوبیتکس روزانه (اگر ساعتی در دسترس نبود)
    try:
        df = await fetch_nobitex_history(NOBITEX_TRAIN_SYMBOLS, resolution="D")
        if not df.empty and len(df) > 300:
            return df, "نوبیتکس"
    except Exception:
        pass

    # تلاش سوم: بایننس از طریق پروکسی
    try:
        df = await fetch_binance_5y(["BTCUSDT", "ETHUSDT"])
        if not df.empty and len(df) > 300:
            return df, "بایننس"
    except Exception:
        pass

    return pd.DataFrame(), ""
