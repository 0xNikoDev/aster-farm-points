import time
from typing import Optional, Tuple, List, Dict, Any
from decimal import Decimal
from api_client import AsterApiClient, SymbolInfo


class PositionCalculator:
    """Calculator for position sizing and parameters"""

    def __init__(self, liquidity_multiplier: float = 1.2, balance_percentage: float = 50):
        self.liquidity_multiplier = liquidity_multiplier
        self.balance_percentage = balance_percentage

    def calculate_position_size(self, symbol_info: SymbolInfo, price: float,
                               available_balance: float, leverage: int) -> float:
        """
        Calculate position size based on available balance percentage
        Takes into account that we need to open 2 positions (LONG and SHORT)
        """
        # Calculate maximum position value based on balance percentage
        # Divide by 2 since we're opening two positions
        max_position_value = (available_balance * (self.balance_percentage / 100)) / 2

        # Apply leverage to get the actual position size
        max_position_value_with_leverage = max_position_value * leverage

        # Calculate quantity based on position value
        max_quantity = max_position_value_with_leverage / price

        # Calculate minimum required quantity
        min_notional_qty = (symbol_info.min_notional * self.liquidity_multiplier) / price
        min_required = max(min_notional_qty, symbol_info.min_qty)

        # Use the smaller of max_quantity or a reasonable maximum
        # but ensure it's at least the minimum required
        quantity = max(min_required, min(max_quantity, max_quantity))

        # Round to step size
        quantity = round(quantity / symbol_info.step_size) * symbol_info.step_size

        return quantity


