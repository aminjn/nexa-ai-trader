import httpx
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional
import asyncio


async def fetch_binance_ohlcv(symbol: str = "BTCUSDT", interval: str = "1d", limit: int = 1000) -> pd.DataFrame:
    """Fetch historical data from Binance public API (no key needed)."""
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore"
    ])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


async def fetch_5year_data(pairs: List[str] = None) -> pd.DataFrame:
    """Fetch 5 years of daily data for training."""
    if pairs is None:
        pairs = ["BTCUSDT", "ETHUSDT"]

    all_frames = []
    for symbol in pairs:
        # Binance limit is 1000 per call, 5 years = ~1825 days, need 2 calls
        frames = []
        end_time = int(datetime.utcnow().timestamp() * 1000)
        for _ in range(2):
            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": symbol,
                "interval": "1d",
                "limit": 1000,
                "endTime": end_time,
            }
            try:
                async with httpx.AsyncClient(timeout=30) as client:
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
            except Exception:
                break
        if frames:
            combined = pd.concat(frames).drop_duplicates("timestamp").sort_values("timestamp")
            all_frames.append(combined)

    if not all_frames:
        return pd.DataFrame()

    result = pd.concat(all_frames, ignore_index=True)
    for col in ["open", "high", "low", "close", "volume"]:
        result[col] = result[col].astype(float)
    result["timestamp"] = pd.to_datetime(result["timestamp"], unit="ms")
    return result
