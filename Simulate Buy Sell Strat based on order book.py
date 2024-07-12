import os
import ccxt
import numpy as np
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configurable Parameters
SYMBOL = '1000SATS/USDT'
ORDER_BOOK_DEPTH = 100  # Increased for more comprehensive analysis
INITIAL_BALANCE = 100  # Starting balance in USDT
TRADE_AMOUNT = 100  # Fixed amount in USDT to trade each time
TRADE_INTERVAL_SECONDS = 2
PROFIT_PERCENTAGE = 0.0044  # Minimum 0.44% profit target

# Order Book Analysis Parameters
VOLUME_IMBALANCE_THRESHOLD = 1.2  # 20% more volume on buy side than sell side

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

def place_order(symbol, side, price, amount):
    logger.info(f"Placing {side} order: {amount:.8f} {symbol} at {price:.8f}")
    # In a real implementation, you would call the exchange's API here
    return {
        'symbol': symbol,
        'side': side,
        'price': price,
        'amount': amount,
        'filled': 0,
        'status': 'open'
    }

def update_order_status(order, current_price):
    if order['status'] == 'open':
        if (order['side'] == 'buy' and current_price <= order['price']) or \
           (order['side'] == 'sell' and current_price >= order['price']):
            order['filled'] = order['amount']
            order['status'] = 'filled'
    return order

def simulate_trading(symbol):
    balance = INITIAL_BALANCE
    symbol_balance = 0
    pnl = []
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

        if (previous_market_condition in ['neutral', 'bearish'] and 
            analysis['market_condition'] == 'bullish'):
            # Bullish trend detected from neutral or bearish market condition
            if active_trade is None and balance >= TRADE_AMOUNT:
                buy_price = analysis['best_ask_price']
                amount_to_buy = TRADE_AMOUNT / buy_price
                active_trade = place_order(symbol, 'buy', buy_price, amount_to_buy)
                logger.info(f"Placing buy order at best ask price: {buy_price:.8f}")

        previous_market_condition = analysis['market_condition']

        if active_trade and active_trade['side'] == 'buy':
            active_trade = update_order_status(active_trade, current_price)
            if active_trade['status'] == 'filled':
                logger.info(f"BUY filled at {active_trade['price']:.8f}")
                symbol_balance += active_trade['amount']
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

                active_trade = place_order(symbol, 'sell', sell_price, active_trade['amount'])
                logger.info(f"Placing sell order at price: {sell_price:.8f}")

        elif active_trade and active_trade['side'] == 'sell':
            active_trade = update_order_status(active_trade, current_price)
            if active_trade['status'] == 'filled':
                logger.info(f"SELL filled at {active_trade['price']:.8f}")
                balance += active_trade['amount'] * active_trade['price']
                symbol_balance -= active_trade['amount']
                active_trade = None  # Ready for the next trade cycle

        total_value = balance + symbol_balance * current_price
        pnl.append(total_value)

        logger.info(f"Current Balance: {balance:.2f} USDT, "
                    f"Symbol Balance: {symbol_balance:.8f}, "
                    f"Total Value: {total_value:.2f}, "
                    f"PNL: {total_value - INITIAL_BALANCE:.2f}")

        yield pnl, balance, symbol_balance, total_value

def main():
    trading_data = simulate_trading(SYMBOL)
    for _ in trading_data:
        pass  # The logging is done inside the simulate_trading function

if __name__ == "__main__":
    main()
