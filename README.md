# Aster DEX Points Farming Bot

A trading bot for automated points farming on Aster DEX through hedged positions.

## Features

- Single pair trading mode with configurable symbol
- Automatic hedge position opening (LONG and SHORT simultaneously)
- Smart position sizing based on percentage of available balance
- Configurable leverage and liquidity settings
- Real-time position monitoring
- Emergency position closing on errors

## Quick Start

### Installation

1. Clone the repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Edit `.env` file with your API credentials and trading parameters

### Configuration

Key settings in `.env`:
- `SYMBOL` - Trading pair (default: BTCUSDT)
- `LEVERAGE` - Position leverage (1-100)
- `LIQUIDITY_MULTIPLIER` - Safety multiplier for minimum order size
- `BALANCE_PERCENTAGE` - Percentage of available balance to use (1-100, default: 50)

### Usage

Run the bot:
```bash
python main.py
```

The bot will:
1. Check account balance
2. Setup trading environment (leverage, hedge mode)
3. Open hedged positions
4. Monitor position status

Stop with `Ctrl+C` to safely exit.

## Referral

Get maximum 1.5x points boost using referral link:
https://www.asterdex.com/en/referral/419099

## Architecture
- `config.py` - Configuration management
- `api_client.py` - API communication layer
- `trading_bot.py` - Core trading logic
- `main.py` - Application entry point

## Safety

- Automatic position closing on errors
- Configurable liquidity multiplier for safe order sizing
- Balance percentage control (splits between LONG and SHORT positions)
- Hedge mode for risk management