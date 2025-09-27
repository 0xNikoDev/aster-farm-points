import sys
import asyncio
from config import Config
from api_client import AsterApiClient
from trading_bot import TradingBot, PositionCalculator, VolumeTradingBot


async def run_single_pair_mode(config: Config, api_client: AsterApiClient):
    print(f"\nTrading Mode: {config.trading.trading_mode}")
    print(f"Symbol: {config.trading.symbol}")
    print(f"Leverage: {config.trading.leverage}x")
    print(f"Liquidity Multiplier: {config.trading.liquidity_multiplier}")
    print(f"Balance Percentage: {config.trading.balance_percentage}%")

    calculator = PositionCalculator(
        liquidity_multiplier=config.trading.liquidity_multiplier,
        balance_percentage=config.trading.balance_percentage
    )

    bot = TradingBot(api_client, calculator)

    await bot.check_account_balance()

    await bot.setup_trading_environment(
        symbol=config.trading.symbol,
        leverage=config.trading.leverage,
        hedge_mode=config.trading.hedge_mode
    )

    await asyncio.sleep(1)

    positions = await bot.open_hedged_positions(
        config.trading.symbol,
        config.trading.leverage
    )

    if positions:
        print("\n✓ Positions opened successfully")
        print("Waiting 5 seconds before checking status...")
        await asyncio.sleep(5)

        position_status = await bot.check_positions_status(config.trading.symbol)

        print("\n" + "=" * 50)
        print("Bot is running. Positions are open.")
        print("To close positions manually, stop the bot (Ctrl+C)")
        print("=" * 50)

        while True:
            await asyncio.sleep(1)


async def run_volume_trading_mode(config: Config, api_client: AsterApiClient):
    print(f"\nVolume Trading Mode: ENABLED")
    print(f"Symbol: {config.volume_trading.symbol}")
    print(f"Leverage: {config.volume_trading.leverage}x")
    print(f"Liquidity Multiplier: {config.volume_trading.liquidity_multiplier}")
    print(f"Balance Percentage: {config.volume_trading.balance_percentage}%")

    calculator = PositionCalculator(
        liquidity_multiplier=config.volume_trading.liquidity_multiplier,
        balance_percentage=config.volume_trading.balance_percentage
    )

    volume_bot = VolumeTradingBot(
        api_client=api_client,
        calculator=calculator,
        min_close_time_sec=config.volume_trading.min_close_time_sec,
        max_close_time_sec=config.volume_trading.max_close_time_sec,
        max_loss_usdt=config.volume_trading.max_loss_usdt,
        min_cycle_delay_sec=config.volume_trading.min_cycle_delay_sec,
        max_cycle_delay_sec=config.volume_trading.max_cycle_delay_sec
    )

    await volume_bot.base_bot.check_account_balance()

    await volume_bot.start_volume_trading(
        symbol=config.volume_trading.symbol,
        leverage=config.volume_trading.leverage,
        hedge_mode=True
    )


async def main_async():
    print("=" * 50)
    print("ASTER DEX POINTS FARMING BOT")
    print("=" * 50)

    try:
        config = Config()

        api_client = AsterApiClient(
            api_key=config.api.api_key,
            secret_key=config.api.secret_key,
            base_url=config.api.base_url,
            timeout=config.api.timeout
        )

        if config.volume_trading.enabled:
            await run_volume_trading_mode(config, api_client)
        else:
            await run_single_pair_mode(config, api_client)

    except KeyboardInterrupt:
        print("\n\nShutting down bot...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Attempting to close all positions...")

        try:
            if 'api_client' in locals() and 'config' in locals():
                if config.volume_trading.enabled:
                    symbol = config.volume_trading.symbol
                else:
                    symbol = config.trading.symbol

                calculator = PositionCalculator()
                bot = TradingBot(api_client, calculator)
                await bot._emergency_close_positions(symbol)
                print("Emergency close completed")
        except Exception as close_error:
            print(f"Failed to close positions: {close_error}")

        sys.exit(1)
    finally:
        if 'api_client' in locals():
            await api_client.close()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()