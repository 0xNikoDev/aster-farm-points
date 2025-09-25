import requests
import hmac
import hashlib
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal


@dataclass
class SymbolInfo:
    """Symbol trading information"""
    tick_size: float
    step_size: float
    min_qty: float
    min_notional: float


class AsterApiClient:
    """Client for interacting with Aster DEX API"""

    def __init__(self, api_key: str, secret_key: str, base_url: str, timeout: int = 30):
        self.api_key = api_key
        self.secret_key = secret_key
        self.base_url = base_url
        self.timeout = timeout
        self.headers = {"X-MBX-APIKEY": self.api_key}
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def _create_signature(self, params: Dict[str, Any]) -> str:
        """Create HMAC SHA256 signature for request"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None,
                     signed: bool = False) -> Dict[str, Any]:
        """Make HTTP request to API"""
        url = f"{self.base_url}{endpoint}"

        if params is None:
            params = {}

        if signed:
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._create_signature(params)

        try:
            if method == 'GET':
                response = self.session.get(url, params=params, timeout=self.timeout)
            elif method == 'POST':
                response = self.session.post(url, params=params, timeout=self.timeout)
            elif method == 'DELETE':
                response = self.session.delete(url, params=params, timeout=self.timeout)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API request failed: {str(e)}")

    def get_exchange_info(self) -> Dict[str, Any]:
        """Get exchange trading rules and symbol information"""
        return self._make_request('GET', '/fapi/v1/exchangeInfo')

    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        """Get trading parameters for a specific symbol"""
        exchange_info = self.get_exchange_info()

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

    def get_orderbook(self, symbol: str, limit: int = 5) -> Dict[str, Any]:
        """Get order book depth for a symbol"""
        params = {"symbol": symbol, "limit": limit}
        return self._make_request('GET', '/fapi/v1/depth', params)

    def check_hedge_mode(self) -> bool:
        """Check if hedge mode is enabled"""
        result = self._make_request('GET', '/fapi/v1/positionSide/dual', signed=True)
        return result.get('dualSidePosition', False)

    def set_hedge_mode(self, enabled: bool) -> Dict[str, Any]:
        """Enable or disable hedge mode"""
        params = {"dualSidePosition": str(enabled).lower()}
        return self._make_request('POST', '/fapi/v1/positionSide/dual', params, signed=True)

    def set_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
        """Set leverage for a symbol"""
        params = {"symbol": symbol, "leverage": leverage}
        return self._make_request('POST', '/fapi/v1/leverage', params, signed=True)

    def place_order(self, symbol: str, side: str, position_side: str,
                   order_type: str, quantity: float) -> Dict[str, Any]:
        """Place a new order"""
        params = {
            "symbol": symbol,
            "side": side,
            "positionSide": position_side,
            "type": order_type,
            "quantity": quantity
        }
        return self._make_request('POST', '/fapi/v1/order', params, signed=True)

    def get_position_risk(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Get current position information"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._make_request('GET', '/fapi/v2/positionRisk', params, signed=True)

    def get_account_balance(self) -> Dict[str, Any]:
        """Get account balance information"""
        return self._make_request('GET', '/fapi/v2/balance', signed=True)

    def close(self):
        """Close the session"""
        self.session.close()