# technical_analysis.py
# Centralized handler for technical indicators and trend classification.

import pandas as pd
from sqlalchemy import text
import pandas_ta as ta
import numpy as np

from commons.price_utils import PRICE_OUTPUT_UI, prepare_price_for_output

# Shared by the Technical Analyze page and offline backtest adapters so the
# daily/weekly/monthly MA conventions cannot drift between execution paths.
MA_PAIRS_BY_TIMEFRAME = {
    "Day": ((5, 10), (10, 20), (20, 60)),
    "Week": ((4, 12), (12, 26), (26, 52)),
    "Month": ((3, 6), (6, 12), (12, 36)),
}

# Shared by the Technical Analyze page and offline backtest adapters so the
# daily/weekly/monthly MA conventions cannot drift between execution paths.
MA_PAIRS_BY_TIMEFRAME = {
    "Day": ((5, 10), (10, 20), (20, 60)),
    "Week": ((4, 12), (12, 26), (26, 52)),
    "Month": ((3, 6), (6, 12), (12, 36)),
}


# Phase 3 registry: dimensions are metadata only until the Phase 4 scoring
# formula consumes them.  ADX is intentionally grouped as a non-voting gate.
TECHNICAL_DIMENSIONS = {
    "trend_direction": ("MA", "MA cross"),
    "momentum": ("RSI", "Stochastic"),
    "trend_strength": ("ADX",),
    "volume": ("OBV",),
    "volatility": ("ATR", "Bollinger"),
}

TECHNICAL_INDICATOR_METADATA = {
    indicator: {
        "dimension": dimension,
        "votes": dimension != "trend_strength",
    }
    for dimension, indicators in TECHNICAL_DIMENSIONS.items()
    for indicator in indicators
}

# Equal starting weights are intentionally named so Phase 6 can validate and
# tune them.  ADX is excluded because its metadata marks it as non-voting.
TECHNICAL_GROUP_WEIGHTS = {
    "trend_direction": 0.25,
    "momentum": 0.25,
    "volume": 0.25,
    "volatility": 0.25,
}

ADX_TREND_THRESHOLD = 20.0
ADX_LOW_TREND_MULTIPLIER = 0.5

_TECHNICAL_INDICATOR_ALIASES = {
    "ma": "MA",
    "moving average": "MA",
    "ma cross": "MA cross",
    "cross": "MA cross",
    "rsi": "RSI",
    "rsi14": "RSI",
    "stoch": "Stochastic",
    "stochastic": "Stochastic",
    "adx": "ADX", # Average Directional Index
    "obv": "OBV", # On Balance Volume
    "atr": "ATR", # Average True Range
    "bollinger": "Bollinger",
    "bollinger band": "Bollinger",
    "bollinger bands": "Bollinger",
}

_TREND_KEY_SCORES = {
    "Strong Up": 4,
    "Overbought (Up)": 4,
    "Up": 3,
    "Sideways": 2,
    "Unknown": 2,
    "None": 2,
    "Down": 1,
    "Strong Down": 0,
    "Oversold (Down)": 0,
}


def _canonical_indicator_name(indicator_name):
    """Return the registry name for a display alias, or None if unknown."""
    normalized = str(indicator_name or "").strip().casefold()
    return _TECHNICAL_INDICATOR_ALIASES.get(normalized)


def group_technical_indicators(tech_data):
    """Group technical signal records by the resolved Phase 3 dimensions.

    Signal records retain their original shape and order.  Unknown indicator
    names are kept in ``unassigned`` so future additions cannot disappear
    silently.  The helper does not mutate the caller-owned list or records.
    """
    grouped = {dimension: [] for dimension in TECHNICAL_DIMENSIONS}
    grouped["unassigned"] = []

    for signal in tech_data:
        if len(signal) < 2:
            grouped["unassigned"].append(signal)
            continue

        canonical_name = _canonical_indicator_name(signal[1])
        metadata = TECHNICAL_INDICATOR_METADATA.get(canonical_name)
        if metadata is None:
            grouped["unassigned"].append(signal)
            continue

        grouped[metadata["dimension"]].append(signal)

    return grouped


