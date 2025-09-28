from src.core.api_client import SymbolInfo


class PositionCalculator:

    def __init__(self, liquidity_multiplier: float = 1.2, balance_percentage: float = 50):
        self.liquidity_multiplier = liquidity_multiplier
        self.balance_percentage = balance_percentage

    def calculate_position_size(self, symbol_info: SymbolInfo, price: float,
                               available_balance: float, leverage: int,
                               single_position: bool = False) -> float:
        # For dual mode (single position per account) don't divide by 2
        # For hedge mode (two positions on same account) divide by 2
        divider = 1 if single_position else 2
        max_position_value = (available_balance * (self.balance_percentage / 100)) / divider
        max_position_value_with_leverage = max_position_value * leverage
        max_quantity = max_position_value_with_leverage / price
        min_notional_qty = (symbol_info.min_notional * self.liquidity_multiplier) / price
        min_required = max(min_notional_qty, symbol_info.min_qty)
        quantity = max(min_required, min(max_quantity, max_quantity))
        quantity = round(quantity / symbol_info.step_size) * symbol_info.step_size
        return quantity