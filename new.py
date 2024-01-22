import pandas as pd
import talib
from datetime import datetime, timedelta
from binance.client import Client
import decimal
import time

# Binance API credentials
api_key = 'j4gwCqHcT21zyuaJ6TcA0K82Fs0FV3upcxMUoVchyzAexoBQAgDJc4I7ARXLEbDs'
api_secret = 'CWdH5pTVzT8PfLvGyZiqFqUHZ2KtmxLeph5EhV3QHi7Y6JB6erJWU0r5INlJwBHN'

# Initialize Binance client
client = Client(api_key, api_secret, testnet=True)

def get_balance(client, asset):
    """ Get the available balance for a specified asset """
    balance = client.get_asset_balance(asset=asset)
    return float(balance['free'])


def calculate_trade_amount(client, asset, risk_percentage):
    """
    Calculate the amount to trade based on the balance and risk percentage.
    """
    balance = get_balance(client, asset)
    trade_amount = balance * risk_percentage / 100
    return trade_amount


def execute_trade(client, symbol, side, trade_amount):
    """
    Execute a trade on Binance.
    """
    # Convert trade amount to the correct format
    trade_amount = decimal.Decimal(str(trade_amount)).quantize(decimal.Decimal('1.00000000'))

    try:
        if side.lower() == 'buy':
            order = client.order_market_buy(symbol=symbol, quantity=trade_amount)
        elif side.lower() == 'sell':
            order = client.order_market_sell(symbol=symbol, quantity=trade_amount)
        else:
            raise ValueError("Trade side must be 'buy' or 'sell'")

        return order
    except Exception as e:
        print(f"An error occurred: {e}")
        return None


def fetch_binance_data(symbol, interval='1m', lookback='1 day'):
    """ Fetch historical data from Binance """
    klines = client.get_historical_klines(symbol, interval, lookback)
    # Convert the klines to a DataFrame
    data = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
    data['timestamp'] = pd.to_datetime(data['timestamp'], unit='ms')
    data.set_index('timestamp', inplace=True)
    # Convert columns to appropriate data types
    for col in ['open', 'high', 'low', 'close', 'volume']:
        data[col] = pd.to_numeric(data[col])
    return data

def identify_market_condition(data, adx_window=14, bbands_window=20, smoothing_window=5):
    """
    Analyze the market condition based on historical data and classify it into categories.

    Parameters:
    data (DataFrame): Historical market data (OHLCV - Open, High, Low, Close, Volume).
    adx_window (int): Number of periods for calculating ADX.
    bbands_window (int): Number of periods for calculating Bollinger Bands.
    smoothing_window (int): Number of periods for smoothing the indicators.

    Returns:
    str: Market condition categorized as 'trending', 'sideways', or 'volatile'.
    """

    # Constants for thresholds
    ADX_THRESHOLD = 25
    BBANDS_WIDTH_THRESHOLD = 2.0  # Example value, adjust based on asset and strategy

    # Calculate ADX
    adx = talib.ADX(data['High'], data['Low'], data['Close'], timeperiod=adx_window)

    # Calculate Bollinger Bands
    upperband, middleband, lowerband = talib.BBANDS(data['Close'], timeperiod=bbands_window, nbdevup=2, nbdevdn=2, matype=0)
    bbands_width = (upperband - lowerband) / middleband

    # Smooth the indicators using a simple moving average
    smoothed_adx = adx.rolling(window=smoothing_window).mean()
    smoothed_bbands_width = bbands_width.rolling(window=smoothing_window).mean()

    # Latest values of smoothed indicators
    latest_adx = smoothed_adx.iloc[-1]
    latest_bbands_width = smoothed_bbands_width.iloc[-1]

    # Determine market condition based on ADX and Bollinger Bands width
    if latest_adx > ADX_THRESHOLD and latest_bbands_width > BBANDS_WIDTH_THRESHOLD:
        return 'trending and volatile'
    elif latest_adx > ADX_THRESHOLD:
        return 'trending'
    elif latest_bbands_width > BBANDS_WIDTH_THRESHOLD:
        return 'volatile'
    else:
        return 'sideways'

def select_strategy_based_on_condition(market_condition):
    """
    Select the trading strategy based on the market condition.
    Returns a function that represents the selected trading strategy.
    """
    if market_condition == 'trending':
        return hybrid_trend_following_strategy  # Your existing SMA strategy function
    elif market_condition == 'sideways':
        return sideways_market_strategy  # Implement mean reversion logic
    elif market_condition == 'volatile':
        return volatile_market_strategy  # Implement a strategy for volatile markets
    else:
        return default_strategy  # A default strategy


