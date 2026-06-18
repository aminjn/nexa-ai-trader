import httpx
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from .base import BaseExchange, Balance, OrderResult
from ..config import settings


class NobitexExchange(BaseExchange):
    def __init__(self, api_key: str, api_secret: str = ""):
        super().__init__(api_key, api_secret)
        self.base_url = settings.NOBITEX_BASE_URL
        self.headers = {
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        }

    async def _get(self, path: str, params: dict = None) -> dict:
        # trust_env=False تا هیچ‌گاه از پروکسی استفاده نشود (نوبیتکس فقط مستقیم از ایران)
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.get(f"{self.base_url}{path}", headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    async def _post(self, path: str, data: dict = None) -> dict:
        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            resp = await client.post(f"{self.base_url}{path}", headers=self.headers, json=data or {})
            resp.raise_for_status()
            return resp.json()

    async def test_connection(self) -> bool:
        # خطاها را پنهان نمی‌کنیم تا علت واقعی در لاگ/پاسخ دیده شود
        result = await self._get("/users/profile")
        return result.get("status") == "ok"

    async def get_balance(self) -> Dict[str, Balance]:
        try:
            result = await self._post("/users/wallets/list")
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

    async def get_holdings(self) -> List[Dict]:
        """لیست دارایی‌های غیرصفر با ارزش تومانی."""
        result = await self._post("/users/wallets/list")
        out = []
        for w in result.get("wallets", []):
            bal = self._safe_float(w.get("balance"))
            if bal > 0:
                out.append({
                    "currency": (w.get("currency", "") or "").upper(),
                    "amount": bal,
                    "value_toman": self._safe_float(w.get("rialBalance")) / 10.0,
                })
        return sorted(out, key=lambda x: x["value_toman"], reverse=True)

    async def get_recent_orders(self, only_buy: bool = True) -> List[Dict]:
        """تاریخچه سفارش‌های انجام‌شده."""
        try:
            params = {"status": "done", "details": 2}
            if only_buy:
                params["type"] = "buy"
            result = await self._get("/market/orders/list", params=params)
            return result.get("orders", [])
        except Exception:
            return []

    async def get_portfolio_value_toman(self) -> float:
        """مجموع ارزش کل کیف‌پول‌ها را به تومان برمی‌گرداند."""
        result = await self._post("/users/wallets/list")
        total_rial = 0.0
        for wallet in result.get("wallets", []):
            total_rial += float(wallet.get("rialBalance", 0) or 0)
        return total_rial / 10.0  # ریال به تومان

    async def get_ticker(self, symbol: str) -> Dict:
        try:
            src, dst = symbol.replace("/", "-").split("-")
            src, dst = self._code(src), self._code(dst)
            msym = self._market_symbol(src, dst)  # مثلاً BTCIRT یا BTCUSDT
            # از orderbook v3 استفاده می‌کنیم که پایدار است
            result = await self._get(f"/v3/orderbook/{msym}")
            if result.get("status") != "ok":
                return {}
            bids = result.get("bids") or []
            asks = result.get("asks") or []
            return {
                "symbol": symbol,
                "last": self._safe_float(result.get("lastTradePrice")),
                "bid": self._safe_float(bids[0][0]) if bids else 0,
                "ask": self._safe_float(asks[0][0]) if asks else 0,
            }
        except Exception:
            return {}

    # نگاشت نام کامل ارز (که نوبیتکس در تاریخچه می‌دهد) به کد کوتاه بازار
    _CODE = {
        "bitcoin": "btc", "ethereum": "eth", "tether": "usdt", "ripple": "xrp",
        "cardano": "ada", "dogecoin": "doge", "litecoin": "ltc", "tron": "trx",
        "stellar": "xlm", "bitcoincash": "bch", "binancecoin": "bnb", "bnb": "bnb",
        "solana": "sol", "polkadot": "dot", "irr": "rls", "irt": "rls",
        "rial": "rls", "toman": "rls",
    }

    @staticmethod
    def _code(c: str) -> str:
        c = (c or "").strip().lower()
        return NobitexExchange._CODE.get(c, c)

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _market_symbol(src: str, dst: str) -> str:
        # نوبیتکس برای بازار ریالی از IRT استفاده می‌کند (نه RLS)
        dst_u = dst.upper()
        if dst_u in ("RLS", "IRR"):
            dst_u = "IRT"
        return f"{src.upper()}{dst_u}"

    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> List:
        try:
            src, dst = symbol.replace("/", "-").split("-")
            src, dst = self._code(src), self._code(dst)
            resolution_map = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D"}
            resolution = resolution_map.get(timeframe, "60")
            to_time = int(datetime.utcnow().timestamp())
            seconds_map = {"1": 60, "5": 300, "15": 900, "60": 3600, "240": 14400, "D": 86400}
            secs = seconds_map.get(resolution, 3600)
            from_time = to_time - secs * limit

            result = await self._get("/market/udf/history", params={
                "symbol": self._market_symbol(src, dst),
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
        src, dst = self._code(src), self._code(dst)
        data = {
            "type": "buy" if side == "buy" else "sell",
            "execution": "market",
            "srcCurrency": src.lower(),
            "dstCurrency": dst.lower(),
            "amount": str(amount),
        }
        result = await self._post("/market/orders/add", data)
        if result.get("status") != "ok":
            raise Exception(result.get("message") or str(result))
        order = result.get("order", {})
        return OrderResult(
            order_id=str(order.get("id", "")),
            symbol=symbol,
            side=side,
            price=self._safe_float(order.get("price")),
            amount=self._safe_float(order.get("amount")),
            status=order.get("status", "submitted"),
            timestamp=str(order.get("created_at", datetime.utcnow().isoformat())),
        )

    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> OrderResult:
        src, dst = symbol.replace("/", "-").split("-")
        src, dst = self._code(src), self._code(dst)
        data = {
            "type": "buy" if side == "buy" else "sell",
            "srcCurrency": src.lower(),
            "dstCurrency": dst.lower(),
            "amount": str(amount),
            "price": str(price),
        }
        result = await self._post("/market/orders/add", data)
        if result.get("status") != "ok":
            raise Exception(result.get("message") or str(result))
        order = result.get("order", {})
        return OrderResult(
            order_id=str(order.get("id", "")),
            symbol=symbol,
            side=side,
            price=self._safe_float(order.get("price")),
            amount=self._safe_float(order.get("amount")),
            status=order.get("status", "submitted"),
            timestamp=str(order.get("created_at", datetime.utcnow().isoformat())),
        )

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        try:
            result = await self._post("/market/orders/cancel", {"id": order_id})
            return result.get("status") == "ok"
        except Exception:
            return False

    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        try:
            params = {"status": "active"}
            result = await self._get("/market/orders/list", params=params)
            return result.get("orders", [])
        except Exception:
            return []

    async def get_order(self, order_id: str, symbol: str) -> Dict:
        try:
            result = await self._post("/market/orders/status", {"id": order_id})
            return result.get("order", {})
        except Exception:
            return {}


def get_exchange(exchange_name: str, api_key: str, api_secret: str = "") -> BaseExchange:
    if exchange_name.lower() == "nobitex":
        return NobitexExchange(api_key, api_secret)
    raise ValueError(f"صرافی {exchange_name} پشتیبانی نمی‌شود")
