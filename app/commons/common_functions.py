import pandas as pd
from sqlalchemy import text
import traceback
# Use the directory prefix for modules within the same package to ensure correct resolution in Docker
from commons.common_queries import BASE_DELTA_CALC_CTE, COMMON_DELTA_FILTER_WHERE_CLAUSE, DELTA_UP_THRESHOLD, DELTA_DOWN_THRESHOLD
from commons.technical_analysis import (
    fetch_data, calculate_stochastic, calculate_rsi, calculate_ma_cross,
    calculate_ma_trend, calculate_ma_cross_trend
)

# Centralized Trend Keys for consistency
TREND_EMOJIS = {
    "Strong Up": "📈",
    "Up": "📈",
    "Sideways": "♻️",
    "Down": "📉",
    "Strong Down": "📉",
    "Unknown": "❓",
    "Overbought (Up)": "🐮",
    "Oversold (Down)": "🐻"
}

# Function to analyze a single ticker
# Moved from suggestion_visualization.py to allow reuse in analyze_visualization.py
def analyze_ticker(ticker, day_range, result_day_range, engine):
    if day_range < 2:
        return None
    try:
        lag_days = day_range - 1

        # 1. Get latest data to calculate current_delta
        query_latest = """
            SELECT date, close, exchange 
            FROM trading_data 
            WHERE ticker = %(ticker)s 
            ORDER BY date DESC 
            LIMIT %(limit)s
        """
        
        conn = engine.raw_connection()
        try:
            df_latest = pd.read_sql(query_latest, conn, params={"ticker": ticker, "limit": day_range})
        finally:
            conn.close()

        exchange = df_latest.iloc[0]["exchange"] if not df_latest.empty and "exchange" in df_latest.columns else "Unknown"

        # Ensure we have enough data points to calculate the delta
        if len(df_latest) < day_range:
            print(f"Insufficient data for {ticker}: Found {len(df_latest)} rows, needed {day_range}.")
            return None
            
        current_close = df_latest.iloc[0]["close"]
        end_date = df_latest.iloc[0]["date"]
        prev_close = df_latest.iloc[-1]["close"]
        start_date = df_latest.iloc[-1]["date"]
        
        if prev_close == 0:
            print(f"Zero previous close price detected for {ticker}.")
            return None
            
        # Calculate the current delta for this specific ticker
        # Convert to native Python float to avoid Psycopg2 adapter issues with numpy types
        current_delta = float(round(((current_close - prev_close) / prev_close * 100), 2))
        
        # 2. Set target range based on current delta
        delta_min = current_delta - 1
        delta_max = current_delta + 1

        # 3. Run historical analysis using the calculated target
        # Use centralized thresholds (:up_threshold, :down_threshold) instead of hardcoded values
        query_str = BASE_DELTA_CALC_CTE + """
            SELECT
                COUNT(*) FILTER (WHERE result_delta > :up_threshold) AS up_count,
                COUNT(*) FILTER (WHERE result_delta < :down_threshold) AS down_count,
                COUNT(*) FILTER (WHERE result_delta BETWEEN :down_threshold AND :up_threshold) AS no_change_count,
                MIN(result_delta) FILTER (WHERE result_delta > 0) AS min_up_delta,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY result_delta) FILTER (WHERE result_delta > 0) AS median_up_delta,
                MAX(result_delta) FILTER (WHERE result_delta > 0) AS max_up_delta,
                MIN(result_delta) FILTER (WHERE result_delta < 0) AS min_down_delta,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY result_delta) FILTER (WHERE result_delta < 0) AS median_down_delta,
                MAX(result_delta) FILTER (WHERE result_delta < 0) AS max_down_delta,
                COUNT(*) AS total_signals
            FROM delta_calc
        """ + COMMON_DELTA_FILTER_WHERE_CLAUSE

        # Convert SQLAlchemy :param syntax to Psycopg2 %(param)s syntax for raw connection
        query_str = query_str.replace(":ticker", "%(ticker)s")
        query_str = query_str.replace(":validation_days", "%(validation_days)s")
        query_str = query_str.replace(":result_days", "%(result_days)s")
        query_str = query_str.replace(":delta_min", "%(delta_min)s")
        query_str = query_str.replace(":delta_max", "%(delta_max)s")
        query_str = query_str.replace(":up_threshold", "%(up_threshold)s")
        query_str = query_str.replace(":down_threshold", "%(down_threshold)s")

        params = {
            "ticker": ticker,
            "validation_days": lag_days,
            "result_days": result_day_range,
            "delta_min": delta_min,
            "delta_max": delta_max,
            "up_threshold": DELTA_UP_THRESHOLD,
            "down_threshold": DELTA_DOWN_THRESHOLD
        }
        
        conn = engine.raw_connection()
        try:
            result = pd.read_sql(query_str, conn, params=params).iloc[0]
        finally:
            conn.close()
        
        if result["total_signals"] > 0:
            possibility_up = round((result["up_count"] / result["total_signals"]) * 100, 2)
            possibility_down = round((result["down_count"] / result["total_signals"]) * 100, 2)
        else:
            possibility_up = 0
            possibility_down = 0
        
        # 4. Determine Statistical Trend
        if possibility_up > 70: stat_trend = "Strong Up"
        elif 53 <= possibility_up <= 70: stat_trend = "Up"
        elif 48 <= possibility_up < 53: stat_trend = "Sideways"
        elif 30 <= possibility_up < 48: stat_trend = "Down"
        else: stat_trend = "Strong Down"

        # 5. Perform Technical Analysis for Trend Alignment
        # Use current logic: Day timeframe for short ranges, Week for long
        tech_timeframe = 'Day' if day_range < 15 else 'Week'
        s_ma, l_ma = (5, 10) if tech_timeframe == 'Day' else (4, 12)
        
        df_tech = fetch_data(ticker, tech_timeframe, 100, engine)
        tech_trend = "Unknown"
        tech_score = 0
        
        if not df_tech.empty:
            tech_data_list = []
            # Run basic indicators
            df_tech, stoch_trend = calculate_stochastic(df_tech)
            tech_data_list.append([0, "Stoch", "", stoch_trend])
            
            df_tech, rsi_trend = calculate_rsi(df_tech, length=14)
            tech_data_list.append([1, "RSI", "", rsi_trend])
            
            df_tech = calculate_ma_cross(df_tech, [(s_ma, l_ma)])
            short_col, long_col, sig_col = f'SMA_{s_ma}', f'SMA_{l_ma}', f'cross_{s_ma}_{l_ma}'
            
            if short_col in df_tech.columns and long_col in df_tech.columns:
                tech_data_list.append([2, "MA", "", calculate_ma_trend(df_tech, short_col, long_col)])
            if sig_col in df_tech.columns:
                tech_data_list.append([3, "Cross", "", calculate_ma_cross_trend(df_tech, sig_col)])
            
            _, tech_trend, tech_score = generate_technical_advice(tech_data_list)

        return {
            "ticker": ticker,
            "exchange": exchange,
            "current_delta": current_delta,
            "start_date": start_date,
            "end_date": end_date,
            "total_signals": result["total_signals"],
            "possibility_up": possibility_up,
            "possibility_down": possibility_down,
            "min_up_delta": result["min_up_delta"],
            "median_up_delta": result["median_up_delta"],
            "max_up_delta": result["max_up_delta"],
            "min_down_delta": result["min_down_delta"],
            "median_down_delta": result["median_down_delta"],
            "max_down_delta": result["max_down_delta"],
            "stat_trend": stat_trend,
            "tech_trend": tech_trend,
            "tech_score": tech_score
        }
    except Exception as e:
        # Avoid flooding logs with tracebacks for expected missing data/columns
        if "exchange" not in str(e).lower():
            print(f"Error analyzing ticker {ticker}: {e}")
        # Return None to indicate failure for this specific ticker, allowing the batch to continue
        return None