def sideways_market_strategy(data, bbands_period=20, rsi_period=14, stochastic_period=14, stochastic_slowk=3, stochastic_slowd=3):
    """
    Strategy for sideways markets using Bollinger Bands, RSI, and Stochastic Oscillator.

    Parameters:
    data (DataFrame): Historical market data with 'Close' price columns.
    bbands_period (int): Number of periods for Bollinger Bands.
    rsi_period (int): Number of periods for RSI.
    stochastic_period (int): Number of periods for Stochastic Oscillator.
    stochastic_slowk (int): Slowing period for %K in Stochastic Oscillator.
    stochastic_slowd (int): Slowing period for %D in Stochastic Oscillator.

    Returns:
    str: 'buy', 'sell', or 'hold' signal.
    """

    # Calculate Bollinger Bands, RSI, and Stochastic Oscillator
    upperband, middleband, lowerband = talib.BBANDS(data['Close'], timeperiod=bbands_period, nbdevup=2, nbdevdn=2, matype=0)
    rsi = talib.RSI(data['Close'], timeperiod=rsi_period)
    slowk, slowd = talib.STOCH(data['High'], data['Low'], data['Close'], fastk_period=stochastic_period, slowk_period=stochastic_slowk, slowk_matype=0, slowd_period=stochastic_slowd, slowd_matype=0)

    # Define thresholds for overbought/oversold conditions
    rsi_overbought, rsi_oversold = 70, 30
    stochastic_overbought, stochastic_oversold = 80, 20

    # Trading logic
    if (data['Close'].iloc[-1] < lowerband.iloc[-1]) or (rsi.iloc[-1] < rsi_oversold) or (slowk.iloc[-1] < stochastic_oversold and slowk.iloc[-1] > slowd.iloc[-1]):
        return 'buy'
    elif (data['Close'].iloc[-1] > upperband.iloc[-1]) or (rsi.iloc[-1] > rsi_overbought) or (slowk.iloc[-1] > stochastic_overbought and slowk.iloc[-1] < slowd.iloc[-1]):
        return 'sell'
    else:
        return 'hold'


# For when the market is trending
def hybrid_trend_following_strategy(data, sma_short_window=50, sma_long_window=200, macd_fast=12, macd_slow=26,
                                    macd_signal=9, adx_window=14, adx_threshold=25, atr_window=14,
                                    volatility_threshold=1.0):
    """
    Hybrid Trend-Following Strategy based on market volatility.

    Parameters:
    data (DataFrame): Historical market data with 'Close', 'High', 'Low' price columns.
    [SMA, MACD, ADX parameters]
    atr_window (int): Window length for ATR to measure volatility.
    volatility_threshold (float): Threshold to switch between '3 out of 3' and '2 out of 3' rules.

    Returns:
    str: 'buy', 'sell', or 'hold' signal.
    """

    # Calculate indicators
    sma_short = data['Close'].rolling(window=sma_short_window, min_periods=1).mean()
    sma_long = data['Close'].rolling(window=sma_long_window, min_periods=1).mean()
    macd, macdsignal, _ = talib.MACD(data['Close'], fastperiod=macd_fast, slowperiod=macd_slow,
                                     signalperiod=macd_signal)
    adx = talib.ADX(data['High'], data['Low'], data['Close'], timeperiod=adx_window)
    atr = talib.ATR(data['High'], data['Low'], data['Close'], timeperiod=atr_window)

    # Determine signals
    sma_signal = 'buy' if sma_short.iloc[-1] > sma_long.iloc[-1] else 'sell'
    macd_signal = 'buy' if macd.iloc[-1] > macdsignal.iloc[-1] else 'sell'
    adx_signal = 'buy' if adx.iloc[-1] > adx_threshold else 'sell'

    # Assess market volatility
    current_volatility = atr.iloc[-1]
    is_volatile = current_volatility > volatility_threshold

    # Hybrid approach: 3 out of 3 in less volatile markets, 2 out of 3 in volatile markets
    signals = [sma_signal, macd_signal, adx_signal]
    buy_signals = signals.count('buy')
    sell_signals = signals.count('sell')

    if is_volatile:
        # 2 out of 3 rule
        if buy_signals >= 2:
            return 'buy'
        elif sell_signals >= 2:
            return 'sell'
        else:
            return 'hold'
    else:
        # 3 out of 3 rule
        if buy_signals == 3:
            return 'buy'
        elif sell_signals == 3:
            return 'sell'
        else:
            return 'hold'


