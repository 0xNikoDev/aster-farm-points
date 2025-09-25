import sys
import time
from config import Config
from api_client import AsterApiClient
from trading_bot import TradingBot, PositionCalculator


def main():
    """Main entry point for the Aster DEX Points Farming Bot"""
    print("=" * 50)
    print("ASTER DEX POINTS FARMING BOT")
    print("=" * 50)

    try:
        config = Config()
        print(f"\nTrading Mode: {config.trading.trading_mode}")
        print(f"Symbol: {config.trading.symbol}")
        print(f"Leverage: {config.trading.leverage}x")
        print(f"Liquidity Multiplier: {config.trading.liquidity_multiplier}")
        print(f"Balance Percentage: {config.trading.balance_percentage}%")

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

        bot = TradingBot(api_client, calculator)

        bot.check_account_balance()

        bot.setup_trading_environment(
            symbol=config.trading.symbol,
            leverage=config.trading.leverage,
            hedge_mode=config.trading.hedge_mode
        )

        time.sleep(1)

        positions = bot.open_hedged_positions(
            config.trading.symbol,
            config.trading.leverage
        )

        if positions:
            print("\n✓ Positions opened successfully")
            print("Waiting 5 seconds before checking status...")
            time.sleep(5)

            position_status = bot.check_positions_status(config.trading.symbol)

            print("\n" + "=" * 50)
            print("Bot is running. Positions are open.")
            print("To close positions manually, stop the bot (Ctrl+C)")
            print("=" * 50)

    except KeyboardInterrupt:
        print("\n\nShutting down bot...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Attempting to close all positions...")

        try:
            if 'bot' in locals() and 'config' in locals():
                bot._emergency_close_positions(config.trading.symbol)
                print("Emergency close completed")
        except Exception as close_error:
            print(f"Failed to close positions: {close_error}")

        sys.exit(1)
    finally:
        if 'api_client' in locals():
            api_client.close()


if __name__ == "__main__":
    main()