# --- Centralized Advice Logic (Migrated from analyze_visualization.py) ---

def provide_advice(validation_days, result_days, analysis_results):
    """Generates statistical advice string and trend key."""
    if analysis_results is None or analysis_results["total_signals"] == 0:
        latest_delta = analysis_results.get('current_delta', 'N/A') if analysis_results else 'N/A'
        return f"The current {validation_days}-day delta is {latest_delta}%, but no historical data matches the criteria.", "Unknown"

    latest_delta = analysis_results["current_delta"]
    up_prob = analysis_results["possibility_up"]
    
    if up_prob > 70: trend = "Strong Up"
    elif 53 <= up_prob <= 70: trend = "Up"
    elif 48 <= up_prob < 53: trend = "Sideways"
    elif 30 <= up_prob < 48: trend = "Down"
    else: trend = "Strong Down"
    
    emoji = TREND_EMOJIS.get(trend, "")
    return f"Based on historical data, after a {validation_days}-day delta of {latest_delta:.2f}%, the stock is more likely to go **{trend} {emoji}** in the next {result_days} days.", trend

def generate_technical_advice(tech_data):
    """Generates technical advice string, trend key, and score."""
    if not tech_data:
        return "Not enough data for technical advice.", "Unknown", 0

    trend_map = {
        "Strong Up": 4, "Overbought (Up)": 4, "Up": 3,
        "Sideways": 2, "Unknown": 2, "None": 2,
        "Down": 1, "Strong Down": 0, "Oversold (Down)": 0
    }

    total_score = sum(trend_map.get(item[3], 2) for item in tech_data)
    percentage = (total_score / (len(tech_data) * 4)) * 100
    
    if percentage > 70: trend = "Strong Up"
    elif 53 <= percentage <= 70: trend = "Up"
    elif 48 <= percentage < 53: trend = "Sideways"
    elif 30 <= percentage < 48: trend = "Down"
    else: trend = "Strong Down"
    
    emoji = TREND_EMOJIS.get(trend, "")
    display = f"Based on {len(tech_data)} indicators, the overall trend is **{trend} {emoji}** (Score: {percentage:.0f}%)."
    return display, trend, percentage

