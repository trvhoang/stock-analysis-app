# technical_analysis.py
# Centralized handler for technical indicators and trend classification.

import pandas as pd
from sqlalchemy import text
import pandas_ta as ta
import numpy as np

def fetch_data(ticker, timeframe, limit, engine):
    """
    Fetches historical stock data for the given ticker.
    
    Args:
        ticker (str): The stock symbol.
        timeframe (str): 'Day', 'Week', or 'Month'.
        limit (int): The number of data points to retrieve (lookback period).
        engine: SQLAlchemy engine.
        
    Returns:
        pd.DataFrame: DataFrame containing OHLCV data, sorted by date ascending.
    """
    # Adjust the database limit to fetch enough daily data for resampling
    # Use generous multipliers to account for non-trading days
    db_limit = limit
    if timeframe == 'Week':
        db_limit = limit * 8 
    elif timeframe == 'Month':
        db_limit = limit * 32

    # Use raw DBAPI query syntax (%(name)s) instead of SQLAlchemy syntax (:name)
    # This allows us to use the raw connection and bypass pandas' SQLAlchemy detection issues
    query = """
        SELECT date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker = %(ticker)s
        ORDER BY date DESC
        LIMIT %(limit)s
    """
    
    # Fetch daily data
    # Use a raw connection to bypass pandas/sqlalchemy detection issues
    # engine.raw_connection() returns a raw psycopg2 connection which has .cursor()
    conn = engine.raw_connection()
    try:
        df = pd.read_sql(query, conn, params={"ticker": ticker, "limit": db_limit})
    finally:
        conn.close()

    if df.empty:
        return pd.DataFrame()

    # Convert date column to datetime objects for resampling
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').set_index('date')

    # Resample data for Week/Month timeframes
    if timeframe in ['Week', 'Month']:
        resample_period = 'W' if timeframe == 'Week' else 'ME'
        
        # Define aggregation rules
        agg_rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        
        df = df.resample(resample_period).agg(agg_rules)
        
        # As requested, remove any resampled periods that had no trading days
        df.dropna(inplace=True)

    # Ensure the final dataframe has the requested number of rows and reset index
    df = df.tail(limit).reset_index()

    return df

def calculate_stochastic(df):
   """
    Calculates Stochastic Oscillator (%K and %D).

    Args:
        df (pd.DataFrame): DataFrame containing OHLCV data.

    Returns:
        pd.DataFrame: DataFrame with added '%K' and '%D' columns.
    """
   try:
       # Calculate %K
       lowest_low = df['low'].rolling(window=10).min()
       highest_high = df['high'].rolling(window=10).max()
       df['%K'] = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))

       # Smooth %K to get the smoothed %K value
       df['%K'] = df['%K'].rolling(window=3).mean()

       # Calculate %D (Simple Moving Average of %K)
       df['%D'] = df['%K'].rolling(window=3).mean()

       trend = calculate_stochastic_trend(df, k_col='%K', d_col='%D')
       return df, trend

   except Exception as e:

       print(f"Error calculating Stochastic Oscillator: {e}")

       return df, "Unknown"

       return df



def calculate_rsi_trend(df, rsi_col='RSI_14'):
    """
    Determines the current trend of the RSI indicator based on historical behavior.
    
    Logic:
    - Scope: Scans up to 30 recent candles.
    - Up (Bullish): RSI 40-80, support 40-50, hits >70, rising momentum.
    - Down (Bearish): RSI 20-60, resistance 50-60, hits <30, falling momentum.
    - Sideways: >70% time in 40-60, OR swing < 20 pts, OR frequent 50-crosses.
    
    Args:
        df (pd.DataFrame): DataFrame containing the RSI column.
        rsi_col (str): Name of the RSI column.
        
    Returns:
        str: "Up", "Down", "Sideways", or "Unknown".
    """
    if rsi_col not in df.columns or df.empty:
        return "Unknown"

    # 1. Define Lookback Window (max 30 candles)
    lookback = 30
    if len(df) < lookback:
        recent_df = df.copy()
    else:
        recent_df = df.tail(lookback).copy()
    
    rsi_series = recent_df[rsi_col]
    current_rsi = rsi_series.iloc[-1]
    
    # Safety check for NaN at the end
    if pd.isna(current_rsi):
        return "Unknown"

    # 2. Check Sideways Conditions (Revised Rules)
    # Condition A: >70% of time between 40 and 55
    in_neutral_zone = rsi_series.between(40, 55).sum()
    neutral_ratio = in_neutral_zone / len(rsi_series)
    
    # Condition B: Narrow Oscillation (High - Low <= 15) over last 20 bars
    swing_window = 20
    if len(rsi_series) >= swing_window:
        swing_series = rsi_series.tail(swing_window)
        swing_range = swing_series.max() - swing_series.min()
    else:
        # If not enough data for swing check, default to a high range so we don't accidentally trigger it
        swing_range = 100 
        
    if neutral_ratio > 0.70 or swing_range <= 15:
        return "Sideways"

    # 3. Check Directional Trends (Revised Rules)
    # Need at least 3 points to check 2 consecutive moves (t, t-1, t-2)
    # We use tail(3) to check the sequence
    if len(rsi_series) >= 3:
        last_3 = rsi_series.tail(3).values
        # Check 2 consecutive rising: val[1]>val[0], val[2]>val[1]
        is_2_rising = (last_3[1] > last_3[0]) and (last_3[2] > last_3[1])
        # Check 2 consecutive falling
        is_2_falling = (last_3[1] < last_3[0]) and (last_3[2] < last_3[1])
    else:
        # Fallback for very short history: simple comparison of last 2
        is_2_rising = current_rsi > rsi_series.iloc[-2] if len(rsi_series) > 1 else False
        is_2_falling = current_rsi < rsi_series.iloc[-2] if len(rsi_series) > 1 else False

    # Up (Bullish): 40-80, 2 rising, latest > 55
    if (40 <= current_rsi <= 80) and is_2_rising and (current_rsi > 55):
        # Strong Up: > 65 anytime in lookback
        if (rsi_series > 65).any():
            return "Strong Up"
        return "Up"

    # Down (Bearish): 20-60, 2 falling, latest < 40
    if (20 <= current_rsi <= 60) and is_2_falling and (current_rsi < 40):
        # Strong Down: < 30 anytime in lookback
        if (rsi_series < 30).any():
            return "Strong Down"
        return "Down"
        
    # If it falls outside these specific buckets but hasn't triggered "Sideways"
    # likely in a transition or extreme overbought/sold state without clear direction
    if current_rsi > 80: return "Overbought (Up)"
    if current_rsi < 20: return "Oversold (Down)"

    return "Unknown"

