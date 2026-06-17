import httpx
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from .base import BaseExchange, Balance, OrderResult

NOBITEX_BASE = "https://api.nobitex.ir"


class NobitexExchange(BaseExchange):
    def __init__(self, api_key: str, api_secret: str = ""):
        super().__init__(api_key, api_secret)
        self.base_url = NOBITEX_BASE
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"{self.base_url}{path}", headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, data: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}{path}", headers=self.headers, json=data or {})
            resp.raise_for_status()
            return resp.json()

    async def test_connection(self) -> bool:
        try:
            result = await self._get("/users/profile/")
            return result.get("status") == "ok"
        except Exception:
            return False

    async def get_balance(self) -> Dict[str, Balance]:
        try:
            result = await self._post("/users/wallets/list/")
            balances = {}
            for wallet in result.get("wallets", []):
                currency = wallet.get("currency", "").upper()
                balance_val = float(wallet.get("balance", 0))
                blocked = float(wallet.get("blockedBalance", 0))
                balances[currency] = Balance(
                    currency=currency,
                    free=balance_val - blocked,
                    used=blocked,
                    total=balance_val,
                )
            return balances
        except Exception as e:
            return {}

    async def get_ticker(self, symbol: str) -> Dict:
        try:
            # Nobitex uses srcCurrency/dstCurrency format
            src, dst = symbol.replace("/", "-").split("-")
            result = await self._get("/market/stats/", params={
                "srcCurrency": src.lower(),
                "dstCurrency": dst.lower(),
            })
            stats = result.get("stats", {})
            key = f"{src.lower()}-{dst.lower()}"
            data = stats.get(key, {})
            return {
                "symbol": symbol,
                "last": float(data.get("latest", 0)),
                "bid": float(data.get("bestBuy", 0)),
                "ask": float(data.get("bestSell", 0)),
                "high": float(data.get("dayHigh", 0)),
                "low": float(data.get("dayLow", 0)),
                "volume": float(data.get("dayVolume", 0)),
                "change_pct": float(data.get("dayChange", 0)),
            }
        except Exception as e:
            return {}

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> List:
        try:
            src, dst = symbol.replace("/", "-").split("-")
            resolution_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}
            resolution = resolution_map.get(timeframe, "60")
            to_time = int(datetime.utcnow().timestamp())
            seconds_map = {"1": 60, "5": 300, "15": 900, "60": 3600, "240": 14400, "D": 86400}
            secs = seconds_map.get(resolution, 3600)
            from_time = to_time - secs * limit

            result = await self._get("/market/udf/history", params={
                "symbol": f"{src.upper()}{dst.upper()}",
                "resolution": resolution,
                "from": from_time,
                "to": to_time,
            })
            if result.get("s") != "ok":
                return []
            t = result.get("t", [])
            o = result.get("o", [])
            h = result.get("h", [])
            l = result.get("l", [])
            c = result.get("c", [])
            v = result.get("v", [])
            return [[t[i]*1000, float(o[i]), float(h[i]), float(l[i]), float(c[i]), float(v[i])]
                    for i in range(len(t))]
        except Exception:
            return []

    async def create_market_order(self, symbol: str, side: str, amount: float) -> OrderResult:
        src, dst = symbol.replace("/", "-").split("-")
        data = {
            "type": "buy" if side == "buy" else "sell",
            "srcCurrency": src.lower(),
            "dstCurrency": dst.lower(),
            "amount": str(amount),
            "price": "market",
        }
        result = await self._post("/market/orders/add/", data)
        order = result.get("order", {})
        return OrderResult(
            order_id=str(order.get("id", "")),
            symbol=symbol,
            side=side,
            price=float(order.get("price", 0)),
            amount=float(order.get("amount", 0)),
            status=order.get("status", "submitted"),
            timestamp=str(order.get("created_at", datetime.utcnow().isoformat())),
        )

    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> OrderResult:
        src, dst = symbol.replace("/", "-").split("-")
        data = {
            "type": "buy" if side == "buy" else "sell",
            "srcCurrency": src.lower(),
            "dstCurrency": dst.lower(),
            "amount": str(amount),
            "price": str(price),
        }
        result = await self._post("/market/orders/add/", data)
        order = result.get("order", {})
        return OrderResult(
            order_id=str(order.get("id", "")),
            symbol=symbol,
            side=side,
            price=float(order.get("price", 0)),
            amount=float(order.get("amount", 0)),
            status=order.get("status", "submitted"),
            timestamp=str(order.get("created_at", datetime.utcnow().isoformat())),
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            result = await self._post("/market/orders/cancel/", {"id": order_id})
            return result.get("status") == "ok"
        except Exception:
            return False

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        try:
            params = {"status": "active"}
            result = await self._get("/market/orders/list/", params=params)
            return result.get("orders", [])
        except Exception:
            return []

    async def get_order(self, order_id: str, symbol: str) -> Dict:
        try:
            result = await self._post("/market/orders/status/", {"id": order_id})
            return result.get("order", {})
        except Exception:
            return {}


def get_exchange(exchange_name: str, api_key: str, api_secret: str = "") -> BaseExchange:
    if exchange_name.lower() == "nobitex":
        return NobitexExchange(api_key, api_secret)
    raise ValueError(f"صرافی {exchange_name} پشتیبانی نمی‌شود")
