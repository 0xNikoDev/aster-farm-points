import asyncio
import random
from typing import Optional, Tuple, List, Dict, Any
from decimal import Decimal
from api_client import AsterApiClient, SymbolInfo


class PositionCalculator:

    def __init__(self, liquidity_multiplier: float = 1.2, balance_percentage: float = 50):
        self.liquidity_multiplier = liquidity_multiplier
        self.balance_percentage = balance_percentage

    def calculate_position_size(self, symbol_info: SymbolInfo, price: float,
                               available_balance: float, leverage: int) -> float:
        max_position_value = (available_balance * (self.balance_percentage / 100)) / 2
        max_position_value_with_leverage = max_position_value * leverage
        max_quantity = max_position_value_with_leverage / price
        min_notional_qty = (symbol_info.min_notional * self.liquidity_multiplier) / price
        min_required = max(min_notional_qty, symbol_info.min_qty)
        quantity = max(min_required, min(max_quantity, max_quantity))
        quantity = round(quantity / symbol_info.step_size) * symbol_info.step_size
        return quantity


class TradingBot:

    def __init__(self, api_client: AsterApiClient, calculator: PositionCalculator):
        self.api_client = api_client
        self.calculator = calculator

    async def setup_trading_environment(self, symbol: str, leverage: int, hedge_mode: bool) -> None:
        print("=== Setting up trading environment ===")

        if hedge_mode:
            current_hedge_mode = await self.api_client.check_hedge_mode()
            print(f"Current hedge mode status: {current_hedge_mode}")

            if not current_hedge_mode:
                result = await self.api_client.set_hedge_mode(True)
                print(f"Hedge mode enabled: {result}")
                await asyncio.sleep(0.5)
            else:
                print("Hedge mode already enabled")

        leverage_result = await self.api_client.set_leverage(symbol, leverage)
        print(f"Leverage set to {leverage}x for {symbol}: {leverage_result}")

    async def get_market_prices(self, symbol: str) -> Tuple[float, float, float]:
        orderbook = await self.api_client.get_orderbook(symbol)
        best_bid = float(orderbook['bids'][0][0])
        best_ask = float(orderbook['asks'][0][0])
        mid_price = (best_bid + best_ask) / 2
        return best_bid, best_ask, mid_price

    async def open_hedged_positions(self, symbol: str, leverage: int) -> List[Dict[str, Any]]:
        print(f"\n=== Opening hedged positions for {symbol} ===")

        balances = await self.api_client.get_account_balance()
        usdt_balance = 0
        for balance in balances:
            if isinstance(balance, dict) and balance.get('asset') == 'USDT':
                usdt_balance = float(balance.get('availableBalance', 0))
                break

        if usdt_balance == 0:
            raise Exception("No USDT balance available")

        print(f"Available USDT balance: {usdt_balance}")

        symbol_info = await self.api_client.get_symbol_info(symbol)
        if not symbol_info:
            raise Exception(f"Failed to get symbol info for {symbol}")

        best_bid, best_ask, mid_price = await self.get_market_prices(symbol)
        print(f"Best bid: {best_bid}, Best ask: {best_ask}")

        quantity = self.calculator.calculate_position_size(
            symbol_info, mid_price, usdt_balance, leverage
        )
        print(f"Calculated quantity: {quantity} (using {self.calculator.balance_percentage}% of balance)")

        positions = []

        try:
            long_result = await self.api_client.place_order(
                symbol=symbol,
                side="BUY",
                position_side="LONG",
                order_type="MARKET",
                quantity=quantity
            )

            short_result = await self.api_client.place_order(
                symbol=symbol,
                side="SELL",
                position_side="SHORT",
                order_type="MARKET",
                quantity=quantity
            )

            order_id = long_result.get('orderId', 'N/A') if isinstance(long_result, dict) else 'N/A'
            print(f"LONG position opened: Order ID {order_id}")
            positions.append({"side": "LONG", "result": long_result})
            order_id = short_result.get('orderId', 'N/A') if isinstance(short_result, dict) else 'N/A'
            print(f"SHORT position opened: Order ID {order_id}")
            positions.append({"side": "SHORT", "result": short_result})

        except Exception as e:
            print(f"Error opening positions: {e}")
            await self._emergency_close_positions(symbol)
            raise

        return positions

    async def check_positions_status(self, symbol: str) -> Dict[str, Any]:
        print(f"\n=== Checking positions for {symbol} ===")

        positions = await self.api_client.get_position_risk(symbol)
        position_summary = {
            "symbol": symbol,
            "positions": [],
            "total_pnl": 0.0
        }

        for pos in positions:
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

    async def check_account_balance(self) -> List[Dict[str, Any]]:
        print("\n=== Account Balance ===")
        balances = await self.api_client.get_account_balance()
        active_balances = []

        for balance in balances:
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

    async def _emergency_close_positions(self, symbol: str) -> None:
        print(f"\n=== Emergency closing positions for {symbol} ===")

        try:
            positions = await self.api_client.get_position_risk(symbol)

            for pos in positions:
                if isinstance(pos, dict):
                    pos_amt = float(pos.get('positionAmt', 0))
                    if pos_amt != 0:
                        close_side = "SELL" if pos_amt > 0 else "BUY"

                        close_result = await self.api_client.place_order(
                            symbol=symbol,
                            side=close_side,
                            position_side=pos.get('positionSide'),
                            order_type="MARKET",
                            quantity=abs(pos_amt)
                        )
                        order_id = close_result.get('orderId', 'N/A') if isinstance(close_result, dict) else 'N/A'
                        print(f"Closed {pos.get('positionSide')} position: "
                              f"Order ID {order_id}")
                        await asyncio.sleep(0.5)

        except Exception as e:
            print(f"Failed to close positions: {e}")

    async def close_positions(self, symbol: str) -> None:
        print(f"\n=== Closing positions for {symbol} ===")

        try:
            positions = await self.api_client.get_position_risk(symbol)

            for pos in positions:
                if isinstance(pos, dict):
                    pos_amt = float(pos.get('positionAmt', 0))
                    if pos_amt != 0:
                        close_side = "SELL" if pos_amt > 0 else "BUY"

                        close_result = await self.api_client.place_order(
                            symbol=symbol,
                            side=close_side,
                            position_side=pos.get('positionSide'),
                            order_type="MARKET",
                            quantity=abs(pos_amt)
                        )
                        order_id = close_result.get('orderId', 'N/A') if isinstance(close_result, dict) else 'N/A'
                        print(f"Closed {pos.get('positionSide')} position: Order ID {order_id}")

        except Exception as e:
            print(f"Error closing positions: {e}")
            raise


