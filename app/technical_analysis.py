import pandas as pd
from sqlalchemy import text
import pandas_ta as ta

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
        resample_period = 'W' if timeframe == 'Week' else 'M'
        
        # Define aggregation rules
        agg_rules = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}
        
        df = df.resample(resample_period).agg(agg_rules)
        
        # As requested, remove any resampled periods that had no trading days
        df.dropna(inplace=True)

    # Ensure the final dataframe has the requested number of rows and reset index
    df = df.tail(limit).reset_index()

    return df

def calculate_stochastic(df):
    pass

def calculate_rsi(df):
    pass

def calculate_ma_cross(df, ma_pairs):
    """
    Calculates SMAs and detects cross signals for given pairs.
    
    Args:
        df (pd.DataFrame): Input OHLCV data.
        ma_pairs (list of tuples): List of (short_ma, long_ma) pairs.
        
    Returns:
        pd.DataFrame: DataFrame with appended SMA and cross signal columns.
    """
    for short_ma, long_ma in ma_pairs:
        # Calculate SMAs using pandas_ta, which appends them to the df
        df.ta.sma(length=short_ma, append=True)
        df.ta.sma(length=long_ma, append=True)

        short_ma_col = f'SMA_{short_ma}'
        long_ma_col = f'SMA_{long_ma}'
        signal_col = f'cross_{short_ma}_{long_ma}'

        # Detect Golden Cross (1) and Death Cross (-1)
        golden_cross = (df[short_ma_col] > df[long_ma_col]) & (df[short_ma_col].shift(1) <= df[long_ma_col].shift(1))
        death_cross = (df[short_ma_col] < df[long_ma_col]) & (df[short_ma_col].shift(1) >= df[long_ma_col].shift(1))
        
        df[signal_col] = 0
        df.loc[golden_cross, signal_col] = 1
        df.loc[death_cross, signal_col] = -1
    return df

def calculate_ichimoku(df):
    pass

def calculate_bollinger(df):
    pass