class TradingBot:
    """Main trading bot for Aster DEX points farming"""

    def __init__(self, api_client: AsterApiClient, calculator: PositionCalculator):
        self.api_client = api_client
        self.calculator = calculator

    def setup_trading_environment(self, symbol: str, leverage: int, hedge_mode: bool) -> None:
        """Setup trading environment with specified parameters"""
        print("=== Setting up trading environment ===")

        if hedge_mode:
            current_hedge_mode = self.api_client.check_hedge_mode()
            print(f"Current hedge mode status: {current_hedge_mode}")

            if not current_hedge_mode:
                result = self.api_client.set_hedge_mode(True)
                print(f"Hedge mode enabled: {result}")
                time.sleep(0.5)
            else:
                print("Hedge mode already enabled")

        leverage_result = self.api_client.set_leverage(symbol, leverage)
        print(f"Leverage set to {leverage}x for {symbol}: {leverage_result}")

    def get_market_prices(self, symbol: str) -> Tuple[float, float, float]:
        """Get current market prices from orderbook"""
        orderbook = self.api_client.get_orderbook(symbol)
        best_bid = float(orderbook['bids'][0][0])
        best_ask = float(orderbook['asks'][0][0])
        mid_price = (best_bid + best_ask) / 2
        return best_bid, best_ask, mid_price

    def open_hedged_positions(self, symbol: str, leverage: int) -> List[Dict[str, Any]]:
        """Open both LONG and SHORT positions for hedging"""
        print(f"\n=== Opening hedged positions for {symbol} ===")

        # Get account balance first
        balances = self.api_client.get_account_balance()
        usdt_balance = 0
        for balance in balances:
            # Check if balance is a dict before using .get()
            if isinstance(balance, dict) and balance.get('asset') == 'USDT':
                usdt_balance = float(balance.get('availableBalance', 0))
                break

        if usdt_balance == 0:
            raise Exception("No USDT balance available")

        print(f"Available USDT balance: {usdt_balance}")

        symbol_info = self.api_client.get_symbol_info(symbol)
        if not symbol_info:
            raise Exception(f"Failed to get symbol info for {symbol}")

        best_bid, best_ask, mid_price = self.get_market_prices(symbol)
        print(f"Best bid: {best_bid}, Best ask: {best_ask}")

        quantity = self.calculator.calculate_position_size(
            symbol_info, mid_price, usdt_balance, leverage
        )
        print(f"Calculated quantity: {quantity} (using {self.calculator.balance_percentage}% of balance)")

        positions = []

        try:
            long_result = self.api_client.place_order(
                symbol=symbol,
                side="BUY",
                position_side="LONG",
                order_type="MARKET",
                quantity=quantity
            )
            order_id = long_result.get('orderId', 'N/A') if isinstance(long_result, dict) else 'N/A'
            print(f"LONG position opened: Order ID {order_id}")
            positions.append({"side": "LONG", "result": long_result})

            time.sleep(0.5)

            short_result = self.api_client.place_order(
                symbol=symbol,
                side="SELL",
                position_side="SHORT",
                order_type="MARKET",
                quantity=quantity
            )
            order_id = short_result.get('orderId', 'N/A') if isinstance(short_result, dict) else 'N/A'
            print(f"SHORT position opened: Order ID {order_id}")
            positions.append({"side": "SHORT", "result": short_result})

        except Exception as e:
            print(f"Error opening positions: {e}")
            self._emergency_close_positions(symbol)
            raise

        return positions

    def check_positions_status(self, symbol: str) -> Dict[str, Any]:
        """Check current position status and P&L"""
        print(f"\n=== Checking positions for {symbol} ===")

        positions = self.api_client.get_position_risk(symbol)
        position_summary = {
            "symbol": symbol,
            "positions": [],
            "total_pnl": 0.0
        }

        for pos in positions:
            # Check if pos is a dict before using .get()
            if isinstance(pos, dict) and float(pos.get('positionAmt', 0)) != 0:
                pnl = float(pos.get('unRealizedProfit', 0))
                position_summary["total_pnl"] += pnl

                position_info = {
                    "side": pos.get('positionSide'),
                    "amount": pos.get('positionAmt'),
                    "entry_price": pos.get('entryPrice'),
                    "unrealized_pnl": pnl
                }
                position_summary["positions"].append(position_info)

                print(f"Side: {position_info['side']}, "
                      f"Amount: {position_info['amount']}, "
                      f"Entry Price: {position_info['entry_price']}, "
                      f"PnL: {position_info['unrealized_pnl']}")

        print(f"\nTotal PnL: {position_summary['total_pnl']} USDT")
        return position_summary

    def check_account_balance(self) -> List[Dict[str, Any]]:
        """Check account balance"""
        print("\n=== Account Balance ===")
        balances = self.api_client.get_account_balance()
        active_balances = []

        for balance in balances:
            # Check if balance is a dict before using .get()
            if isinstance(balance, dict) and float(balance.get('balance', 0)) > 0:
                active_balance = {
                    "asset": balance.get('asset'),
                    "balance": balance.get('balance'),
                    "available": balance.get('availableBalance')
                }
                active_balances.append(active_balance)
                print(f"{active_balance['asset']}: {active_balance['balance']} "
                      f"(Available: {active_balance['available']})")

        return active_balances

    def _emergency_close_positions(self, symbol: str) -> None:
        """Emergency close all positions for a symbol"""
        print(f"\n=== Emergency closing positions for {symbol} ===")

        try:
            positions = self.api_client.get_position_risk(symbol)

            for pos in positions:
                # Check if pos is a dict before using .get()
                if isinstance(pos, dict):
                    pos_amt = float(pos.get('positionAmt', 0))
                    if pos_amt != 0:
                        close_side = "SELL" if pos_amt > 0 else "BUY"

                        close_result = self.api_client.place_order(
                            symbol=symbol,
                            side=close_side,
                            position_side=pos.get('positionSide'),
                            order_type="MARKET",
                            quantity=abs(pos_amt)
                        )
                        order_id = close_result.get('orderId', 'N/A') if isinstance(close_result, dict) else 'N/A'
                        print(f"Closed {pos.get('positionSide')} position: "
                              f"Order ID {order_id}")
                        time.sleep(0.5)

        except Exception as e:
            print(f"Failed to close positions: {e}")