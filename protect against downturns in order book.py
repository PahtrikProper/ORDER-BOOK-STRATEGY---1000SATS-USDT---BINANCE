"""
# Trading Bot for 1000SATS/USDT on Binance

## Overview

This trading bot is designed to perform live trading on the Binance exchange for the `1000SATS/USDT` trading pair. The bot uses the `ccxt` library to interact with the Binance API and bases its trading decisions purely on order book analysis. The primary goal is to buy and sell based on detected market conditions, volume imbalances, and the presence of large orders (whales).

## Strategy

The bot makes trading decisions based on the following strategy:

1. **Order Book Analysis**: Analyzes the top 10 levels of the order book to detect market conditions, volume imbalances, and large orders.
2. **Market Conditions**:
    - **Bullish**: More buy volume than sell volume, detected large bid orders, no significant sell walls.
    - **Bearish**: More sell volume than buy volume, detected large ask orders, or significant sell walls.
    - **Neutral**: Neither bullish nor bearish conditions detected.
3. **Trading Logic**:
    - **Buy**: Place a buy order when the market condition changes from bearish or neutral to bullish.
    - **Sell**: Place a sell order when a profit target is met or if the market condition changes to bearish during an active trade.

## Configuration Parameters

- `SYMBOL`: The trading pair (default is `1000SATS/USDT`).
- `ORDER_BOOK_DEPTH`: Number of levels in the order book to analyze (default is 100).
- `TRADE_AMOUNT`: Fixed amount in USDT to trade each time (default is 100).
- `TRADE_INTERVAL_SECONDS`: Interval between trade checks (default is 1 second).
- `PROFIT_PERCENTAGE`: Minimum profit target for selling (default is 0.44%).
- `VOLUME_IMBALANCE_THRESHOLD`: Threshold for detecting volume imbalances (default is 1.2).
- `SELL_WALL_THRESHOLD`: Threshold for detecting large sell walls (default is 1.5).
- `LARGE_ORDER_THRESHOLD`: Threshold for detecting large orders (default is 1% of total volume).

## Functions

### `fetch_order_book(symbol, limit=ORDER_BOOK_DEPTH)`

Fetches the order book for the specified symbol and depth. Handles network, exchange, and rate limit errors.

### `analyze_order_book(order_book)`

Analyzes the top 10 levels of the order book to determine:
- Volume imbalance between bids and asks.
- Presence of large sell walls.
- Large orders in bids and asks.
- Ideal exit price for a profitable sell.
- Market condition (bullish, bearish, or neutral).

### `place_order(symbol, side, amount, price=None)`

Places a limit buy or sell order on the exchange. Logs the order details and handles errors.

### `get_current_balance(asset)`

Fetches the current available balance of the specified asset. Handles errors.

### `check_open_orders(symbol)`

Checks for any open orders for the specified symbol. Returns `True` if there are open orders, `False` otherwise.

### `cancel_all_orders(symbol)`

Cancels all open orders for the specified symbol. Handles errors and logs the cancellations.

### `trading_bot(symbol)`

The main trading bot function:
- Checks the order book and market conditions at regular intervals.
- Places buy orders when market conditions change to bullish.
- Places sell orders when profit targets are met or market conditions change to bearish.
- Cancels and replaces orders based on real-time analysis of the order book.

## How to Run

1. **Install Dependencies**: Ensure you have `ccxt`, `python-dotenv`, and other required libraries installed.
    ```bash
    pip install ccxt python-dotenv
    ```

2. **Set Up Environment Variables**: Create a `.env` file with your Binance API credentials.
    ```
    BINANCE_API_KEY=your_api_key
    BINANCE_API_SECRET=your_api_secret
    ```

3. **Run the Bot**: Execute the script.
    ```bash
    python your_script_name.py
    ```

## Logging

The bot uses Python's built-in logging module to log information, warnings, and errors. Logs include details about placed orders, detected market conditions, balance updates, and any errors encountered during execution.

## Disclaimer

This bot is for educational purposes only. Trading cryptocurrencies involves significant risk, and you should not trade with money you cannot afford to lose. The author is not responsible for any financial losses incurred while using this bot.

---

Feel free to modify the parameters and improve the strategy according to your needs. Happy trading!
"""
import os
import ccxt
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configurable Parameters
SYMBOL = '1000SATS/USDT'
ORDER_BOOK_DEPTH = 100  # Increased for more comprehensive analysis
TRADE_AMOUNT = 100  # Fixed amount in USDT to trade each time
TRADE_INTERVAL_SECONDS = 1  # Check every second
PROFIT_PERCENTAGE = 0.0044  # Minimum 0.44% profit target

