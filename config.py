import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ApiConfig:
    """API configuration settings"""
    api_key: str
    api_secret: str
    api_key2: Optional[str] = None
    api_secret2: Optional[str] = None
    base_url: str = 'https://fapi.asterdex.com'
    timeout: int = 5
    retry_attempts: int = 3
    retry_delay: int = 1


@dataclass
class TradingConfig:
    """Trading configuration settings"""
    mode: str
    symbol: str
    leverage: int
    liquidity_multiplier: float
    balance_percentage: float
    hedge_mode: bool
    max_loss_usdt: float
    min_cycle_delay_sec: int
    max_cycle_delay_sec: int


@dataclass
class VolumeTradingConfig:
    """Volume trading mode configuration settings"""
    min_close_time_sec: int
    max_close_time_sec: int


@dataclass
class DualTradingConfig:
    """Dual account trading mode configuration settings"""
    max_position_deviation_percent: float
    min_hold_time_sec: int
    max_hold_time_sec: int


class Config:
    """Application configuration manager"""

    def __init__(self):
        self.api = self._load_api_config()
        self.trading = self._load_trading_config()
        self.volume = self._load_volume_config()
        self.dual = self._load_dual_config()
        self._validate_config()

    @staticmethod
    def _load_api_config() -> ApiConfig:
        """Load API configuration from environment variables"""
        return ApiConfig(
            api_key=os.getenv('API_KEY', ''),
            api_secret=os.getenv('API_SECRET', ''),
            api_key2=os.getenv('API_KEY2'),
            api_secret2=os.getenv('API_SECRET2'),
            base_url=os.getenv('BASE_URL', 'https://fapi.asterdex.com'),
            timeout=int(os.getenv('REQUEST_TIMEOUT', '5')),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
            retry_delay=int(os.getenv('RETRY_DELAY', '1'))
        )

    @staticmethod
    def _load_trading_config() -> TradingConfig:
        """Load trading configuration from environment variables"""
        return TradingConfig(
            mode=os.getenv('MODE', 'volume').lower(),
            symbol=os.getenv('SYMBOL', 'BTCUSDT'),
            leverage=int(os.getenv('LEVERAGE', '20')),
            liquidity_multiplier=float(os.getenv('LIQUIDITY_MULTIPLIER', '1.2')),
            balance_percentage=float(os.getenv('BALANCE_PERCENTAGE', '50')),
            hedge_mode=os.getenv('HEDGE_MODE', 'true').lower() == 'true',
            max_loss_usdt=float(os.getenv('MAX_LOSS_USDT', '100')),
            min_cycle_delay_sec=int(os.getenv('MIN_CYCLE_DELAY_SEC', '5')),
            max_cycle_delay_sec=int(os.getenv('MAX_CYCLE_DELAY_SEC', '15'))
        )

    @staticmethod
    def _load_volume_config() -> VolumeTradingConfig:
        """Load volume trading configuration from environment variables"""
        return VolumeTradingConfig(
            min_close_time_sec=int(os.getenv('MIN_CLOSE_TIME_SEC', '10')),
            max_close_time_sec=int(os.getenv('MAX_CLOSE_TIME_SEC', '30'))
        )

    @staticmethod
    def _load_dual_config() -> DualTradingConfig:
        """Load dual account configuration from environment variables"""
        return DualTradingConfig(
            max_position_deviation_percent=float(os.getenv('MAX_POSITION_DEVIATION_PERCENT', '20')),
            min_hold_time_sec=int(os.getenv('DUAL_MIN_HOLD_TIME_SEC', '30')),
            max_hold_time_sec=int(os.getenv('DUAL_MAX_HOLD_TIME_SEC', '300'))
        )

    def _validate_config(self):
        """Validate configuration parameters"""
        if not self.api.api_key or not self.api.api_secret:
            raise ValueError("API_KEY and API_SECRET must be set in .env file")

        if self.trading.mode == 'dual':
            if not self.api.api_key2 or not self.api.api_secret2:
                raise ValueError("API_KEY2 and API_SECRET2 must be set for dual mode")

        if self.trading.leverage < 1 or self.trading.leverage > 100:
            raise ValueError("Leverage must be between 1 and 100")

        if self.trading.liquidity_multiplier < 1.0:
            raise ValueError("Liquidity multiplier must be at least 1.0")

        if self.trading.balance_percentage < 1 or self.trading.balance_percentage > 100:
            raise ValueError("Balance percentage must be between 1 and 100")

        if self.trading.mode not in ['volume', 'dual']:
            raise ValueError("Invalid mode. Supported modes: 'volume', 'dual'")

        if self.trading.max_loss_usdt <= 0:
            raise ValueError("MAX_LOSS_USDT must be greater than 0")

        if self.trading.min_cycle_delay_sec < 0:
            raise ValueError("MIN_CYCLE_DELAY_SEC must be non-negative")

        if self.trading.max_cycle_delay_sec < self.trading.min_cycle_delay_sec:
            raise ValueError("MAX_CYCLE_DELAY_SEC must be greater than MIN_CYCLE_DELAY_SEC")

        if self.trading.mode == 'volume':
            if self.volume.min_close_time_sec < 1:
                raise ValueError("MIN_CLOSE_TIME_SEC must be at least 1 second")

            if self.volume.max_close_time_sec < self.volume.min_close_time_sec:
                raise ValueError("MAX_CLOSE_TIME_SEC must be greater than MIN_CLOSE_TIME_SEC")

        if self.trading.mode == 'dual':
            if self.dual.max_position_deviation_percent <= 0:
                raise ValueError("MAX_POSITION_DEVIATION_PERCENT must be greater than 0")

            if self.dual.min_hold_time_sec < 1:
                raise ValueError("DUAL_MIN_HOLD_TIME_SEC must be at least 1 second")

            if self.dual.max_hold_time_sec < self.dual.min_hold_time_sec:
                raise ValueError("DUAL_MAX_HOLD_TIME_SEC must be greater than DUAL_MIN_HOLD_TIME_SEC")