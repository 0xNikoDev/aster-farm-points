import sys
import asyncio
from config import Config
from api_client import AsterApiClient
from trading_bot import TradingBot, PositionCalculator, VolumeTradingBot


async def run_single_pair_mode(config: Config, bot: TradingBot):
    print(f"\nSingle Pair Mode: {config.trading.symbol} | Leverage: {config.trading.leverage}x")

    await bot.setup_trading_environment(
        symbol=config.trading.symbol,
        leverage=config.trading.leverage,
        hedge_mode=config.trading.hedge_mode
    )

    positions = await bot.open_hedged_positions(
        config.trading.symbol,
        config.trading.leverage
    )

    if positions:
        print("\n✓ Positions opened successfully")
        print("Press Ctrl+C to close positions and exit\n")

        while True:
            await asyncio.sleep(1)


async def run_volume_trading_mode(config: Config, calculator: PositionCalculator, api_client: AsterApiClient):
    volume_bot = VolumeTradingBot(
        api_client=api_client,
        calculator=calculator,
        min_close_time_sec=config.volume_trading.min_close_time_sec,
        max_close_time_sec=config.volume_trading.max_close_time_sec,
        max_loss_usdt=config.volume_trading.max_loss_usdt,
        min_cycle_delay_sec=config.volume_trading.min_cycle_delay_sec,
        max_cycle_delay_sec=config.volume_trading.max_cycle_delay_sec
    )

    await volume_bot.start_volume_trading(
        symbol=config.trading.symbol,
        leverage=config.trading.leverage,
        hedge_mode=config.trading.hedge_mode
    )


async def main_async():
    print("ASTER DEX BOT")
    config = None
    api_client = None

    try:
        config = Config()

        api_client = AsterApiClient(
            api_key=config.api.api_key,
            secret_key=config.api.secret_key,
            base_url=config.api.base_url,
            timeout=config.api.timeout
        )

        calculator = PositionCalculator(
            liquidity_multiplier=config.trading.liquidity_multiplier,
            balance_percentage=config.trading.balance_percentage
        )

        if config.trading.trading_mode == 'volume':
            await run_volume_trading_mode(config, calculator, api_client)
        else:
            bot = TradingBot(api_client, calculator)
            await run_single_pair_mode(config, bot)

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        if api_client and config:
            bot = TradingBot(api_client, PositionCalculator())
            await bot.close_positions(config.trading.symbol)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if api_client and config:
            bot = TradingBot(api_client, PositionCalculator())
            await bot.close_positions(config.trading.symbol)
        sys.exit(1)
    finally:
        if api_client:
            await api_client.close()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()