def generate_final_advice(ticker, statistical_trend, technical_trend):
    """Combines statistical and technical trends into a final recommendation."""
    matrix = {
        "Strong Up": {"Strong Up": "Strong Up", "Up": "Up", "Sideways": "Up", "Down": "Unknown", "Strong Down": "Unknown"},
        "Up": {"Strong Up": "Up", "Up": "Up", "Sideways": "Sideways", "Down": "Unknown", "Strong Down": "Unknown"},
        "Sideways": {"Strong Up": "Up", "Up": "Sideways", "Sideways": "Unknown", "Down": "Down", "Strong Down": "Down"},
        "Down": {"Strong Up": "Unknown", "Up": "Unknown", "Sideways": "Unknown", "Down": "Down", "Strong Down": "Strong Down"},
        "Strong Down": {"Strong Up": "Unknown", "Up": "Unknown", "Sideways": "Unknown", "Down": "Strong Down", "Strong Down": "Strong Down"}
    }

    final_outlook = matrix.get(statistical_trend, {}).get(technical_trend, "Unknown")
    emoji = TREND_EMOJIS.get(final_outlook, "❓")
    
    explanations = {
        "Strong Up": "Both analyses are strongly bullish.",
        "Up": "Both analyses point towards a bullish outlook.",
        "Sideways": "Analyses show mixed signals, suggesting sideways movement.",
        "Down": "Both analyses point towards a bearish outlook.",
        "Strong Down": "Both analyses are strongly bearish.",
        "Unknown": "Signals are conflicting, leading to an uncertain outlook."
    }

    return f"**{ticker}'s trend: {final_outlook} {emoji}**. {explanations.get(final_outlook, '')}"

def synthesize_all_advice(stats_data, validation_days, result_days, engine):
    """
    Generates the advice strings based on stats and technical analysis.
    This centralizes the logic to be shared between UI and API.
    """
    ticker = stats_data['ticker']
    
    # 1. Get Statistical Advice
    stat_msg, stat_trend = provide_advice(validation_days, result_days, stats_data)
    
    # 2. Perform Technical Analysis
    if validation_days < 15:
        tech_timeframe, s_ma, l_ma = 'Day', 5, 10
    else:
        tech_timeframe, s_ma, l_ma = 'Week', 4, 12
        
    df_tech = fetch_data(ticker, tech_timeframe, 100, engine)
    tech_data = []
    
    if not df_tech.empty:
        # Run indicators and collect trend data
        df_tech, stoch_trend = calculate_stochastic(df_tech)
        tech_data.append([0, "Stochastic", "", stoch_trend])
        
        df_tech, rsi_trend = calculate_rsi(df_tech, length=14)
        tech_data.append([1, "RSI14", "", rsi_trend])
        
        df_tech = calculate_ma_cross(df_tech, [(s_ma, l_ma)])
        short_col, long_col, sig_col = f'SMA_{s_ma}', f'SMA_{l_ma}', f'cross_{s_ma}_{l_ma}'
        
        if short_col in df_tech.columns and long_col in df_tech.columns:
            tech_data.append([2, "MA", "", calculate_ma_trend(df_tech, short_col, long_col)])
        if sig_col in df_tech.columns:
            tech_data.append([3, "MA cross", "", calculate_ma_cross_trend(df_tech, sig_col)])

    tech_msg, tech_trend, _ = generate_technical_advice(tech_data)
    
    # 3. Get Final Advice
    final_msg = generate_final_advice(ticker, stat_trend, tech_trend)
    
    return {
        "statistical": stat_msg.replace("**", ""), # Strip markdown for API
        "technical": tech_msg.replace("**", ""),
        "final": final_msg.replace("**", "")
    }