# Order Book Analysis Parameters
VOLUME_IMBALANCE_THRESHOLD = 1.2  # 20% more volume on buy side than sell side
SELL_WALL_THRESHOLD = 1.5  # Ratio indicating a large sell wall
LARGE_ORDER_THRESHOLD = 0.01  # 1% of total volume as a large order

# Rate Limiting Parameters
MAX_REQUESTS_PER_MINUTE = 1200
RATE_LIMIT_SAFETY_FACTOR = 0.75

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Binance API with rate limiting
exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'rateLimit': int((60 / MAX_REQUESTS_PER_MINUTE) * 1000 / RATE_LIMIT_SAFETY_FACTOR)
})

def fetch_order_book(symbol, limit=ORDER_BOOK_DEPTH):
    try:
        return exchange.fetch_order_book(symbol, limit=limit)
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Exchange error: {e}")
    except ccxt.RateLimitExceeded as e:
        logger.error(f"Rate limit exceeded: {e}")
        time.sleep(60)
    return None

def analyze_order_book(order_book):
    asks = order_book['asks'][:10]  # Top 10 asks
    bids = order_book['bids'][:10]  # Top 10 bids
    
    if not asks or not bids:
        logger.warning("Not enough asks or bids in the order book for analysis.")
        return None
    
    # Calculate buy/sell volume imbalance
    total_bid_volume = sum(volume for price, volume in bids)
    total_ask_volume = sum(volume for price, volume in asks)
    volume_imbalance = total_bid_volume / total_ask_volume

    # Detect large sell walls
    large_sell_wall = any(volume > total_bid_volume / SELL_WALL_THRESHOLD for price, volume in asks)

    # Detect large orders in the bids and asks
    large_bid_order = any(volume > LARGE_ORDER_THRESHOLD * total_bid_volume for price, volume in bids)
    large_ask_order = any(volume > LARGE_ORDER_THRESHOLD * total_ask_volume for price, volume in asks)

    # Calculate ideal exit price based on profit percentage
    min_exit_price = min(ask[0] for ask in asks) * (1 + PROFIT_PERCENTAGE)
    
    # Determine market condition
    market_condition = 'neutral'
    if large_sell_wall or volume_imbalance < 1 / VOLUME_IMBALANCE_THRESHOLD or large_ask_order:
        market_condition = 'bearish'
    elif volume_imbalance > VOLUME_IMBALANCE_THRESHOLD and large_bid_order:
        market_condition = 'bullish'
    
    return {
        'best_ask_price': min(ask[0] for ask in asks),
        'best_bid_price': max(bid[0] for bid in bids),
        'min_exit_price': min_exit_price,
        'market_condition': market_condition,
        'large_sell_wall': large_sell_wall
    }

def place_order(symbol, side, amount, price=None):
    try:
        if side == 'buy':
            order = exchange.create_limit_buy_order(symbol, amount, price)
        else:
            order = exchange.create_limit_sell_order(symbol, amount, price)
        logger.info(f"Placed {side} order: {amount:.8f} {symbol} at {price:.8f}")
        return order
    except ccxt.BaseError as e:
        logger.error(f"Error placing {side} order: {e}")
        return None

def get_current_balance(asset):
    try:
        balance = exchange.fetch_balance()
        return balance['free'][asset]
    except ccxt.BaseError as e:
        logger.error(f"Error fetching balance: {e}")
        return 0

