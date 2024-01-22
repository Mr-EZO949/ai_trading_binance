import talib
import yfinance as yf
def consensus_trend_following_strategy(data, sma_short_window=50, sma_long_window=200, macd_fast=12, macd_slow=26, macd_signal=9, adx_window=14, adx_threshold=25):
    """
    Trend-Following Strategy based on a consensus of at least two out of three indicators: SMA, MACD, and ADX.

    Parameters:
    data (DataFrame): Historical market data with 'Close', 'High', 'Low' price columns.
    sma_short_window, sma_long_window: Parameters for SMA.
    macd_fast, macd_slow, macd_signal: Parameters for MACD.
    adx_window: Window length for ADX.
    adx_threshold: Threshold to determine strong trend in ADX.

    Returns:
    str: 'buy', 'sell', or 'hold' signal.
    """

    # SMA Signal
    sma_short = data['Close'].rolling(window=sma_short_window, min_periods=1).mean()
    sma_long = data['Close'].rolling(window=sma_long_window, min_periods=1).mean()
    sma_signal = 'buy' if sma_short.iloc[-1] > sma_long.iloc[-1] else 'sell'

    # MACD Signal
    macd, macdsignal, _ = talib.MACD(data['Close'], fastperiod=macd_fast, slowperiod=macd_slow, signalperiod=macd_signal)
    macd_signal = 'buy' if macd.iloc[-1] > macdsignal.iloc[-1] else 'sell'

    # ADX Signal
    adx = talib.ADX(data['High'], data['Low'], data['Close'], timeperiod=adx_window)
    adx_signal = 'buy' if adx.iloc[-1] > adx_threshold else 'sell'

    # Count consensus
    signals = [sma_signal, macd_signal, adx_signal]
    buy_signals = signals.count('buy')
    sell_signals = signals.count('sell')

    # Generate trading signal based on consensus
    if buy_signals >= 2:
        return 'buy'
    elif sell_signals >= 2:
        return 'sell'
    else:
        return 'hold'
