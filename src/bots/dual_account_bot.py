import asyncio
import random
from typing import Dict, Any, Tuple
from src.core.api_client import AsterApiClient
from src.utils.position_calculator import PositionCalculator
from src.bots.base_trading_bot import BaseTradingBot


class DualAccountBot:

    def __init__(self, api_client1: AsterApiClient, api_client2: AsterApiClient,
                 calculator: PositionCalculator, max_position_deviation_percent: float = 20,
                 max_loss_usdt: float = 100, min_cycle_delay_sec: int = 5,
                 max_cycle_delay_sec: int = 15, min_hold_time_sec: int = 30,
                 max_hold_time_sec: int = 300):
        self.bot1 = BaseTradingBot(api_client1, calculator)
        self.bot2 = BaseTradingBot(api_client2, calculator)
        self.calculator = calculator
        self.max_position_deviation_percent = max_position_deviation_percent
        self.max_loss_usdt = max_loss_usdt
        self.min_cycle_delay_sec = min_cycle_delay_sec
        self.max_cycle_delay_sec = max_cycle_delay_sec
        self.min_hold_time_sec = min_hold_time_sec
        self.max_hold_time_sec = max_hold_time_sec
        self.total_pnl = 0.0
        self.cycles_completed = 0
        self.account1_pnl = 0.0
        self.account2_pnl = 0.0

    async def setup_both_accounts(self, symbol: str, leverage: int, hedge_mode: bool):
        await asyncio.gather(
            self.bot1.setup_trading_environment(symbol, leverage, hedge_mode),
            self.bot2.setup_trading_environment(symbol, leverage, hedge_mode)
        )

    @staticmethod
    async def _open_market_position(bot: BaseTradingBot, symbol: str,
                                    position_side: str, quantity: float,
                                    account_name: str) -> Dict[str, Any]:
        """Helper method to open a market position"""
        side = "BUY" if position_side == "LONG" else "SELL"

        result = await bot.api_client.place_order(
            symbol=symbol,
            side=side,
            position_side=position_side,
            order_type="MARKET",
            quantity=quantity
        )

        entry_price = float(result.get('avgPrice', 0))
        print(f"✅ {account_name}: {position_side} {quantity} @ {entry_price:.4f} | {symbol}")

        return {
            'quantity': quantity,
            'entry_price': entry_price,
            'side': position_side
        }

    async def open_opposite_positions(self, symbol: str, leverage: int) -> Tuple[Dict, Dict]:
        # Get balances from both accounts
        balance1 = await self.bot1.get_usdt_balance()
        balance2 = await self.bot2.get_usdt_balance()

        # Use minimum balance for position sizing
        min_balance = min(balance1, balance2)
        print(f"💰 Account 1: {balance1:.2f} USDT | Account 2: {balance2:.2f} USDT")
        print(f"📊 Using minimum balance: {min_balance:.2f} USDT for equal position sizing")

        # Get symbol info and market prices
        symbol_info = await self.bot1.api_client.get_symbol_info(symbol)
        if not symbol_info:
            raise Exception(f"Failed to get symbol info for {symbol}")

        best_bid, best_ask, mid_price = await self.bot1.get_market_prices(symbol)

        # Calculate position size based on minimum balance
        # Use single_position=True since each account opens only one position
        quantity = self.calculator.calculate_position_size(
            symbol_info, mid_price, min_balance, leverage, single_position=True
        )

        # Randomly decide which account gets LONG and which gets SHORT
        long_on_first = random.choice([True, False])

        try:
            if long_on_first:
                # Account 1: LONG, Account 2: SHORT
                position1_info = await self._open_market_position(
                    self.bot1, symbol, "LONG", quantity, "Account 1"
                )
                position2_info = await self._open_market_position(
                    self.bot2, symbol, "SHORT", quantity, "Account 2"
                )
            else:
                # Account 1: SHORT, Account 2: LONG
                position1_info = await self._open_market_position(
                    self.bot1, symbol, "SHORT", quantity, "Account 1"
                )
                position2_info = await self._open_market_position(
                    self.bot2, symbol, "LONG", quantity, "Account 2"
                )

            margin_per_position = (quantity * mid_price) / leverage
            print(f"💼 Margin per position: {margin_per_position:.2f} USDT")

            return position1_info, position2_info

        except Exception as e:
            print(f"❌ Error opening opposite positions: {e}")
            await self.close_all_positions(symbol)
            raise

    @staticmethod
    async def calculate_position_deviation(position: Dict, initial_margin: float) -> float:
        if initial_margin == 0:
            return 0
        pnl = position.get('unrealized_pnl', 0)
        return abs(pnl / initial_margin) * 100

    async def _check_deviation(self, positions: list, position_info: Dict,
                              initial_margin: float, account_name: str) -> bool:
        """Check if position deviation exceeds threshold"""
        for pos in positions:
            if pos['side'] == position_info['side']:
                deviation = await self.calculate_position_deviation(pos, initial_margin)
                if deviation >= self.max_position_deviation_percent:
                    print(f"⚠️ {account_name} deviation: {deviation:.2f}% - Closing positions")
                    return True
        return False

    async def monitor_positions(self, symbol: str, position1_info: Dict,
                               position2_info: Dict, leverage: int) -> bool:
        check_interval = 1
        hold_time = random.randint(self.min_hold_time_sec, self.max_hold_time_sec)
        start_time = asyncio.get_event_loop().time()

        # Calculate margins
        position1_margin = position1_info['quantity'] * position1_info['entry_price'] / leverage
        position2_margin = position2_info['quantity'] * position2_info['entry_price'] / leverage

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            positions1 = await self.bot1.get_position_details(symbol)
            positions2 = await self.bot2.get_position_details(symbol)

            if not positions1 or not positions2:
                return True

            # Check deviations for both accounts
            if await self._check_deviation(positions1, position1_info, position1_margin, "Account 1"):
                return True

            if await self._check_deviation(positions2, position2_info, position2_margin, "Account 2"):
                return True

            # Check combined PnL
            combined_pnl = sum(p['unrealized_pnl'] for p in positions1) + \
                          sum(p['unrealized_pnl'] for p in positions2)

            if combined_pnl > 0:
                print(f"✅ Positive PnL detected: {combined_pnl:.4f} USDT - Closing positions")
                return True

            if elapsed >= hold_time:
                print(f"⏱️ Hold time reached ({hold_time}s) - Closing positions")
                return True

            await asyncio.sleep(check_interval)

    async def close_all_positions(self, symbol: str):
        await asyncio.gather(
            self.bot1.close_positions(symbol, silent=True),
            self.bot2.close_positions(symbol, silent=True)
        )
        print("✓ All positions closed on both accounts")

    def _print_cycle_result(self, cycle_pnl: float, account1_cycle_pnl: float,
                           account2_cycle_pnl: float):
        """Print cycle result with proper formatting"""
        status = "✅ Profit" if cycle_pnl >= 0 else "❌ Loss"
        print(f"{status}: Cycle #{self.cycles_completed}")
        print(f"   Account 1: {account1_cycle_pnl:.4f} USDT | Account 2: {account2_cycle_pnl:.4f} USDT")

        if cycle_pnl >= 0:
            print(f"   Combined Profit: {cycle_pnl:.4f} USDT | Total PnL: {self.total_pnl:.4f} USDT")
        else:
            print(f"   Combined Loss: {abs(cycle_pnl):.4f} USDT | Total PnL: {self.total_pnl:.4f} USDT")

    async def run_dual_trading_cycle(self, symbol: str, leverage: int) -> bool:
        if abs(self.total_pnl) >= self.max_loss_usdt:
            return False

        try:
            balance1_before = await self.bot1.get_usdt_balance()
            balance2_before = await self.bot2.get_usdt_balance()

            position1_info, position2_info = await self.open_opposite_positions(symbol, leverage)

            monitoring_task = asyncio.create_task(
                self.monitor_positions(symbol, position1_info, position2_info, leverage)
            )

            await monitoring_task

            await self.close_all_positions(symbol)
            await asyncio.sleep(1)

            balance1_after = await self.bot1.get_usdt_balance()
            balance2_after = await self.bot2.get_usdt_balance()

            account1_cycle_pnl = balance1_after - balance1_before
            account2_cycle_pnl = balance2_after - balance2_before
            cycle_pnl = account1_cycle_pnl + account2_cycle_pnl

            self.account1_pnl += account1_cycle_pnl
            self.account2_pnl += account2_cycle_pnl
            self.total_pnl += cycle_pnl
            self.cycles_completed += 1

            self._print_cycle_result(cycle_pnl, account1_cycle_pnl, account2_cycle_pnl)

            if abs(self.total_pnl) >= self.max_loss_usdt:
                return False

            delay = random.randint(self.min_cycle_delay_sec, self.max_cycle_delay_sec)
            print(f"⏳ Waiting {delay} seconds before next cycle...")
            await asyncio.sleep(delay)

            return True

        except Exception as e:
            print(f"\n❌ Error in dual trading cycle: {e}")
            await self.close_all_positions(symbol)
            return False

    async def start_dual_trading(self, symbol: str, leverage: int, hedge_mode: bool = False):
        print(f"\n▶️ Dual Account Trading: {symbol} | Leverage: {leverage}x")
        print(f"Max Deviation: {self.max_position_deviation_percent}% | Max Loss: {self.max_loss_usdt} USDT")
        print(f"Hold time: {self.min_hold_time_sec}-{self.max_hold_time_sec}s")
        print(f"Delay between cycles: {self.min_cycle_delay_sec}-{self.max_cycle_delay_sec}s\n")

        await self.setup_both_accounts(symbol, leverage, hedge_mode)

        try:
            while True:
                should_continue = await self.run_dual_trading_cycle(symbol, leverage)
                if not should_continue:
                    print(f"\n⏹️ Stopped | Cycles: {self.cycles_completed}")
                    print(f"Account 1 PnL: {self.account1_pnl:.4f} USDT")
                    print(f"Account 2 PnL: {self.account2_pnl:.4f} USDT")
                    print(f"Total PnL: {self.total_pnl:.4f} USDT")
                    break

        except KeyboardInterrupt:
            print(f"\n\n⚠️ Interrupted - Closing all positions...")
            await self.close_all_positions(symbol)
            print(f"Final Stats:")
            print(f"Cycles: {self.cycles_completed}")
            print(f"Account 1 PnL: {self.account1_pnl:.4f} USDT")
            print(f"Account 2 PnL: {self.account2_pnl:.4f} USDT")
            print(f"Total PnL: {self.total_pnl:.4f} USDT")
        except Exception as e:
            print(f"\n❌ Fatal error: {e}")
            await self.close_all_positions(symbol)
            raise