def calculate_rsi(df, length=14):
    """
    Calculates the Relative Strength Index (RSI).
    
    Args:
        df (pd.DataFrame): Input OHLCV data.
        length (int): The lookback period for RSI.
        
    Returns:
        tuple: (pd.DataFrame, str) -> (DataFrame with RSI col, Trend Status)
    """
    # Explicitly calculate RSI on the 'close' price and assign it to a new column.
    rsi_col = f"RSI_{length}"
    rsi_series = ta.rsi(df['close'], length=length)
    if rsi_series is not None:
        df[rsi_col] = rsi_series
    else:
        df[rsi_col] = pd.Series(float('nan'), index=df.index)
    
    # Calculate Trend
    trend = calculate_rsi_trend(df, rsi_col)
    
    return df, trend

def calculate_ma_trend(df, short_ma_col, long_ma_col, price_col='close'):
    """
    Determines the trend based on MA spread and reversal patterns.
    Sideways: Spread < 2% of price.
    Up: Short > Long OR a bullish reversal pattern is detected.
    Down: Short < Long OR a bearish reversal pattern is detected.
    """
    if df.empty or short_ma_col not in df.columns or long_ma_col not in df.columns:
        return "Unknown"
         
    last_row = df.iloc[-1]
    if price_col not in df.columns:
        return "Unknown"
    if short_ma_col not in df.columns or long_ma_col not in df.columns:
        return "Unknown"

    short_val = last_row[short_ma_col]
    long_val = last_row[long_ma_col]
    price = last_row[price_col]
    
    if pd.isna(short_val) or pd.isna(long_val) or price == 0:
        return "Unknown"

    # 1. Check for Sideways trend first
    diff = abs(short_val - long_val)
    spread_pct = (diff / price) * 100
    if spread_pct < 2.0:
        return "Sideways"

    # 2. Check for Reversal Patterns
    if len(df) >= 4:
        recent_df = df.tail(4)
        short_ma_series = recent_df[short_ma_col].values
        long_ma_series = recent_df[long_ma_col].values
        delta_ma_series = np.abs(short_ma_series - long_ma_series)

        # Check for 3 consecutive rising/falling periods
        is_3_rising_short = (short_ma_series[1] > short_ma_series[0]) and (short_ma_series[2] > short_ma_series[1]) and (short_ma_series[3] > short_ma_series[2])
        is_3_rising_long = (long_ma_series[1] > long_ma_series[0]) and (long_ma_series[2] > long_ma_series[1]) and (long_ma_series[3] > long_ma_series[2])
        
        is_3_falling_short = (short_ma_series[1] < short_ma_series[0]) and (short_ma_series[2] < short_ma_series[1]) and (short_ma_series[3] < short_ma_series[2])
        is_3_falling_long = (long_ma_series[1] < long_ma_series[0]) and (long_ma_series[2] < long_ma_series[1]) and (long_ma_series[3] < long_ma_series[2])

        is_3_falling_delta = (delta_ma_series[1] < delta_ma_series[0]) and (delta_ma_series[2] < delta_ma_series[1]) and (delta_ma_series[3] < delta_ma_series[2])

        # Bullish Reversal: Fast MA is below Slow MA, but both are rising and the gap is closing.
        if short_val < long_val and is_3_rising_short and is_3_rising_long and is_3_falling_delta:
            return "Up"

        # Bearish Reversal: Fast MA is above Slow MA, but both are falling and the gap is closing.
        if short_val > long_val and is_3_falling_short and is_3_falling_long and is_3_falling_delta:
            return "Down"

    # 3. Default Trend Logic (based on current position)
    if short_val > long_val:
        return "Up"
    
    return "Down"

