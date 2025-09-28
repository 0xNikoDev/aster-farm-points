import asyncio
import random
from src.core.api_client import AsterApiClient
from src.utils.position_calculator import PositionCalculator
from src.bots.base_trading_bot import BaseTradingBot


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
        self.base_bot = BaseTradingBot(api_client, calculator)

    async def run_volume_trading_cycle(self, symbol: str, leverage: int) -> bool:
        if abs(self.total_pnl) >= self.max_loss_usdt:
            return False

        try:
            balance_before = await self.base_bot.get_usdt_balance()
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