def apply_adx_gate(group_scores, adx_value):
    """Apply the resolved low-ADX multiplier without mutating input scores.

    The binary boundary is deliberate: values below 20.0 halve only the
    trend-direction score; values at or above 20.0 keep it unchanged.  An
    unavailable ADX is not penalized a second time, so invalid values skip
    gating and preserve the full score.
    """
    gated_scores = dict(group_scores)

    try:
        numeric_adx = float(adx_value)
    except (TypeError, ValueError):
        return gated_scores

    if pd.isna(numeric_adx):
        return gated_scores

    if (
        numeric_adx < ADX_TREND_THRESHOLD
        and "trend_direction" in gated_scores
    ):
        gated_scores["trend_direction"] *= ADX_LOW_TREND_MULTIPLIER

    return gated_scores


def calculate_dimension_technical_score(tech_data, adx_value=None):
    """Aggregate technical points by dimension and return score details.

    Each available voting dimension first receives the mean of its indicator
    points.  Missing dimensions are omitted and the configured weights are
    renormalized over the remaining dimensions.  Non-voting dimensions, such
    as ADX's ``trend_strength`` group, never enter the calculation.

    Returns:
        tuple: ``(percentage, group_scores, indicator_count)`` where
        ``percentage`` remains on the existing 0-100 scale.
    """
    grouped = group_technical_indicators(tech_data)
    group_scores = {}
    indicator_count = 0

    for dimension in TECHNICAL_GROUP_WEIGHTS:
        scores = [
            _TREND_KEY_SCORES.get(signal[3], 2)
            for signal in grouped[dimension]
            if len(signal) > 3
        ]
        if not scores:
            continue

        group_scores[dimension] = sum(scores) / len(scores)
        indicator_count += len(scores)

    if not group_scores:
        return 0.0, {}, 0

    group_scores = apply_adx_gate(group_scores, adx_value)

    available_weight = sum(
        TECHNICAL_GROUP_WEIGHTS[dimension] for dimension in group_scores
    )
    weighted_points = sum(
        group_scores[dimension] * TECHNICAL_GROUP_WEIGHTS[dimension]
        for dimension in group_scores
    ) / available_weight
    percentage = (weighted_points / 4) * 100

    return percentage, group_scores, indicator_count


def calculate_trend_correlation(trend_frame):
    """Return pairwise correlation of indicator trend keys on a 0-4 scale.

    ``trend_frame`` is expected to have one indicator per column and one
    aligned observation per row (for example, ticker/date observations). The
    existing technical score mapping is reused: Unknown/neutral values map
    to 2, bullish values to 3/4, and bearish values to 0/1.  The input is
    not mutated. Constant columns follow pandas' standard NaN correlation
    result because their correlation is undefined.
    """
    if not isinstance(trend_frame, pd.DataFrame) or trend_frame.empty:
        return pd.DataFrame(index=trend_frame.columns, columns=trend_frame.columns, dtype=float) if isinstance(trend_frame, pd.DataFrame) else pd.DataFrame()

    scored = trend_frame.apply(lambda series: series.map(_TREND_KEY_SCORES))
    return scored.corr()

