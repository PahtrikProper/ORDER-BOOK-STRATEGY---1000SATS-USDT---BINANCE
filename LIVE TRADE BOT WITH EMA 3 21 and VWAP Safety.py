# Detailed Description of the Script
# This script is designed to automate high-frequency cryptocurrency trading on the Binance exchange using the CCXT library. The main objective is to perform scalping trades by buying low and selling high based on specific market conditions and technical indicators. Here's a detailed description of what the script does:
#
# Imports and Environment Setup:
# The script imports necessary modules: os, ccxt, time, logging, load_dotenv from dotenv, and Decimal from decimal.
# It loads environment variables from a .env file to securely manage API keys and secrets.
#
# Configurable Parameters:
# SYMBOL: The trading pair (e.g., '1000SATS/USDT').
# ORDER_BOOK_DEPTH: The depth of the order book to fetch.
# TRADE_AMOUNT: The fixed amount in USDT to trade each time.
# TRADE_INTERVAL_SECONDS: The interval between trades, set to 1 second for high-frequency trading.
# PROFIT_PERCENTAGE: The minimum profit target set to 0.44%.
# TRADING_FEE_PERCENTAGE: The trading fee percentage, set to 0.1% as an example.
# LEFTOVER_THRESHOLD: The threshold to ignore small leftover balances, set to 10 units of the symbol.
#
# EMA Parameters:
# EMA_SHORT_PERIOD: The short period for calculating the Exponential Moving Average (EMA), set to 3.
# EMA_LONG_PERIOD: The long period for calculating the EMA, set to 21.
#
# Order Book Analysis Parameters:
# VOLUME_IMBALANCE_THRESHOLD: The threshold for volume imbalance, set to 1.2 (20% more volume on the buy side than the sell side).
# MAX_SYMBOL_BALANCE_USDT_EQUIV: The maximum symbol balance in USDT equivalent, set to 50 USDT.
#
# Rate Limiting Parameters:
# MAX_REQUESTS_PER_MINUTE: The maximum number of requests allowed per minute, set to 1200.
# RATE_LIMIT_SAFETY_FACTOR: A safety factor for rate limiting, set to 0.75.
#
# Logging Setup:
# Configures logging to output messages with a specific format including timestamp, log level, and message content.
# Creates a logger instance for logging information, warnings, and errors.
#
# Binance API Initialization:
# Initializes the Binance exchange API with API key and secret loaded from the environment variables.
# Enables rate limiting to prevent exceeding the exchange's API request limits.
#
# Summary of Script Functionality
# Fetches Market Data: Loads market data and order books for the specified trading pair.
# Fetches Historical Data: Retrieves historical price data to calculate technical indicators.
# Calculates EMAs: Computes the 3-period and 21-period Exponential Moving Averages to identify trends.
# Analyzes Order Book: Determines market conditions based on order book data and volume imbalances.
# Executes Trades: Places buy and sell orders based on specified conditions, including market trend and EMA crossover.
# Manages Balances: Fetches and checks account balances to ensure sufficient funds for trading and ignores small leftover balances.
# Logs Activity: Logs detailed information about market conditions, order statuses, and account balances to help monitor and debug the trading bot's activity.






import os
import ccxt
import time
import logging
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN

# Load environment variables
load_dotenv()

# Configurable Parameters
SYMBOL = '1000SATS/USDT'
ORDER_BOOK_DEPTH = 100
TRADE_AMOUNT = Decimal('200')  # Fixed amount in USDT to trade each time
TRADE_INTERVAL_SECONDS = 1  # Reduced interval for higher frequency
PROFIT_PERCENTAGE = Decimal('0.0044')  # Minimum 0.44% profit target
TRADING_FEE_PERCENTAGE = Decimal('0.001')  # Example trading fee (0.1%)
LEFTOVER_THRESHOLD = Decimal('10')  # Threshold to ignore small leftover balances

# EMA Parameters
EMA_SHORT_PERIOD = 3
EMA_LONG_PERIOD = 21

# Order Book Analysis Parameters
VOLUME_IMBALANCE_THRESHOLD = Decimal('1.2')  # 20% more volume on buy side than sell side
MAX_SYMBOL_BALANCE_USDT_EQUIV = Decimal('50')  # Maximum symbol balance in USDT equivalent

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

def load_markets_data():
    try:
        exchange.load_markets()
        return exchange.markets
    except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
        logger.error(f"Error loading markets: {e}")
        time.sleep(60)
    return None

market_data = load_markets_data()

