# Aster DEX Points Farming Bot

A trading bot for automated points farming on Aster DEX through hedged positions with support for volume trading and dual account strategies.

## Features

### Core Features
- Smart position sizing based on percentage of available balance
- Configurable leverage and liquidity settings
- Real-time position monitoring
- Emergency position closing on errors
- PnL calculation through balance comparison

### Trading Modes

#### Volume Trading Mode
- Automated cycle trading with hedged positions (LONG and SHORT simultaneously)
- Random order execution sequence (LONG→SHORT or SHORT→LONG)
- Configurable position hold time
- Automatic position closing on positive PnL
- Cycle delay between trades
- Maximum loss limit protection
- Detailed PnL tracking per cycle

#### Dual Account Mode
- Trade on two accounts simultaneously with opposite positions
- Account 1 opens LONG while Account 2 opens SHORT (or vice versa)
- Position deviation monitoring (closes if loss exceeds threshold percentage)
- Real-time monitoring every second
- Combined PnL tracking across both accounts
- Automatic position closing on:
  - Combined positive PnL
  - Position deviation exceeding limit
  - Maximum loss reached

## Quick Start

### Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Configure `.env` file with your API credentials and trading parameters

### Configuration

#### Common Settings in `.env`:
- `MODE` - Trading mode: 'volume' or 'dual' (default: volume)
- `SYMBOL` - Trading pair (default: BTCUSDT)
- `LEVERAGE` - Position leverage (1-100, default: 20)
- `HEDGE_MODE` - Enable hedge mode: true/false (default: true)
- `LIQUIDITY_MULTIPLIER` - Safety multiplier for minimum order size (default: 1.2)
- `BALANCE_PERCENTAGE` - Percentage of available balance to use (1-100, default: 50)
- `MAX_LOSS_USDT` - Maximum allowed loss in USDT (default: 100)

#### Volume Mode Settings:
- `MIN_CLOSE_TIME_SEC` - Minimum time to hold positions in seconds (default: 10)
- `MAX_CLOSE_TIME_SEC` - Maximum time to hold positions in seconds (default: 30)
- `MIN_CYCLE_DELAY_SEC` - Minimum delay between cycles in seconds (default: 5)
- `MAX_CYCLE_DELAY_SEC` - Maximum delay between cycles in seconds (default: 15)

#### Dual Account Mode Settings:
- `API_KEY2` - API key for second account (required for dual mode)
- `API_SECRET2` - API secret for second account (required for dual mode)
- `MAX_POSITION_DEVIATION_PERCENT` - Maximum allowed position deviation in % (default: 20)
- `MIN_CYCLE_DELAY_SEC` - Minimum delay between cycles in seconds (default: 5)
- `MAX_CYCLE_DELAY_SEC` - Maximum delay between cycles in seconds (default: 15)

### Usage

#### Volume Trading Mode:
```bash
MODE=volume python main.py
```

#### Dual Account Mode:
```bash
MODE=dual python main.py
```

The bot will:
1. Check account balance(s)
2. Setup trading environment (leverage, hedge mode)
3. Open positions according to selected mode
4. Monitor position status
5. Calculate PnL through balance differences
6. Close positions based on strategy conditions

Stop with `Ctrl+C` to safely exit.

## Referral

Get maximum 1.5x points boost using referral link:
https://www.asterdex.com/en/referral/419099

## Architecture

### Project Structure
- `api_client.py` - API communication layer
- `position_calculator.py` - Position size calculation logic
- `base_trading_bot.py` - Base trading functionality
- `volume_trading_bot.py` - Volume trading mode implementation
- `dual_account_bot.py` - Dual account trading implementation
- `main.py` - Application entry point

## Safety Features
- Automatic position closing on errors
- Configurable liquidity multiplier for safe order sizing
- Balance percentage control (splits between positions)
- Hedge mode for risk management
- Maximum loss limits
- Position deviation monitoring (dual mode)
- Real-time PnL tracking through balance comparison