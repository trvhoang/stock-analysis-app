# suggestion_visualization.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
import concurrent.futures

# Function to get all tickers with average volume filter
def get_all_tickers(engine, min_avg_volume):
    query = text("""
        SELECT ticker
        FROM trading_data
        WHERE ticker <> 'VNINDEX'
        GROUP BY ticker
        HAVING AVG(volume) >= :min_avg_volume
    """)
    return pd.read_sql(query, engine, params={"min_avg_volume": min_avg_volume})["ticker"].tolist()

# Function to analyze a single ticker (no changes here)
def analyze_ticker(ticker, day_range, result_day_range, engine):
    query = text("""
        WITH trading_days AS (
            SELECT date, close,
                   ROW_NUMBER() OVER (ORDER BY date) AS day_rank
            FROM trading_data
            WHERE ticker = :ticker
        ),
        ordered_data AS (
            SELECT date, close,
                   LAG(close, :day_range) OVER (ORDER BY date) AS prev_close,
                   LEAD(close, :result_day_range) OVER (ORDER BY date) AS next_close,
                   day_rank,
                   LAG(day_rank, :day_range) OVER (ORDER BY date) AS prev_day_rank,
                   LEAD(day_rank, :result_day_range) OVER (ORDER BY date) AS next_day_rank
            FROM trading_days
        ),
        delta_calc AS (
            SELECT date,
                   close,
                   prev_close,
                   next_close,
                   CASE 
                       WHEN prev_close IS NOT NULL AND (day_rank - prev_day_rank) = :day_range
                       THEN ROUND(((close - prev_close)::FLOAT / prev_close * 100)::NUMERIC, 2)
                       ELSE NULL 
                   END AS signal_delta,
                   CASE 
                       WHEN next_close IS NOT NULL AND (next_day_rank - day_rank) = :result_day_range
                       THEN ROUND(((next_close - close)::FLOAT / close * 100)::NUMERIC, 2)
                       ELSE NULL 
                   END AS result_delta
            FROM ordered_data
        )
        SELECT 
            COUNT(*) FILTER (WHERE result_delta > 0) AS up_count,
            COUNT(*) FILTER (WHERE result_delta < 0) AS down_count,
            COUNT(*) FILTER (WHERE result_delta = 0) AS no_change_count,
            MIN(result_delta) FILTER (WHERE result_delta > 0) AS min_up_delta,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY result_delta) FILTER (WHERE result_delta > 0) AS median_up_delta,
            MAX(result_delta) FILTER (WHERE result_delta > 0) AS max_up_delta,
            MIN(result_delta) FILTER (WHERE result_delta < 0) AS min_down_delta,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY result_delta) FILTER (WHERE result_delta < 0) AS median_down_delta,
            MAX(result_delta) FILTER (WHERE result_delta < 0) AS max_down_delta,
            COUNT(*) AS total_signals
        FROM delta_calc
        WHERE signal_delta IS NOT NULL AND result_delta IS NOT NULL
    """)
    
    params = {"ticker": ticker, "day_range": day_range, "result_day_range": result_day_range}
    result = pd.read_sql(query, engine, params=params).iloc[0]
    
    if result["total_signals"] > 0:
        possibility_up = round((result["up_count"] / result["total_signals"]) * 100, 2)
        possibility_down = round((result["down_count"] / result["total_signals"]) * 100, 2)
    else:
        possibility_up = 0
        possibility_down = 0
    
    return {
        "ticker": ticker,
        "possibility_up": possibility_up,
        "possibility_down": possibility_down,
        "min_up_delta": result["min_up_delta"],
        "median_up_delta": result["median_up_delta"],
        "max_up_delta": result["max_up_delta"],
        "min_down_delta": result["min_down_delta"],
        "median_down_delta": result["median_down_delta"],
        "max_down_delta": result["max_down_delta"]
    }

# Main page function with volume filter
def suggestion_page(engine):
    st.header("Suggestion Page")
    
    # Input fields
    col1, col2, col3 = st.columns(3)
    with col1:
        day_range = st.number_input("Day Range", min_value=1, value=5, step=1)
    with col2:
        result_day_range = st.number_input("Result Day Range", min_value=1, value=7, step=1)
    with col3:
        volume_threshold = st.number_input("Min Avg Volume (in thousands)", min_value=0, value=100, step=10)
    
    # Button to trigger analysis
    if st.button("Generate Suggestions"):
        min_avg_volume = volume_threshold * 1000  # Convert thousands to actual volume
        tickers = get_all_tickers(engine, min_avg_volume)
        st.write(f"Analyzing {len(tickers)} tickers with average volume >= {min_avg_volume}...")
        
        # Parallel processing of tickers
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            future_to_ticker = {executor.submit(analyze_ticker, ticker, day_range, result_day_range, engine): ticker for ticker in tickers}
            for future in concurrent.futures.as_completed(future_to_ticker):
                results.append(future.result())
        
        # Convert results to DataFrame
        df_results = pd.DataFrame(results)
        
        # Table 1: Top 5 by Possibility of Up
        top_up_possibility = df_results.nlargest(5, "possibility_up")[["ticker", "possibility_up"]]
        st.subheader("Top 5 Tickers by Possibility of Up")
        st.dataframe(top_up_possibility, use_container_width=True)
        
        # Table 2: Top 5 by Delta of Up
        top_up_delta = df_results.nlargest(5, "max_up_delta")[["ticker", "min_up_delta", "median_up_delta", "max_up_delta"]]
        st.subheader("Top 5 Tickers by Delta of Up")
        st.dataframe(top_up_delta, use_container_width=True)
        
        # Table 3: Top 5 by Possibility of Down
        top_down_possibility = df_results.nsmallest(5, "possibility_down")[["ticker", "possibility_down"]]
        st.subheader("Top 5 Tickers by Possibility of Down")
        st.dataframe(top_down_possibility, use_container_width=True)
        
        # Table 4: Top 5 by Delta of Down
        top_down_delta = df_results.nsmallest(5, "min_down_delta")[["ticker", "min_down_delta", "median_down_delta", "max_down_delta"]]
        st.subheader("Top 5 Tickers by Delta of Down")
        st.dataframe(top_down_delta, use_container_width=True)