import aiohttp
import hmac
import hashlib
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SymbolInfo:
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float


class AsterApiClient:

    def __init__(self, api_key: str, secret_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.timeout = timeout
        self.headers = {"X-MBX-APIKEY": self.api_key}
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def _create_signature(self, params: Dict[str, Any]) -> str:
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                           signed: bool = False) -> Dict[str, Any]:
        if self.session is None:
            self.session = aiohttp.ClientSession(headers=self.headers)

        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._create_signature(params)

        try:
            timeout = aiohttp.ClientTimeout(total=self.timeout)

            if method == 'GET':
                async with self.session.get(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method == 'POST':
                async with self.session.post(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            elif method == 'DELETE':
                async with self.session.delete(url, params=params, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            raise Exception(f"API request failed: {str(e)}")

    async def get_exchange_info(self) -> Dict[str, Any]:
        return await self._make_request('GET', '/fapi/v1/exchangeInfo')

    async def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        exchange_info = await self.get_exchange_info()

        for s in exchange_info.get('symbols', []):
            if s['symbol'] == symbol:
                filters = {}
                for f in s['filters']:
                    if f['filterType'] == 'PRICE_FILTER':
                        filters['tick_size'] = float(f['tickSize'])
                    elif f['filterType'] == 'LOT_SIZE':
                        filters['step_size'] = float(f['stepSize'])
                        filters['min_qty'] = float(f['minQty'])
                    elif f['filterType'] == 'MIN_NOTIONAL':
                        filters['min_notional'] = float(f['notional'])

                if all(k in filters for k in ['tick_size', 'step_size', 'min_qty', 'min_notional']):
                    return SymbolInfo(**filters)
        return None

    async def get_orderbook(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        params = {"symbol": symbol, "limit": limit}
        return await self._make_request('GET', '/fapi/v1/depth', params)

    async def check_hedge_mode(self) -> bool:
        result = await self._make_request('GET', '/fapi/v1/positionSide/dual', signed=True)
        return result.get('dualSidePosition', False)

    async def set_hedge_mode(self, enabled: bool) -> Dict[str, Any]:
        params = {"dualSidePosition": str(enabled).lower()}
        return await self._make_request('POST', '/fapi/v1/positionSide/dual', params, signed=True)

    async def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        params = {"symbol": symbol, "leverage": leverage}
        return await self._make_request('POST', '/fapi/v1/leverage', params, signed=True)

    async def place_order(self, symbol: str, side: str, position_side: str,
                         order_type: str, quantity: float) -> Dict[str, Any]:
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "quantity": quantity
        }
        return await self._make_request('POST', '/fapi/v1/order', params, signed=True)

    async def get_position_risk(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if symbol:
            params['symbol'] = symbol
        return await self._make_request('GET', '/fapi/v2/positionRisk', params, signed=True)

    async def get_account_balance(self) -> Dict[str, Any]:
        return await self._make_request('GET', '/fapi/v2/balance', signed=True)

    async def close(self):
        if self.session:
            await self.session.close()