def fetch_order_book(symbol, limit=ORDER_BOOK_DEPTH):
    try:
        return exchange.fetch_order_book(symbol, limit=limit)
    except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
        logger.error(f"Error fetching order book: {e}")
        time.sleep(60)
    return None

def fetch_ohlcv(symbol, timeframe='1m', limit=30):
    try:
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
        logger.error(f"Error fetching OHLCV data: {e}")
        time.sleep(60)
    return None

def calculate_ema(prices, period):
    ema = []
    k = 2 / (period + 1)
    ema.append(prices[0])
    for price in prices[1:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

def calculate_vwap(order_book):
    bids = order_book['bids']
    asks = order_book['asks']
    
    bid_vwap = sum(Decimal(price) * Decimal(volume) for price, volume in bids) / sum(Decimal(volume) for _, volume in bids)
    ask_vwap = sum(Decimal(price) * Decimal(volume) for price, volume in asks) / sum(Decimal(volume) for _, volume in asks)
    
    return bid_vwap, ask_vwap

def analyze_order_book(order_book):
    asks = order_book['asks']
    bids = order_book['bids']
    
    if len(bids) < 6 or len(asks) < 6:
        logger.warning("Not enough bid/ask levels in the order book for analysis.")
        return None

    best_ask_price = Decimal(str(asks[0][0]))
    dynamic_bid_price = Decimal(str(bids[min(5, len(bids) - 1)][0]))  # Dynamically select bid price

    bid_vwap, ask_vwap = calculate_vwap(order_book)
    
    total_bid_volume = sum(Decimal(str(volume)) for _, volume in bids)
    total_ask_volume = sum(Decimal(str(volume)) for _, volume in asks)
    volume_imbalance = total_bid_volume / total_ask_volume

    min_exit_price = dynamic_bid_price * (1 + PROFIT_PERCENTAGE)
    
    market_condition = 'neutral'
    if volume_imbalance > VOLUME_IMBALANCE_THRESHOLD:
        market_condition = 'bullish'
    elif volume_imbalance < 1 / VOLUME_IMBALANCE_THRESHOLD:
        market_condition = 'bearish'
    
    return {
        'best_ask_price': best_ask_price,
        'dynamic_bid_price': dynamic_bid_price,
        'min_exit_price': min_exit_price,
        'market_condition': market_condition,
        'bid_vwap': bid_vwap,
        'ask_vwap': ask_vwap
    }

def validate_order(symbol, side, price, amount):
    global market_data
    if market_data is None:
        market_data = load_markets_data()
        if market_data is None:
            return False

    market = market_data[symbol]

    min_amount = Decimal(str(market['limits']['amount']['min']))
    if amount < min_amount:
        logger.error(f"Order amount {amount} is less than minimum allowed {min_amount}.")
        return False

    price_precision = market['precision']['price']
    amount_precision = market['precision']['amount']
    price = Decimal(str(price)).quantize(Decimal(f'1e-{price_precision}'), rounding=ROUND_DOWN)
    amount = Decimal(str(amount)).quantize(Decimal(f'1e-{amount_precision}'), rounding=ROUND_DOWN)

    lot_size_step = market['limits']['amount'].get('step')
    if lot_size_step:
        lot_size_step = Decimal(str(lot_size_step))
        if amount % lot_size_step != 0:
            amount = (amount // lot_size_step) * lot_size_step

    notional = price * amount
    min_notional = Decimal(str(market['limits']['cost']['min']))
    if notional < min_notional:
        logger.error(f"Order notional {notional} is less than minimum allowed {min_notional}.")
        return False

    return price, amount

def place_order(symbol, side, price, amount):
    logger.info(f"Placing {side} order: {amount:.8f} {symbol} at {price:.8f}")
    validation = validate_order(symbol, side, price, amount)
    if not validation:
        return None
    price, amount = validation
    try:
        if side == 'buy':
            order = exchange.create_limit_buy_order(symbol, float(amount), float(price))
        else:
            order = exchange.create_limit_sell_order(symbol, float(amount), float(price))
        logger.info(f"Order placed: {order}")
        return order
    except (ccxt.InsufficientFunds, ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
        logger.error(f"Error placing order: {e}")
        if isinstance(e, ccxt.RateLimitExceeded):
            time.sleep(60)
    return None

def update_order_status(order):
    try:
        order_info = exchange.fetch_order(order['id'], order['symbol'])
        order.update(order_info)
    except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
        logger.error(f"Error updating order status: {e}")
        if isinstance(e, ccxt.RateLimitExceeded):
            time.sleep(60)
    return order

def fetch_balances():
    try:
        balance_info = exchange.fetch_balance()
        usdt_balance = Decimal(str(balance_info['total']['USDT']))
        symbol_balance = Decimal(str(balance_info['total'][SYMBOL.split('/')[0]]))
        return usdt_balance, symbol_balance
    except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
        logger.error(f"Error fetching balances: {e}")
        if isinstance(e, ccxt.RateLimitExceeded):
            time.sleep(60)
    return None, None

def live_trading(symbol):
    balance, symbol_balance = fetch_balances()
    if balance is None or symbol_balance is None:
        logger.error("Failed to fetch initial balances. Exiting.")
        return

    active_trade = None
    last_api_call_time = time.time()
    previous_market_condition = 'neutral'

    while True:
        time_since_last_call = time.time() - last_api_call_time
        if time_since_last_call < TRADE_INTERVAL_SECONDS:
            time.sleep(TRADE_INTERVAL_SECONDS - time_since_last_call)
        
        order_book = fetch_order_book(symbol)
        ohlcv = fetch_ohlcv(symbol)
        last_api_call_time = time.time()
        
        if order_book is None or ohlcv is None:
            logger.warning("Failed to fetch order book or OHLCV data. Skipping this iteration.")
            continue

        analysis = analyze_order_book(order_book)
        if analysis is None:
            logger.warning("Failed to analyze order book. Skipping this iteration.")
            continue

        closes = [ohlc[4] for ohlc in ohlcv]
        ema_short = calculate_ema(closes, EMA_SHORT_PERIOD)
        ema_long = calculate_ema(closes, EMA_LONG_PERIOD)

        current_price = Decimal(str(order_book['asks'][0][0]))

        logger.info(f"Market condition: {analysis['market_condition']}, EMA Short: {ema_short[-1]}, EMA Long: {ema_long[-1]}")

        symbol_balance_usdt_equiv = symbol_balance * current_price

        if (previous_market_condition in ['neutral', 'bearish'] and 
            analysis['market_condition'] == 'bullish' and 
            ema_short[-1] > ema_long[-1] and
            symbol_balance_usdt_equiv < MAX_SYMBOL_BALANCE_USDT_EQUIV):
            if active_trade is None and balance >= TRADE_AMOUNT:
                buy_price = analysis['dynamic_bid_price']
                amount_to_buy = TRADE_AMOUNT / buy_price
                amount_to_buy_with_fee = amount_to_buy * (1 - TRADING_FEE_PERCENTAGE)
                active_trade = place_order(symbol, 'buy', buy_price, amount_to_buy_with_fee)
                if active_trade is not None:
                    logger.info(f"Placing buy order at dynamic bid price: {buy_price:.8f}")
                    balance -= buy_price * amount_to_buy

        if active_trade and active_trade['side'] == 'buy':
            active_trade = update_order_status(active_trade)
            if active_trade['status'] == 'closed':
                logger.info(f"BUY filled at {active_trade['price']:.8f}")
                symbol_balance += Decimal(str(active_trade['amount']))
                
                min_sell_price = analysis['min_exit_price']
                amount_to_sell = Decimal(str(active_trade['amount'])) * (1 - TRADING_FEE_PERCENTAGE)
                
                usdt_balance, symbol_balance = fetch_balances()
                if symbol_balance >= amount_to_sell:
                    active_trade = place_order(symbol, 'sell', min_sell_price, amount_to_sell)
                    if active_trade is not None:
                        logger.info(f"Placing sell order at price: {min_sell_price:.8f}")
                        symbol_balance -= amount_to_sell
                    else:
                        logger.error("Failed to place sell order.")
                else:
                    logger.error("Insufficient balance to place sell order.")
            elif active_trade['status'] != 'open':
                logger.error(f"Unexpected buy order status: {active_trade['status']}")

        elif active_trade and active_trade['side'] == 'sell':
            active_trade = update_order_status(active_trade)
            if active_trade['status'] == 'closed':
                logger.info(f"SELL filled at {active_trade['price']:.8f}")
                balance += Decimal(str(active_trade['amount'])) * Decimal(str(active_trade['price']))
                active_trade = None
            elif active_trade['status'] != 'open':
                logger.error(f"Unexpected sell order status: {active_trade['status']}")

        total_value = balance + symbol_balance * current_price
        logger.info(f"Current Balance: {balance:.2f} USDT, "
                    f"Symbol Balance: {symbol_balance:.8f}, "
                    f"Total Value: {total_value:.2f}")

        previous_market_condition = analysis['market_condition']

def main():
    while True:
        try:
            live_trading(SYMBOL)
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