def calculate_ma_cross_trend(df, signal_col):
    """
    Determines the trend based on recent MA cross events.
    """
    if signal_col not in df.columns or df.empty:
        return "Unknown"
    
    # Get the 3 latest *actual* cross events (non-zero signals)
    latest_crosses = df[df[signal_col] != 0][signal_col].tail(3).tolist()

    if len(latest_crosses) < 2:
        return "Unknown" # Not enough events to determine a trend

    # Check if 2 or more of the last 3 crosses have the same value
    if latest_crosses.count(1) >= 2:
        return "Up"  # Recent Golden crosses suggest an Up trend
    elif latest_crosses.count(-1) >= 2:
        return "Down"  # Recent Death crosses suggest a Down trend
    else:
        return "Sideways" # Mixed signals (e.g., [1, -1, 1])

def calculate_ma_cross(df, ma_pairs):
    """
    Calculates SMAs and detects cross signals for given pairs.
    
    Args:
        df (pd.DataFrame): Input OHLCV data.
        ma_pairs (list of tuples): List of (short_ma, long_ma) pairs.
        
    Returns:
        pd.DataFrame: DataFrame with added SMA and cross signal columns.
    """
    for short_ma, long_ma in ma_pairs:
        # Define column names first
        short_ma_col = f'SMA_{short_ma}'
        long_ma_col = f'SMA_{long_ma}'
        signal_col = f'cross_{short_ma}_{long_ma}'

        # Explicitly calculate and assign SMAs on the 'close' price to ensure a single series is returned.
        if 'close' not in df.columns:
            return df
        # Handle cases where pandas_ta returns None (e.g. insufficient data)
        sma_short_series = ta.sma(df['close'], length=int(short_ma))
        if sma_short_series is not None:
            df[short_ma_col] = sma_short_series
        else:
            df[short_ma_col] = pd.Series(float('nan'), index=df.index)
            
        sma_long_series = ta.sma(df['close'], length=long_ma)
        if sma_long_series is not None:
            df[long_ma_col] = sma_long_series
        else:
            df[long_ma_col] = pd.Series(float('nan'), index=df.index)
        
        # Detect Golden Cross (1) and Death Cross (-1)
        # Use .fillna(False) to safely handle NaNs at the beginning of the SMA series
        # Ensure numeric comparisons to avoid TypeError with NoneType
        s_ma = pd.to_numeric(df[short_ma_col], errors='coerce')
        l_ma = pd.to_numeric(df[long_ma_col], errors='coerce')
        
        golden_cross = (s_ma > l_ma) & (s_ma.shift(1) <= l_ma.shift(1))
        death_cross = (s_ma < l_ma) & (s_ma.shift(1) >= l_ma.shift(1))
        
        df[signal_col] = 0
        df.loc[golden_cross.fillna(False), signal_col] = 1
        df.loc[death_cross.fillna(False), signal_col] = -1
        
    return df

def calculate_ichimoku(df):
    pass

def calculate_bollinger(df):
    pass

def calculate_stochastic_trend(df, k_col='%K', d_col='%D') -> str:
    """
    Determines the trend based on Stochastic Oscillator (%K and %D) values.

    Args:
        df (pd.DataFrame): DataFrame containing %K and %D columns.
        k_col (str): Name of the %K column.
        d_col (str): Name of the %D column.

    Returns:
        str: "Up", "Down", or "Sideways".
    """
    if df.empty:
        return "Unknown"

    if k_col not in df.columns or d_col not in df.columns:
        return "Unknown"

    # Get the latest %K and %D values
    k_val = df[k_col].iloc[-1]
    d_val = df[d_col].iloc[-1]

    # --- General Trend ---
    if k_val > 70 and d_val > 70:
        return "Up"
    elif k_val < 30 and d_val < 30:
        return "Down"

    # --- Crossovers ---
    if k_val > d_val and k_val > 50 and d_val > 50:
        return "Up"
    elif k_val < d_val and k_val < 50 and d_val < 50:
        return "Down"

    # --- Sideways ---
    # The "Whipsaw" Warning: If %K and %D are crossing each other frequently near the 50 level, it confirms a "Chop" zone with zero momentum.
    crosses_50 = ((df[k_col].shift(1) - 50) * (df[k_col] - 50) < 0).sum() # Count 50-crosses
    if crosses_50 / len(df) > 0.25: # Adjust threshold as needed
        return "Sideways"

    # If none of the above conditions are met, return "Sideways"
    # which is a more neutral classification than "Unknown" in this context.
    return "Sideways"