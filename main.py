import asyncio
from config import Config
from src.core import AsterApiClient
from src.utils import PositionCalculator
from src.bots import VolumeTradingBot, DualAccountBot


async def main():
    config = Config()

    calculator = PositionCalculator(
        liquidity_multiplier=config.trading.liquidity_multiplier,
        balance_percentage=config.trading.balance_percentage
    )

    if config.trading.mode == 'volume':
        api_client = AsterApiClient(
            config.api.api_key,
            config.api.api_secret,
            base_url=config.api.base_url
        )

        bot = VolumeTradingBot(
            api_client=api_client,
            calculator=calculator,
            min_close_time_sec=config.volume.min_close_time_sec,
            max_close_time_sec=config.volume.max_close_time_sec,
            max_loss_usdt=config.trading.max_loss_usdt,
            min_cycle_delay_sec=config.trading.min_cycle_delay_sec,
            max_cycle_delay_sec=config.trading.max_cycle_delay_sec
        )

        await bot.start_volume_trading(
            config.trading.symbol,
            config.trading.leverage,
            config.trading.hedge_mode
        )

    elif config.trading.mode == 'dual':
        api_client1 = AsterApiClient(
            config.api.api_key,
            config.api.api_secret,
            base_url=config.api.base_url
        )
        api_client2 = AsterApiClient(
            config.api.api_key2,
            config.api.api_secret2,
            base_url=config.api.base_url
        )

        bot = DualAccountBot(
            api_client1=api_client1,
            api_client2=api_client2,
            calculator=calculator,
            max_position_deviation_percent=config.dual.max_position_deviation_percent,
            max_loss_usdt=config.trading.max_loss_usdt,
            min_cycle_delay_sec=config.trading.min_cycle_delay_sec,
            max_cycle_delay_sec=config.trading.max_cycle_delay_sec,
            min_hold_time_sec=config.dual.min_hold_time_sec,
            max_hold_time_sec=config.dual.max_hold_time_sec
        )

        await bot.start_dual_trading(
            config.trading.symbol,
            config.trading.leverage,
            config.trading.hedge_mode
        )

    else:
        raise ValueError(f"Unknown mode: {config.trading.mode}. Use 'volume' or 'dual'")


if __name__ == "__main__":
    asyncio.run(main())