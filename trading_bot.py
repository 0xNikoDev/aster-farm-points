import asyncio
import random
from typing import Tuple, List, Dict, Any
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
        if hedge_mode:
            current_hedge_mode = await self.api_client.check_hedge_mode()
            if not current_hedge_mode:
                await self.api_client.set_hedge_mode(True)
                await asyncio.sleep(0.5)
        await self.api_client.set_leverage(symbol, leverage)

    async def get_market_prices(self, symbol: str) -> Tuple[float, float, float]:
        orderbook = await self.api_client.get_orderbook(symbol)
        best_bid = float(orderbook['bids'][0][0])
        best_ask = float(orderbook['asks'][0][0])
        mid_price = (best_bid + best_ask) / 2
        return best_bid, best_ask, mid_price

    async def open_hedged_positions(self, symbol: str, leverage: int) -> Dict[str, Any]:
        usdt_balance = await self.get_usdt_balance()
        if usdt_balance == 0:
            raise Exception("No USDT balance available")

        symbol_info = await self.api_client.get_symbol_info(symbol)
        if not symbol_info:
            raise Exception(f"Failed to get symbol info for {symbol}")

        best_bid, best_ask, mid_price = await self.get_market_prices(symbol)
        quantity = self.calculator.calculate_position_size(
            symbol_info, mid_price, usdt_balance, leverage
        )

        try:
            open_long_first = random.choice([True, False])

            if open_long_first:
                long_result = await self.api_client.place_order(
                    symbol=symbol,
                    side="BUY",
                    position_side="LONG",
                    order_type="MARKET",
                    quantity=quantity
                )
                long_price = float(long_result.get('avgPrice', mid_price))

                short_result = await self.api_client.place_order(
                    symbol=symbol,
                    side="SELL",
                    position_side="SHORT",
                    order_type="MARKET",
                    quantity=quantity
                )
                short_price = float(short_result.get('avgPrice', mid_price))

                print(f"✅ Opened: LONG {quantity} @ {long_price:.4f} "
                      f"→ SHORT {quantity} @ {short_price:.4f} | {symbol}")
            else:
                short_result = await self.api_client.place_order(
                    symbol=symbol,
                    side="SELL",
                    position_side="SHORT",
                    order_type="MARKET",
                    quantity=quantity
                )
                short_price = float(short_result.get('avgPrice', mid_price))

                long_result = await self.api_client.place_order(
                    symbol=symbol,
                    side="BUY",
                    position_side="LONG",
                    order_type="MARKET",
                    quantity=quantity
                )
                long_price = float(long_result.get('avgPrice', mid_price))

                print(f"✅ Opened: SHORT {quantity} @ {short_price:.4f} "
                      f"→ LONG {quantity} @ {long_price:.4f} | {symbol}")

            return {'quantity': quantity, 'long_price': long_price, 'short_price': short_price}

        except Exception as e:
            print(f"❌ Error opening positions: {e}")
            await self.close_positions(symbol, silent=True)
            raise

    async def check_positions_status(self, symbol: str) -> Dict[str, Any]:
        positions = await self.api_client.get_position_risk(symbol)
        total_pnl = 0.0

        for pos in positions:
            if isinstance(pos, dict) and float(pos.get('positionAmt', 0)) != 0:
                pnl = float(pos.get('unRealizedProfit', 0))
                total_pnl += pnl

        return {"total_pnl": total_pnl}

    async def get_usdt_balance(self) -> float:
        balances = await self.api_client.get_account_balance()
        for balance in balances:
            if isinstance(balance, dict) and balance.get('asset') == 'USDT':
                return float(balance.get('availableBalance', 0))
        return 0.0

    async def close_positions(self, symbol: str, silent: bool = False) -> None:
        try:
            positions = await self.api_client.get_position_risk(symbol)

            for pos in positions:
                if isinstance(pos, dict):
                    pos_amt = float(pos.get('positionAmt', 0))
                    if pos_amt != 0:
                        close_side = "SELL" if pos_amt > 0 else "BUY"
                        await self.api_client.place_order(
                            symbol=symbol,
                            side=close_side,
                            position_side=pos.get('positionSide'),
                            order_type="MARKET",
                            quantity=abs(pos_amt)
                        )
            if not silent:
                print("✓ Positions closed")
        except Exception as e:
            print(f"❌ Error closing positions: {e}")


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
        if abs(self.total_pnl) >= self.max_loss_usdt:
            return False

        try:
            balance_before = await self.base_bot.get_usdt_balance()

            # open positions
            await self.base_bot.open_hedged_positions(symbol, leverage)

            close_time = random.randint(self.min_close_time_sec, self.max_close_time_sec)
            start_time = asyncio.get_event_loop().time()
            check_interval = 2

            while True:
                elapsed = asyncio.get_event_loop().time() - start_time

                position_status = await self.base_bot.check_positions_status(symbol)
                current_pnl = position_status['total_pnl']

                if current_pnl > 0:
                    break

                if elapsed >= close_time:
                    break

                await asyncio.sleep(check_interval)

            await self.base_bot.close_positions(symbol)

            await asyncio.sleep(1)
            balance_after = await self.base_bot.get_usdt_balance()
            cycle_pnl = balance_after - balance_before

            self.total_pnl += cycle_pnl
            self.cycles_completed += 1

            if cycle_pnl < 0:
                print(f"❌ Loss: Cycle #{self.cycles_completed} | Loss: {abs(cycle_pnl):.4f} USDT | Total PnL: {self.total_pnl:.4f} USDT")
            else:
                print(f"✅ Profit: Cycle #{self.cycles_completed} | Profit: {cycle_pnl:.4f} USDT | Total PnL: {self.total_pnl:.4f} USDT")

            if abs(self.total_pnl) >= self.max_loss_usdt:
                return False

            delay = random.randint(self.min_cycle_delay_sec, self.max_cycle_delay_sec)
            await asyncio.sleep(delay)

            return True

        except Exception as e:
            print(f"\n❌ Error in trading cycle: {e}")
            await self.base_bot.close_positions(symbol, silent=True)
            return False

    async def start_volume_trading(self, symbol: str, leverage: int, hedge_mode: bool):
        print(f"\n▶️ Volume Trading: {symbol} | Leverage: {leverage}x | Max Loss: {self.max_loss_usdt} USDT")
        print(f"Close Time: {self.min_close_time_sec}-{self.max_close_time_sec}s | Delay: {self.min_cycle_delay_sec}-{self.max_cycle_delay_sec}s\n")

        await self.base_bot.setup_trading_environment(symbol, leverage, hedge_mode)

        try:
            while True:
                should_continue = await self.run_volume_trading_cycle(symbol, leverage)
                if not should_continue:
                    print(f"\n⏹️ Stopped | Cycles: {self.cycles_completed} | Final PnL: {self.total_pnl:.4f} USDT")
                    break

        except KeyboardInterrupt:
            print(f"\n\n⚠️ Interrupted - Closing positions...")
            await self.base_bot.close_positions(symbol)
            print(f"Final: {self.cycles_completed} cycles | PnL: {self.total_pnl:.4f} USDT")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            await self.base_bot.close_positions(symbol, silent=True)
            raise