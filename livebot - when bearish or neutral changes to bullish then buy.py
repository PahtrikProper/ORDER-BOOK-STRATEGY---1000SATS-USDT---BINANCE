import os
import ccxt
import time
import logging
from dotenv import load_dotenv
from math import floor

# Load environment variables
load_dotenv()

# Configurable Parameters
SYMBOL = '1000SATS/USDT'
ORDER_BOOK_DEPTH = 100  # Increased for more comprehensive analysis
TRADE_AMOUNT = 200  # Fixed amount in USDT to trade each time
TRADE_INTERVAL_SECONDS = 2
PROFIT_PERCENTAGE = 0.0044  # Minimum 0.44% profit target

# Order Book Analysis Parameters
VOLUME_IMBALANCE_THRESHOLD = 1.2  # 20% more volume on buy side than sell side
MAX_SYMBOL_BALANCE_USDT_EQUIV = 50  # Maximum symbol balance in USDT equivalent

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

# Load markets data
def load_markets_data():
    try:
        exchange.load_markets()
        return exchange.markets
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Exchange error: {e}")
    except ccxt.RateLimitExceeded as e:
        logger.error(f"Rate limit exceeded: {e}")
        time.sleep(60)
    return None

market_data = load_markets_data()

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
    asks = order_book['asks']
    bids = order_book['bids']
    
    if not asks or not bids:
        logger.warning("Not enough asks or bids in the order book for analysis.")
        return None
    
    # Best ask (lowest ask price) and best bid (highest bid price)
    best_ask_price, best_ask_volume = asks[0]
    best_bid_price, best_bid_volume = bids[0]
    
    # Calculate buy/sell volume imbalance
    total_bid_volume = sum(volume for price, volume in bids)
    total_ask_volume = sum(volume for price, volume in asks)
    volume_imbalance = total_bid_volume / total_ask_volume

    # Calculate ideal exit price based on profit percentage
    min_exit_price = best_ask_price * (1 + PROFIT_PERCENTAGE)
    
    # Determine market condition
    market_condition = 'neutral'
    if volume_imbalance > VOLUME_IMBALANCE_THRESHOLD:
        market_condition = 'bullish'
    elif volume_imbalance < 1 / VOLUME_IMBALANCE_THRESHOLD:
        market_condition = 'bearish'
    
    return {
        'best_ask_price': best_ask_price,
        'best_bid_price': best_bid_price,
        'min_exit_price': min_exit_price,
        'market_condition': market_condition
    }

def validate_order(symbol, side, price, amount):
    global market_data
    if market_data is None:
        market_data = load_markets_data()
        if market_data is None:
            return False

    market = market_data[symbol]

    # Minimum order size
    if amount < market['limits']['amount']['min']:
        logger.error(f"Order amount {amount} is less than minimum allowed {market['limits']['amount']['min']}.")
        return False

    # Price and quantity precision
    price_precision = market['precision']['price']
    amount_precision = market['precision']['amount']
    price = round(price, price_precision)
    amount = round(amount, amount_precision)

    # Lot size step (if available)
    lot_size_step = market['limits']['amount'].get('step')
    if lot_size_step and amount % lot_size_step != 0:
        logger.error(f"Order amount {amount} is not a multiple of lot size step {lot_size_step}.")
        return False

    # Notional value
    notional = price * amount
    if notional < market['limits']['cost']['min']:
        logger.error(f"Order notional {notional} is less than minimum allowed {market['limits']['cost']['min']}.")
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
            order = exchange.create_limit_buy_order(symbol, amount, price)
        else:
            order = exchange.create_limit_sell_order(symbol, amount, price)
        logger.info(f"Order placed: {order}")
        return order
    except ccxt.InsufficientFunds as e:
        logger.error(f"Insufficient funds: {e}")
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Exchange error: {e}")
    except ccxt.RateLimitExceeded as e:
        logger.error(f"Rate limit exceeded: {e}")
        time.sleep(60)
    return None

def update_order_status(order):
    try:
        order_info = exchange.fetch_order(order['id'], order['symbol'])
        order.update(order_info)
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Exchange error: {e}")
    except ccxt.RateLimitExceeded as e:
        logger.error(f"Rate limit exceeded: {e}")
        time.sleep(60)
    return order

def fetch_balances():
    try:
        balance_info = exchange.fetch_balance()
        usdt_balance = balance_info['total']['USDT']
        symbol_balance = balance_info['total'][SYMBOL.split('/')[0]]
        return usdt_balance, symbol_balance
    except ccxt.NetworkError as e:
        logger.error(f"Network error: {e}")
    except ccxt.ExchangeError as e:
        logger.error(f"Exchange error: {e}")
    except ccxt.RateLimitExceeded as e:
        logger.error(f"Rate limit exceeded: {e}")
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
    has_bought = False

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

        # Calculate symbol balance in USDT equivalent
        symbol_balance_usdt_equiv = symbol_balance * current_price

        if (previous_market_condition in ['neutral', 'bearish'] and 
            analysis['market_condition'] == 'bullish' and 
            symbol_balance_usdt_equiv < MAX_SYMBOL_BALANCE_USDT_EQUIV and not has_bought):
            # Bullish trend detected from neutral or bearish market condition
            if active_trade is None and balance >= TRADE_AMOUNT:
                buy_price = analysis['best_ask_price']
                amount_to_buy = TRADE_AMOUNT / buy_price
                active_trade = place_order(symbol, 'buy', buy_price, amount_to_buy)
                if active_trade is not None:
                    logger.info(f"Placing buy order at best ask price: {buy_price:.8f}")
                    balance -= buy_price * amount_to_buy
                    has_bought = True

        if active_trade and active_trade['side'] == 'buy':
            active_trade = update_order_status(active_trade)
            if active_trade['status'] == 'closed':
                logger.info(f"BUY filled at {active_trade['price']:.8f}")
                symbol_balance += active_trade['amount']
                
                # Wait 15 seconds before placing the sell order
                time.sleep(15)

                # Fetch the latest balances
                _, updated_symbol_balance = fetch_balances()

                # Round down symbol balance to two decimal places
                rounded_symbol_balance = floor(updated_symbol_balance * 100) / 100

                # Determine the sell price for at least 0.44% profit
                min_sell_price = analysis['min_exit_price']

                # Place a sell order at the target price
                sell_order = place_order(symbol, 'sell', min_sell_price, rounded_symbol_balance)
                if sell_order is not None:
                    logger.info(f"Placing sell order: {rounded_symbol_balance:.8f} {symbol} at {min_sell_price:.8f}")

        if active_trade and active_trade['side'] == 'sell':
            active_trade = update_order_status(active_trade)
            if active_trade['status'] == 'closed':
                # Fetch the latest balances before updating
                balance, symbol_balance = fetch_balances()
                logger.info(f"SELL filled at {active_trade['price']:.8f}")
                active_trade = None  # Ready for the next trade cycle
                has_bought = False  # Reset for the next buy condition

        total_value = balance + symbol_balance * current_price
        logger.info(f"Current Balance: {balance:.2f} USDT, "
                    f"Symbol Balance: {symbol_balance:.8f}, "
                    f"Total Value: {total_value:.2f}")

        previous_market_condition = analysis['market_condition']

def main():
    live_trading(SYMBOL)

if __name__ == "__main__":
    main()
