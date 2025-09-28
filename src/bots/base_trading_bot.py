import asyncio
import random
from typing import Tuple, Dict, Any
from src.core.api_client import AsterApiClient
from src.utils.position_calculator import PositionCalculator


class BaseTradingBot:

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

    async def open_single_position(self, symbol: str, side: str, leverage: int) -> Dict[str, Any]:
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
            if side == "LONG":
                result = await self.api_client.place_order(
                    symbol=symbol,
                    side="BUY",
                    position_side="LONG",
                    order_type="MARKET",
                    quantity=quantity
                )
                entry_price = float(result.get('avgPrice', mid_price))
                print(f"✅ Opened: LONG {quantity} @ {entry_price:.4f} | {symbol}")
            else:
                result = await self.api_client.place_order(
                    symbol=symbol,
                    side="SELL",
                    position_side="SHORT",
                    order_type="MARKET",
                    quantity=quantity
                )
                entry_price = float(result.get('avgPrice', mid_price))
                print(f"✅ Opened: SHORT {quantity} @ {entry_price:.4f} | {symbol}")

            return {'quantity': quantity, 'entry_price': entry_price, 'side': side}

        except Exception as e:
            print(f"❌ Error opening {side} position: {e}")
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

    async def get_position_details(self, symbol: str) -> list:
        positions = await self.api_client.get_position_risk(symbol)
        active_positions = []

        for pos in positions:
            if isinstance(pos, dict) and float(pos.get('positionAmt', 0)) != 0:
                active_positions.append({
                    'side': pos.get('positionSide'),
                    'amount': float(pos.get('positionAmt', 0)),
                    'entry_price': float(pos.get('entryPrice', 0)),
                    'unrealized_pnl': float(pos.get('unRealizedProfit', 0)),
                    'margin': float(pos.get('isolatedWallet', 0)) or float(pos.get('initialMargin', 0))
                })

        return active_positions

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