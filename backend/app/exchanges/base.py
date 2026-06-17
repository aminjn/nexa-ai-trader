from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class Balance:
    currency: str
    free: float
    used: float
    total: float


@dataclass
class OrderResult:
    order_id: str
    symbol: str
    side: str
    price: float
    amount: float
    status: str
    timestamp: str


class BaseExchange(ABC):
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret

    @abstractmethod
    async def get_balance(self) -> Dict[str, Balance]:
        pass

    @abstractmethod
    async def get_ticker(self, symbol: str) -> Dict:
        pass

    @abstractmethod
    async def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 200) -> List:
        pass

    @abstractmethod
    async def create_market_order(self, symbol: str, side: str, amount: float) -> OrderResult:
        pass

    @abstractmethod
    async def create_limit_order(self, symbol: str, side: str, amount: float, price: float) -> OrderResult:
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        pass

    @abstractmethod
    async def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        pass

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str) -> Dict:
        pass

    @abstractmethod
    async def test_connection(self) -> bool:
        pass