def check_open_orders(symbol):
    try:
        open_orders = exchange.fetch_open_orders(symbol)
        return len(open_orders) > 0
    except ccxt.BaseError as e:
        logger.error(f"Error fetching open orders: {e}")
        return False

def cancel_all_orders(symbol):
    try:
        orders = exchange.fetch_open_orders(symbol)
        for order in orders:
            exchange.cancel_order(order['id'], symbol)
        logger.info(f"Cancelled all open orders for {symbol}")
    except ccxt.BaseError as e:
        logger.error(f"Error cancelling orders: {e}")

def trading_bot(symbol):
    balance = TRADE_AMOUNT
    symbol_balance = 0
    active_trade = None
    last_api_call_time = time.time()
    previous_market_condition = 'neutral'

    while True:
        time_since_last_call = time.time() - last_api_call_time
        if time_since_last_call < TRADE_INTERVAL_SECONDS:
            time.sleep(TRADE_INTERVAL_SECONDS - time_since_last_call)
        
        order_book = fetch_order_book(symbol)
        last_api_call_time = time.time()
        
        if order_book is None:
            logger.warning("Failed to fetch order book. Skipping this iteration.")
            continue

        analysis = analyze_order_book(order_book)
        if analysis is None:
            logger.warning("Failed to analyze order book. Skipping this iteration.")
            continue
        
        current_price = order_book['asks'][0][0]  # Current market price based on the first ask

        logger.info(f"Market condition: {analysis['market_condition']}")

        # Buy condition: market condition must change from bearish or neutral to bullish
        if previous_market_condition in ['neutral', 'bearish'] and analysis['market_condition'] == 'bullish':
            if active_trade is None and balance >= TRADE_AMOUNT:
                buy_price = analysis['best_ask_price']
                amount_to_buy = TRADE_AMOUNT / buy_price
                active_trade = place_order(symbol, 'buy', amount_to_buy, buy_price)
                logger.info(f"Placing buy order at best ask price: {buy_price:.8f}")
            elif active_trade and active_trade['side'] == 'sell':
                cancel_all_orders(symbol)
                active_trade = None

        previous_market_condition = analysis['market_condition']

        if active_trade and active_trade['side'] == 'buy':
            order = exchange.fetch_order(active_trade['id'], symbol)
            if order['status'] == 'closed':
                logger.info(f"BUY filled at {order['price']:.8f}")
                symbol_balance += order['amount']
                balance -= TRADE_AMOUNT
                
                # Determine the sell price for at least 0.44% profit
                min_sell_price = analysis['min_exit_price']
                # Find the highest possible sell price in the order book that meets the profit target
                for ask_price, ask_volume in order_book['asks']:
                    if ask_price > min_sell_price:
                        sell_price = ask_price
                        break
                else:
                    sell_price = min_sell_price
                
                asset = symbol.split('/')[0]
                symbol_balance = get_current_balance(asset)
                amount_to_sell = round(symbol_balance, 8)  # Round down to avoid over-selling
                
                active_trade = place_order(symbol, 'sell', amount_to_sell, sell_price)
                logger.info(f"Placing sell order at price: {sell_price:.8f}")

        elif active_trade and active_trade['side'] == 'sell':
            order = exchange.fetch_order(active_trade['id'], symbol)
            if order['status'] == 'closed':
                logger.info(f"SELL filled at {order['price']:.8f}")
                balance += order['amount'] * order['price']
                symbol_balance -= order['amount']
                active_trade = None  # Ready for the next trade cycle
            elif analysis['market_condition'] == 'bearish':
                cancel_all_orders(symbol)
                active_trade = None

        total_value = balance + symbol_balance * current_price

        logger.info(f"Current Balance: {balance:.2f} USDT, "
                    f"Symbol Balance: {symbol_balance:.8f}, "
                    f"Total Value: {total_value:.2f}, "
                    f"PNL: {total_value - TRADE_AMOUNT:.2f}")

def main():
    trading_bot(SYMBOL)

if __name__ == "__main__":
    main()
