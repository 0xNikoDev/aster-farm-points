import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ApiConfig:
    """API configuration settings"""
    api_key: str
    secret_key: str
    base_url: str
    timeout: int
    retry_attempts: int
    retry_delay: int


@dataclass
class TradingConfig:
    """Trading configuration settings"""
    symbol: str
    leverage: int
    liquidity_multiplier: float
    balance_percentage: float
    hedge_mode: bool
    trading_mode: str


class Config:
    """Application configuration manager"""

    def __init__(self):
        self.api = self._load_api_config()
        self.trading = self._load_trading_config()
        self._validate_config()

    @staticmethod
    def _load_api_config() -> ApiConfig:
        """Load API configuration from environment variables"""
        return ApiConfig(
            api_key=os.getenv('API_KEY', ''),
            secret_key=os.getenv('SECRET_KEY', ''),
            base_url=os.getenv('BASE_URL', 'https://fapi.asterdex.com'),
            timeout=int(os.getenv('REQUEST_TIMEOUT', '5')),
            retry_attempts=int(os.getenv('RETRY_ATTEMPTS', '3')),
            retry_delay=int(os.getenv('RETRY_DELAY', '1'))
        )

    @staticmethod
    def _load_trading_config() -> TradingConfig:
        """Load trading configuration from environment variables"""
        return TradingConfig(
            symbol=os.getenv('SYMBOL', 'BTCUSDT'),
            leverage=int(os.getenv('LEVERAGE', '3')),
            liquidity_multiplier=float(os.getenv('LIQUIDITY_MULTIPLIER', '1.2')),
            balance_percentage=float(os.getenv('BALANCE_PERCENTAGE', '50')),
            hedge_mode=os.getenv('HEDGE_MODE', 'true').lower() == 'true',
            trading_mode=os.getenv('TRADING_MODE', 'single_pair')
        )

    def _validate_config(self):
        """Validate configuration parameters"""
        if not self.api.api_key or not self.api.secret_key:
            raise ValueError("API_KEY and SECRET_KEY must be set in .env file")

        if self.trading.leverage < 1 or self.trading.leverage > 100:
            raise ValueError("Leverage must be between 1 and 100")

        if self.trading.liquidity_multiplier < 1.0:
            raise ValueError("Liquidity multiplier must be at least 1.0")

        if self.trading.balance_percentage < 1 or self.trading.balance_percentage > 100:
            raise ValueError("Balance percentage must be between 1 and 100")

        if self.trading.trading_mode not in ['single_pair']:
            raise ValueError("Invalid trading mode. Currently only 'single_pair' is supported")