# For when the market is volatile
def volatile_market_strategy(data, atr_period=14, bbands_period=20, bbands_std_dev=2, rsi_period=14, rsi_overbought=70, rsi_oversold=30, atr_multiplier=1.5):
    """
    Strategy for volatile markets using ATR, Bollinger Bands, and RSI.

    Parameters:
    data (DataFrame): Historical market data with 'Close', 'High', 'Low' price columns.
    atr_period (int): Number of periods for ATR.
    bbands_period (int): Number of periods for Bollinger Bands.
    bbands_std_dev (int): Standard deviation for Bollinger Bands.
    rsi_period (int): Number of periods for RSI.
    rsi_overbought (int): RSI level for overbought condition.
    rsi_oversold (int): RSI level for oversold condition.
    atr_multiplier (float): Multiplier for ATR to set stop-loss level.

    Returns:
    dict: Contains 'action' (str: 'buy', 'sell', or 'hold') and 'stop_loss' (float) levels.
    """

    # Calculate ATR, Bollinger Bands, and RSI
    atr = talib.ATR(data['High'], data['Low'], data['Close'], timeperiod=atr_period)
    upperband, middleband, lowerband = talib.BBANDS(data['Close'], timeperiod=bbands_period, nbdevup=bbands_std_dev, nbdevdn=bbands_std_dev, matype=0)
    rsi = talib.RSI(data['Close'], timeperiod=rsi_period)

    # Trading signals based on indicators
    is_overbought = rsi.iloc[-1] > rsi_overbought
    is_oversold = rsi.iloc[-1] < rsi_oversold
    price_above_upper_band = data['Close'].iloc[-1] > upperband.iloc[-1]
    price_below_lower_band = data['Close'].iloc[-1] < lowerband.iloc[-1]

    # Calculate stop-loss level based on ATR
    current_atr = atr.iloc[-1]
    stop_loss = None

    # Strategy logic with ATR for stop-loss calculation
    if is_oversold and price_below_lower_band:
        # Potential buy signal in volatile market
        stop_loss = data['Close'].iloc[-1] - atr_multiplier * current_atr
        return {'action': 'buy', 'stop_loss': stop_loss}
    elif is_overbought and price_above_upper_band:
        # Potential sell signal in volatile market
        stop_loss = data['Close'].iloc[-1] + atr_multiplier * current_atr
        return {'action': 'sell', 'stop_loss': stop_loss}
    else:
        return {'action': 'hold', 'stop_loss': stop_loss}


def default_strategy(data, macd_fast=12, macd_slow=26, macd_signal=9, rsi_period=14, rsi_overbought=70, rsi_oversold=30, sar_step=0.02, sar_maximum=0.2):
    """
    Default trading strategy with a passive approach, using MACD, RSI, and Parabolic SAR.
    Trades are executed only when there is a strong consensus among the indicators.

    Parameters:
    data (DataFrame): Historical market data with 'Close', 'High', 'Low' price columns.
    [MACD, RSI, SAR parameters]

    Returns:
    str: 'buy', 'sell', or 'hold' signal.
    """

    # Calculate MACD, RSI, and Parabolic SAR
    macd, macdsignal, _ = talib.MACD(data['Close'], fastperiod=macd_fast, slowperiod=macd_slow, signalperiod=macd_signal)
    rsi = talib.RSI(data['Close'], timeperiod=rsi_period)
    sar = talib.SAR(data['High'], data['Low'], acceleration=sar_step, maximum=sar_maximum)

    # Trading logic with strong consensus requirement
    last_price = data['Close'].iloc[-1]
    macd_cross_up = macd.iloc[-1] > macdsignal.iloc[-1]
    macd_cross_down = macd.iloc[-1] < macdsignal.iloc[-1]
    rsi_oversold = rsi.iloc[-1] < rsi_oversold
    rsi_overbought = rsi.iloc[-1] > rsi_overbought
    price_above_sar = last_price > sar.iloc[-1]
    price_below_sar = last_price < sar.iloc[-1]

    if macd_cross_up and rsi_oversold and price_above_sar:
        # Strong buy signal when all indicators agree
        return 'buy'
    elif macd_cross_down and rsi_overbought and price_below_sar:
        # Strong sell signal when all indicators agree
        return 'sell'
    else:
        return 'hold'


def main_trading_loop(symbol, interval='1m', risk_percentage=5, sleep_time=60):
    while True:
        try:
            # Fetch real-time data from Binance
            data = fetch_binance_data(client, symbol, interval=interval)

            # Identify market condition
            market_condition = identify_market_condition(data)
            print(f"Market condition for {symbol}: {market_condition}")

            # Select trading strategy based on market condition
            trading_strategy = select_strategy_based_on_condition(market_condition)

            # Get trading signal (buy, sell, hold)
            trading_action = trading_strategy(data)

            if trading_action in ['buy', 'sell']:
                # Calculate trade amount
                trade_amount = calculate_trade_amount(client, 'USDT', risk_percentage)
                print(f"Executing {trading_action} for {trade_amount} USDT")

                # Execute trade
                order_result = execute_trade(client, symbol, trading_action, trade_amount)
                print(order_result)
            else:
                print("Holding position")

        except Exception as e:
            print(f"An error occurred: {e}")

        # Sleep for a while before fetching new data
        time.sleep(sleep_time)

# Example usage
symbol = 'BTCUSDT'
main_trading_loop(symbol)