class VolumeTradingBot:

    def __init__(self, api_client: AsterApiClient, calculator: PositionCalculator,
                 min_close_time_sec: int, max_close_time_sec: int,
                 max_loss_usdt: float, min_cycle_delay_sec: int, max_cycle_delay_sec: int):
        self.api_client = api_client
        self.calculator = calculator
        self.min_close_time_sec = min_close_time_sec
        self.max_close_time_sec = max_close_time_sec
        self.max_loss_usdt = max_loss_usdt
        self.min_cycle_delay_sec = min_cycle_delay_sec
        self.max_cycle_delay_sec = max_cycle_delay_sec
        self.total_pnl = 0.0
        self.cycles_completed = 0
        self.base_bot = TradingBot(api_client, calculator)

    async def run_volume_trading_cycle(self, symbol: str, leverage: int) -> bool:
        print(f"\n{'='*60}")
        print(f"CYCLE #{self.cycles_completed + 1} | Total PnL: {self.total_pnl:.4f} USDT")
        print(f"{'='*60}")

        if abs(self.total_pnl) >= self.max_loss_usdt:
            print(f"\n❌ MAX_LOSS reached: {self.total_pnl:.4f} USDT (limit: {self.max_loss_usdt})")
            return False

        try:
            positions = await self.base_bot.open_hedged_positions(symbol, leverage)

            close_time = random.randint(self.min_close_time_sec, self.max_close_time_sec)
            print(f"\nMonitoring for {close_time} seconds (or early close in profit)...")

            start_time = asyncio.get_event_loop().time()
            check_interval = 2

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time

                position_status = await self.base_bot.check_positions_status(symbol)
                current_pnl = position_status['total_pnl']

                if current_pnl > 0:
                    print(f"✅ Profit detected: {current_pnl:.4f} USDT - Closing early!")
                    break

                if elapsed >= close_time:
                    print(f"⏰ Time limit reached ({close_time}s) - Closing positions")
                    break

                await asyncio.sleep(check_interval)

            await self.base_bot.close_positions(symbol)

            await asyncio.sleep(1)
            final_status = await self.base_bot.check_positions_status(symbol)
            cycle_pnl = final_status['total_pnl']

            self.total_pnl += cycle_pnl
            self.cycles_completed += 1

            print(f"\n📊 Cycle #{self.cycles_completed} completed")
            print(f"   Cycle PnL: {cycle_pnl:.4f} USDT")
            print(f"   Total PnL: {self.total_pnl:.4f} USDT")
            print(f"   Max Loss Limit: {self.max_loss_usdt} USDT")

            if abs(self.total_pnl) >= self.max_loss_usdt:
                print(f"\n❌ MAX_LOSS reached after cycle completion")
                return False

            delay = random.randint(self.min_cycle_delay_sec, self.max_cycle_delay_sec)
            print(f"\n⏳ Waiting {delay} seconds before next cycle...")
            await asyncio.sleep(delay)

            return True

        except Exception as e:
            print(f"\n❌ Error in trading cycle: {e}")
            await self.base_bot._emergency_close_positions(symbol)
            return False

    async def start_volume_trading(self, symbol: str, leverage: int, hedge_mode: bool):
        print("\n" + "="*60)
        print("VOLUME TRADING MODE")
        print("="*60)
        print(f"Symbol: {symbol}")
        print(f"Leverage: {leverage}x")
        print(f"Close Time Range: {self.min_close_time_sec}-{self.max_close_time_sec} seconds")
        print(f"Max Loss: {self.max_loss_usdt} USDT")
        print(f"Cycle Delay: {self.min_cycle_delay_sec}-{self.max_cycle_delay_sec} seconds")
        print("="*60)

        await self.base_bot.setup_trading_environment(symbol, leverage, hedge_mode)

        try:
            while True:
                should_continue = await self.run_volume_trading_cycle(symbol, leverage)
                if not should_continue:
                    print("\n" + "="*60)
                    print("VOLUME TRADING STOPPED")
                    print(f"Total Cycles: {self.cycles_completed}")
                    print(f"Final PnL: {self.total_pnl:.4f} USDT")
                    print("="*60)
                    break

        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted by user - Closing all positions...")
            await self.base_bot._emergency_close_positions(symbol)
            print(f"\nFinal Statistics:")
            print(f"  Total Cycles: {self.cycles_completed}")
            print(f"  Final PnL: {self.total_pnl:.4f} USDT")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            await self.base_bot._emergency_close_positions(symbol)
            raise