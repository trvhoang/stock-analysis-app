import pandas as pd
from sqlalchemy import text
from common_queries import BASE_DELTA_CALC_CTE, COMMON_DELTA_FILTER_WHERE_CLAUSE, DELTA_UP_THRESHOLD, DELTA_DOWN_THRESHOLD

# Function to analyze a single ticker
# Moved from suggestion_visualization.py to allow reuse in analyze_visualization.py
def analyze_ticker(ticker, day_range, result_day_range, engine):
    if day_range < 2:
        return None
    try:
        lag_days = day_range - 1

        # 1. Get latest data to calculate current_delta
        # We need the close of the most recent date, and the close 'lag_days' trading days before that.
        # We fetch day_range (which is lag_days + 1) records to get the start and end points of the window.
        query_latest = text("""
            SELECT date, close 
            FROM trading_data 
            WHERE ticker = :ticker 
            ORDER BY date DESC 
            LIMIT :limit
        """)
        
        df_latest = pd.read_sql(query_latest, engine, params={"ticker": ticker, "limit": day_range})
        
        # Ensure we have enough data points to calculate the delta
        if len(df_latest) < day_range:
            return None
            
        current_close = df_latest.iloc[0]["close"]
        end_date = df_latest.iloc[0]["date"]
        prev_close = df_latest.iloc[-1]["close"]
        start_date = df_latest.iloc[-1]["date"]
        
        if prev_close == 0:
            return None
            
        # Calculate the current delta for this specific ticker
        current_delta = round(((current_close - prev_close) / prev_close * 100), 2)
        
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

        query = text(query_str)
        
        params = {
            "ticker": ticker,
            "validation_days": lag_days,
            "result_days": result_day_range,
            "delta_min": delta_min,
            "delta_max": delta_max,
            "up_threshold": DELTA_UP_THRESHOLD,
            "down_threshold": DELTA_DOWN_THRESHOLD
        }
        result = pd.read_sql(query, engine, params=params).iloc[0]
        
        if result["total_signals"] > 0:
            possibility_up = round((result["up_count"] / result["total_signals"]) * 100, 2)
            possibility_down = round((result["down_count"] / result["total_signals"]) * 100, 2)
        else:
            possibility_up = 0
            possibility_down = 0
        
        return {
            "ticker": ticker,
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
            "max_down_delta": result["max_down_delta"]
        }
    except Exception:
        # Return None to indicate failure for this specific ticker, allowing the batch to continue
        return None