def fetch_data(ticker, timeframe, limit, engine):
    """
    Fetches historical stock data for the given ticker.
    
    Args:
        ticker (str): The stock symbol.
        timeframe (str): 'Day', 'Week', or 'Month'.
        limit (int): The number of data points to retrieve (lookback period).
        engine: SQLAlchemy engine.
        
    Returns:
        pd.DataFrame: OHLCV data sorted by date ascending with price columns
        scaled to k VND for technical UI/report consumers.
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

    # Keep database values untouched while giving technical consumers k VND
    # values suitable for charts, reports, and indicator calculations.
    for price_column in ("open", "high", "low", "close"):
        df[price_column] = prepare_price_for_output(
            df[price_column], PRICE_OUTPUT_UI
        )

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

def _true_range(df):
    """
    Computes the True Range series from high/low/close.
    First row has no previous close, so TR_0 = high_0 - low_0.
    Returns a float Series aligned to df.index, or None if required
    columns are missing.
    """
    if not {'high', 'low', 'close'}.issubset(df.columns):
        return None

    high = pd.to_numeric(df['high'], errors='coerce')
    low = pd.to_numeric(df['low'], errors='coerce')
    close = pd.to_numeric(df['close'], errors='coerce')
    prev_close = close.shift(1)

    range_hl = high - low
    range_hc = (high - prev_close).abs()
    range_lc = (low - prev_close).abs()

    tr = pd.concat([range_hl, range_hc, range_lc], axis=1).max(axis=1)
    # No previous close on the first bar: fall back to high-low only.
    if len(tr) > 0:
        tr.iloc[0] = range_hl.iloc[0]

    return tr


def calculate_atr(df, period=14):
    """
    Calculates the Average True Range (ATR) using Wilder-style smoothing.

    Contract:
    - Output: pd.Series named 'ATR_{period}', aligned to df.index.
    - True Range: max(high-low, |high-prev_close|, |low-prev_close|);
      first bar uses high-low only (no previous close).
    - Smoothing: ewm(alpha=1/period, adjust=False, min_periods=period).
    - Missing required columns or empty input: all-NaN Series aligned
      to df.index (empty Series for empty input). Never raises.
    - Does not mutate the input DataFrame.

    Args:
        df (pd.DataFrame): OHLCV data with 'high', 'low', 'close' columns.
        period (int): Wilder smoothing period.

    Returns:
        pd.Series: ATR values named 'ATR_{period}'.
    """
    col_name = f"ATR_{period}"

    if df.empty:
        return pd.Series(dtype=float, index=df.index, name=col_name)

    tr = _true_range(df)
    if tr is None:
        return pd.Series(float('nan'), index=df.index, name=col_name)

    atr = tr.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    atr.name = col_name
    return atr


def calculate_bollinger(df, period=20, std_mult=2):
    """
    Calculates Bollinger Bands: middle/upper/lower bands, bandwidth, and
    percent-b (position within the bands).

    Contract:
    - Output: pd.DataFrame aligned to df.index with columns
      'BBM_{period}_{std_mult}', 'BBU_{period}_{std_mult}',
      'BBL_{period}_{std_mult}', 'BBB_{period}_{std_mult}' (bandwidth, %),
      'BBP_{period}_{std_mult}' (percent-b).
    - middle = rolling mean(close, period); std = rolling std(close, period,
      ddof=1); upper/lower = middle +/- std_mult*std.
    - bandwidth = (upper - lower) / middle * 100.
    - percent_b = (close - lower) / (upper - lower).
    - Missing 'close' or empty input: all-NaN columns aligned to df.index
      (empty DataFrame for empty input). Never raises.
    - Does not mutate the input DataFrame.

    Args:
        df (pd.DataFrame): OHLCV data with a 'close' column.
        period (int): Rolling window for the middle band and std dev.
        std_mult (float): Standard deviation multiplier for the bands.

    Returns:
        pd.DataFrame: Bollinger Band columns described above.
    """
    mult_label = int(std_mult) if float(std_mult) == int(std_mult) else std_mult
    cols = [f"BBM_{period}_{mult_label}", f"BBU_{period}_{mult_label}",
            f"BBL_{period}_{mult_label}", f"BBB_{period}_{mult_label}",
            f"BBP_{period}_{mult_label}"]

    if df.empty:
        return pd.DataFrame({c: pd.Series(dtype=float) for c in cols}, index=df.index)

    if 'close' not in df.columns:
        return pd.DataFrame({c: pd.Series(float('nan'), index=df.index) for c in cols})

    close = pd.to_numeric(df['close'], errors='coerce')
    middle = close.rolling(window=period, min_periods=period).mean()
    std = close.rolling(window=period, min_periods=period).std()
    upper = middle + std_mult * std
    lower = middle - std_mult * std
    bandwidth = (upper - lower) / middle * 100
    percent_b = (close - lower) / (upper - lower)

    result = pd.DataFrame(index=df.index)
    result[cols[0]] = middle
    result[cols[1]] = upper
    result[cols[2]] = lower
    result[cols[3]] = bandwidth
    result[cols[4]] = percent_b
    return result


def calculate_obv(df):
    """
    Calculates On-Balance Volume (OBV): cumulative signed volume based on
    close-to-previous-close direction.

    Contract:
    - Output: pd.Series named 'OBV', aligned to df.index.
    - direction = sign(close.diff()), with the first bar's direction
      treated as flat (0) since there is no previous close to compare.
    - OBV = cumsum(direction * volume). The first value is therefore 0,
      not seeded with the first bar's raw volume.
    - Missing 'close'/'volume' or empty input: all-NaN Series aligned to
      df.index (empty Series for empty input). Never raises.
    - Does not mutate the input DataFrame.

    Args:
        df (pd.DataFrame): OHLCV data with 'close' and 'volume' columns.

    Returns:
        pd.Series: OBV values named 'OBV'.
    """
    if df.empty:
        return pd.Series(dtype=float, index=df.index, name='OBV')

    if not {'close', 'volume'}.issubset(df.columns):
        return pd.Series(float('nan'), index=df.index, name='OBV')

    close = pd.to_numeric(df['close'], errors='coerce')
    volume = pd.to_numeric(df['volume'], errors='coerce')

    direction = np.sign(close.diff()).fillna(0)
    obv = (direction * volume).cumsum()
    obv.name = 'OBV'
    return obv


def calculate_adx(df, period=14):
    """
    Calculates the Average Directional Index (ADX) with its directional
    indicators (+DI / -DI), using Wilder-style smoothing.

    Contract:
    - Output: pd.DataFrame aligned to df.index with columns
      'ADX_{period}', 'DMP_{period}' (+DI), 'DMN_{period}' (-DI).
    - +DM/-DM from high/low differences (standard Wilder definition);
      True Range as in calculate_atr. Each is smoothed with
      ewm(alpha=1/period, adjust=False, min_periods=period), matching
      the ATR smoothing choice (an approximation of Wilder's original
      hand-seeded recursion, not an exact reproduction of it).
    - DI = 100 * smoothed_DM / smoothed_TR; DX = 100 * |DIP-DIN| / (DIP+DIN);
      ADX = Wilder-smoothed DX (same ewm). Because ADX is a smoothed
      average of DX, it only becomes non-NaN roughly one additional
      `period` after DI does.
    - Missing required columns or empty input: all-NaN columns aligned to
      df.index (empty DataFrame for empty input). Never raises.
    - Does not mutate the input DataFrame.

    Args:
        df (pd.DataFrame): OHLCV data with 'high', 'low', 'close' columns.
        period (int): Wilder smoothing period.

    Returns:
        pd.DataFrame: 'ADX_{period}', 'DMP_{period}', 'DMN_{period}'.
    """
    cols = [f"ADX_{period}", f"DMP_{period}", f"DMN_{period}"]

    if df.empty:
        return pd.DataFrame({c: pd.Series(dtype=float) for c in cols}, index=df.index)

    if not {'high', 'low', 'close'}.issubset(df.columns):
        return pd.DataFrame({c: pd.Series(float('nan'), index=df.index) for c in cols})

    high = pd.to_numeric(df['high'], errors='coerce')
    low = pd.to_numeric(df['low'], errors='coerce')

    tr = _true_range(df)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )

    smoothing = dict(alpha=1 / period, adjust=False, min_periods=period)
    smoothed_tr = tr.ewm(**smoothing).mean()
    smoothed_plus_dm = plus_dm.ewm(**smoothing).mean()
    smoothed_minus_dm = minus_dm.ewm(**smoothing).mean()

    dip = 100 * smoothed_plus_dm / smoothed_tr
    din = 100 * smoothed_minus_dm / smoothed_tr

    dx = 100 * (dip - din).abs() / (dip + din)
    adx = dx.ewm(**smoothing).mean()

    result = pd.DataFrame(index=df.index)
    result[cols[0]] = adx
    result[cols[1]] = dip
    result[cols[2]] = din
    return result


def get_latest_adx_value(df, period=14):
    """Return the latest numeric ADX value, or None when unavailable."""
    adx_frame = calculate_adx(df, period=period)
    adx_col = f"ADX_{period}"
    if adx_frame.empty or adx_col not in adx_frame.columns:
        return None

    latest = adx_frame[adx_col].iloc[-1]
    return None if pd.isna(latest) else float(latest)


def calculate_atr_trend(df, atr_col='ATR_14', price_col='close', baseline_window=20):
    """
    Classifies ATR trend by comparing normalized ATR (ATR/close) against
    its own trailing baseline.

    Contract (Phase 2 starting values, candidates for Phase 6 recalibration):
    - ratio = current_norm_atr / baseline, where baseline is the mean of
      normalized ATR over the prior `baseline_window` bars (excluding the
      current bar).
    - ratio >= 1.5           -> "Strong Up"
    - 1.1 <= ratio < 1.5     -> "Up"
    - 0.9 <= ratio < 1.1     -> "Sideways"
    - 0.67 <= ratio < 0.9    -> "Down"
    - ratio < 0.67           -> "Strong Down"
    - Missing columns, empty df, or NaN ratio (insufficient history)
      -> "Unknown".

    Args:
        df (pd.DataFrame): Must contain price_col and atr_col.
        atr_col (str): ATR column name.
        price_col (str): Close price column name.
        baseline_window (int): Lookback window for the baseline mean.

    Returns:
        str: One of "Strong Up", "Up", "Sideways", "Down", "Strong Down",
        "Unknown".
    """
    if df.empty or atr_col not in df.columns or price_col not in df.columns:
        return "Unknown"

    close = pd.to_numeric(df[price_col], errors='coerce')
    atr = pd.to_numeric(df[atr_col], errors='coerce')
    norm_atr = atr / close

    baseline = norm_atr.shift(1).rolling(window=baseline_window).mean()

    if len(norm_atr) == 0:
        return "Unknown"

    current = norm_atr.iloc[-1]
    base = baseline.iloc[-1]

    if pd.isna(current) or pd.isna(base) or base == 0:
        return "Unknown"

    ratio = current / base

    if ratio >= 1.5:
        return "Strong Up"
    if ratio >= 1.1:
        return "Up"
    if ratio >= 0.9:
        return "Sideways"
    if ratio >= 0.67:
        return "Down"
    return "Strong Down"


def calculate_obv_trend(df, obv_col='OBV', price_col='close', lookback=10):
    """
    Classifies OBV trend using OBV slope over `lookback` bars, confirmed
    by price direction over the same window.

    Contract (Phase 2 starting values, candidates for Phase 6 recalibration):
    - obv_change = OBV[-1] - OBV[-lookback]; price_pct = percent change of
      close over the same window.
    - Confirmed rising (obv_change > 0 and price_pct > 0):
        "Strong Up" if price_pct > 3, else "Up".
    - Confirmed falling (obv_change < 0 and price_pct < 0):
        "Strong Down" if price_pct < -3, else "Down".
    - Any other case (flat, or OBV/price disagree in sign) -> "Sideways".
    - Missing columns, empty df, fewer than lookback+1 rows, or NaN inputs
      -> "Unknown".

    Args:
        df (pd.DataFrame): Must contain price_col and obv_col.
        obv_col (str): OBV column name.
        price_col (str): Close price column name.
        lookback (int): Number of bars back to compare against.

    Returns:
        str: One of "Strong Up", "Up", "Sideways", "Strong Down", "Down",
        "Unknown".
    """
    if df.empty or obv_col not in df.columns or price_col not in df.columns:
        return "Unknown"

    if len(df) < lookback + 1:
        return "Unknown"

    close = pd.to_numeric(df[price_col], errors='coerce')
    obv = pd.to_numeric(df[obv_col], errors='coerce')

    obv_last = obv.iloc[-1]
    obv_prior = obv.iloc[-(lookback + 1)]
    close_last = close.iloc[-1]
    close_prior = close.iloc[-(lookback + 1)]

    if pd.isna(obv_last) or pd.isna(obv_prior) or pd.isna(close_last) or pd.isna(close_prior):
        return "Unknown"

    if close_prior == 0:
        return "Unknown"

    obv_change = obv_last - obv_prior
    price_pct = (close_last - close_prior) / close_prior * 100

    if obv_change > 0 and price_pct > 0:
        return "Strong Up" if price_pct > 3 else "Up"

    if obv_change < 0 and price_pct < 0:
        return "Strong Down" if price_pct < -3 else "Down"

    return "Sideways"


def calculate_adx_trend(df, adx_col='ADX_14'):
    """
    Classifies ADX trend strength. ADX is non-directional, so only
    strength-oriented keys are returned; bearish keys are never used.

    Contract:
    - rising = latest ADX > previous ADX (requires 2 valid points; if the
      previous value can't be determined, the trend is treated as
      not-confirmed-rising rather than Unknown, as long as the latest
      value itself is valid).
    - ADX < 20                      -> "Sideways"
    - ADX >= 25 and rising          -> "Strong Up"
    - ADX >= 20 and rising          -> "Up"
    - ADX >= 20 and not rising      -> "Sideways"
    - Missing column, empty df, or NaN latest ADX -> "Unknown".

    Args:
        df (pd.DataFrame): Must contain adx_col.
        adx_col (str): ADX column name.

    Returns:
        str: One of "Strong Up", "Up", "Sideways", "Unknown". Never
        returns "Down" or "Strong Down".
    """
    if df.empty or adx_col not in df.columns:
        return "Unknown"

    adx = pd.to_numeric(df[adx_col], errors='coerce')

    if len(adx) == 0:
        return "Unknown"

    current = adx.iloc[-1]
    if pd.isna(current):
        return "Unknown"

    rising = False
    if len(adx) >= 2:
        previous = adx.iloc[-2]
        if not pd.isna(previous):
            rising = current > previous

    if current < 20:
        return "Sideways"
    if current >= 25 and rising:
        return "Strong Up"
    if current >= 20 and rising:
        return "Up"
    return "Sideways"


def calculate_bollinger_trend(
    df,
    price_col='close',
    bbm_col='BBM_20_2',
    bbu_col='BBU_20_2',
    bbl_col='BBL_20_2',
    bbb_col='BBB_20_2',
    bbp_col='BBP_20_2',
    narrow_bandwidth=4.0,
):
    """
    Classifies Bollinger Band position relative to price.

    Contract (Phase 2 starting values, candidates for Phase 6 recalibration):
    - close > upper band                -> "Strong Up"
    - close < lower band                -> "Strong Down"
    - bandwidth < narrow_bandwidth (%)
      and percent-b in [0.4, 0.6]       -> "Sideways" (narrow + centered)
    - close > middle band                -> "Up"
    - close < middle band                -> "Down"
    - close == middle band (fallback)    -> "Sideways"
    - Missing columns, empty df, or NaN latest values -> "Unknown".

    Args:
        df (pd.DataFrame): Must contain price_col and all band columns.
        narrow_bandwidth (float): Bandwidth percentage below which the
            market is considered "narrow" for the Sideways override.

    Returns:
        str: One of "Strong Up", "Up", "Sideways", "Down", "Strong Down",
        "Unknown".
    """
    required = {price_col, bbm_col, bbu_col, bbl_col, bbb_col, bbp_col}
    if df.empty or not required.issubset(df.columns):
        return "Unknown"

    close = pd.to_numeric(df[price_col], errors='coerce').iloc[-1]
    bbm = pd.to_numeric(df[bbm_col], errors='coerce').iloc[-1]
    bbu = pd.to_numeric(df[bbu_col], errors='coerce').iloc[-1]
    bbl = pd.to_numeric(df[bbl_col], errors='coerce').iloc[-1]
    bbb = pd.to_numeric(df[bbb_col], errors='coerce').iloc[-1]
    bbp = pd.to_numeric(df[bbp_col], errors='coerce').iloc[-1]

    if any(pd.isna(v) for v in (close, bbm, bbu, bbl, bbb, bbp)):
        return "Unknown"

    if close > bbu:
        return "Strong Up"
    if close < bbl:
        return "Strong Down"
    if bbb < narrow_bandwidth and 0.4 <= bbp <= 0.6:
        return "Sideways"
    if close > bbm:
        return "Up"
    if close < bbm:
        return "Down"
    return "Sideways"

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


def _latest_numeric_value(df, column):
    """Return one latest numeric column value, or None when unavailable."""
    if column not in df.columns or df.empty:
        return None

    value = pd.to_numeric(df[column], errors="coerce").iloc[-1]
    return None if pd.isna(value) else float(value)


def _format_indicator_value(value, digits=2):
    """Format scalar indicator values without exposing NaN to the UI."""
    return "N/A" if value is None else f"{value:.{digits}f}"


def _format_price_value(value, digits=2):
    """Format a UI-scaled price with an explicit k VND unit."""
    return "N/A" if value is None else f"{value:.{digits}f}k"


def build_technical_snapshot(df, short_ma, long_ma):
    """Calculate all supported indicators once and prepare shared UI signals.

    The returned snapshot is intentionally a plain dictionary so Streamlit,
    shared advice logic, and API callers can consume the same calculation
    result without introducing a new dependency or a second calculation path.
    The input DataFrame is copied before indicator functions add columns.
    """
    working_df = df.copy()

    working_df, stochastic_trend = calculate_stochastic(working_df)
    working_df, rsi_trend = calculate_rsi(working_df, length=14)
    working_df = calculate_ma_cross(working_df, [(short_ma, long_ma)])

    atr_series = calculate_atr(working_df, period=14)
    working_df[atr_series.name] = atr_series
    working_df["OBV"] = calculate_obv(working_df)

    bollinger_frame = calculate_bollinger(working_df, period=20, std_mult=2)
    working_df = working_df.join(bollinger_frame)

    adx_frame = calculate_adx(working_df, period=14)
    working_df = working_df.join(adx_frame)

    short_col = f"SMA_{short_ma}"
    long_col = f"SMA_{long_ma}"
    cross_col = f"cross_{short_ma}_{long_ma}"
    adx_value = _latest_numeric_value(working_df, "ADX_14")

    ma_short_value = _latest_numeric_value(working_df, short_col)
    ma_long_value = _latest_numeric_value(working_df, long_col)
    stoch_k_value = _latest_numeric_value(working_df, "%K")
    stoch_d_value = _latest_numeric_value(working_df, "%D")
    rsi_value = _latest_numeric_value(working_df, "RSI_14")
    dmp_value = _latest_numeric_value(working_df, "DMP_14")
    dmn_value = _latest_numeric_value(working_df, "DMN_14")
    atr_value = _latest_numeric_value(working_df, "ATR_14")
    obv_value = _latest_numeric_value(working_df, "OBV")
    bbm_value = _latest_numeric_value(working_df, "BBM_20_2")
    bbu_value = _latest_numeric_value(working_df, "BBU_20_2")
    bbl_value = _latest_numeric_value(working_df, "BBL_20_2")
    bbb_value = _latest_numeric_value(working_df, "BBB_20_2")
    bbp_value = _latest_numeric_value(working_df, "BBP_20_2")

    ma_trend = calculate_ma_trend(working_df, short_col, long_col)
    ma_cross_trend = calculate_ma_cross_trend(working_df, cross_col)
    adx_trend = calculate_adx_trend(working_df)
    atr_trend = calculate_atr_trend(working_df)
    obv_trend = calculate_obv_trend(working_df)
    bollinger_trend = calculate_bollinger_trend(working_df)

    recent_crosses = []
    if cross_col in working_df.columns:
        recent_crosses = working_df[working_df[cross_col] != 0][cross_col].tail(3).tolist()
    cross_labels = {1: "Golden", -1: "Death"}
    ma_cross_value = " - ".join(
        cross_labels.get(signal, "Unknown") for signal in recent_crosses
    ) or "None"

    indicator_details = [
        {
            "indicator": "MA",
            "dimension": "trend_direction",
            "role": "vote",
            "value": (
                f"SMA_{short_ma}: {_format_price_value(ma_short_value, 1)} - "
                f"SMA_{long_ma}: {_format_price_value(ma_long_value, 1)}"
            ),
            "trend": ma_trend,
        },
        {
            "indicator": "MA cross",
            "dimension": "trend_direction",
            "role": "vote",
            "value": ma_cross_value,
            "trend": ma_cross_trend,
        },
        {
            "indicator": "RSI",
            "dimension": "momentum",
            "role": "vote",
            "value": _format_indicator_value(rsi_value, 1),
            "trend": rsi_trend,
        },
        {
            "indicator": "Stochastic",
            "dimension": "momentum",
            "role": "vote",
            "value": (
                f"%K: {_format_indicator_value(stoch_k_value, 1)} - "
                f"%D: {_format_indicator_value(stoch_d_value, 1)}"
            ),
            "trend": stochastic_trend,
        },
        {
            "indicator": "ADX",
            "dimension": "trend_strength",
            "role": "gate",
            "value": (
                f"ADX: {_format_indicator_value(adx_value, 1)} - "
                f"+DI: {_format_indicator_value(dmp_value, 1)} - "
                f"-DI: {_format_indicator_value(dmn_value, 1)}"
            ),
            "trend": adx_trend,
        },
        {
            "indicator": "OBV",
            "dimension": "volume",
            "role": "vote",
            "value": _format_indicator_value(obv_value, 0),
            "trend": obv_trend,
        },
        {
            "indicator": "ATR",
            "dimension": "volatility",
            "role": "vote",
            "value": _format_price_value(atr_value, 2),
            "trend": atr_trend,
        },
        {
            "indicator": "Bollinger",
            "dimension": "volatility",
            "role": "vote",
            "value": (
                f"Middle: {_format_price_value(bbm_value, 2)} - "
                f"Upper: {_format_price_value(bbu_value, 2)} - "
                f"Lower: {_format_price_value(bbl_value, 2)} - "
                f"Bandwidth: {_format_indicator_value(bbb_value, 2)}% - "
                f"%B: {_format_indicator_value(bbp_value, 2)}"
            ),
            "trend": bollinger_trend,
        },
    ]

    signals = [
        [index, record["indicator"], record["value"], record["trend"]]
        for index, record in enumerate(indicator_details)
    ]

    return {
        "data": working_df,
        "signals": signals,
        "report": indicator_details,
        "adx_value": adx_value,
    }
