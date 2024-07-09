# Crypto Trading Bot

This project is a Python-based cryptocurrency trading bot that uses the Binance exchange to execute a simple buy/sell strategy. The bot fetches the order book, analyzes market conditions, and places trades based on predefined parameters to achieve a minimum profit percentage.
![image](https://github.com/PahtrikProper/ORDER-BOOK-STRATEGY---1000SATS-USDT---BINANCE/assets/131755829/10bf669f-4bef-4d64-b8e4-2a3e78b7b319)

## Features

- Fetches and analyzes the order book for a specified symbol.
- Places buy orders when bullish market conditions are detected.
- Places sell orders to achieve a minimum profit percentage.
- Logs trading activities and performance.

## Requirements

- Python 3.7+
- `ccxt` library for interacting with Binance API
- `numpy` for numerical operations
- `python-dotenv` for loading environment variables

## Installation

### Manual Download

1. Download the bot files from the following links:

   - [trading_bot.py](sandbox:/mnt/data/trading_bot.py)

2. Install the required dependencies:

   ```bash
   pip install ccxt numpy python-dotenv
Create a .env file in the same directory as trading_bot.py and add your Binance API credentials:

env
Copy code
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret
Usage
Configure the trading parameters in the trading_bot.py script, such as SYMBOL, INITIAL_BALANCE, TRADE_AMOUNT, PROFIT_PERCENTAGE, etc.

Run the trading bot:

bash
Copy code
python trading_bot.py
Parameters
SYMBOL: The trading pair to trade (e.g., 1000SATS/USDT).
ORDER_BOOK_DEPTH: The depth of the order book to fetch for analysis.
INITIAL_BALANCE: The initial balance in USDT.
TRADE_AMOUNT: The fixed amount in USDT to trade each time.
TRADE_INTERVAL_SECONDS: The interval between trades in seconds.
PROFIT_PERCENTAGE: The minimum profit percentage to achieve for each trade.
VOLUME_IMBALANCE_THRESHOLD: The threshold for volume imbalance to determine market conditions.
MAX_REQUESTS_PER_MINUTE: The maximum number of API requests per minute.
RATE_LIMIT_SAFETY_FACTOR: The safety factor for rate limiting.
