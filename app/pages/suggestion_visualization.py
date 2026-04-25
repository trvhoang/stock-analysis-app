# suggestion_visualization.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
import concurrent.futures
from datetime import datetime, timedelta
# Updated import to use the commons package prefix
from commons.common_functions import analyze_ticker

# Function to get all tickers with average volume filter, no zero-volume days, and at least one record in the last year
def get_all_tickers(engine, min_avg_volume, year_gap):
    # Calculate the date 1 year ago from today
    # one_year_ago = datetime.today().date() - timedelta(days=365)
    year_ago = datetime.today().date() - timedelta(days=365*year_gap)
    
    # Use raw string with %(param)s placeholders for raw_connection compatibility
    query = """
        SELECT ticker
        FROM trading_data
        WHERE ticker <> 'VNINDEX'
        AND ticker IN (
            SELECT ticker 
            FROM trading_data 
            WHERE date >= %(year_ago)s
        )
        GROUP BY ticker
        HAVING AVG(volume) >= %(min_avg_volume)s
        AND ticker NOT IN (
            SELECT ticker 
            FROM trading_data 
            WHERE volume = 0 
            AND date >= %(year_ago)s
        )
    """
    
    params = {"min_avg_volume": min_avg_volume, "year_ago": year_ago}
    
    # Use raw connection to bypass pandas/SQLAlchemy compatibility issues
    conn = engine.raw_connection()
    try:
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()
        
    return df["ticker"].tolist()

# Main page function with volume filter
def suggestion_page(engine):
    st.header("Suggestion Page")
    
    # Input fields
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        day_range = st.number_input("Day Range", min_value=2, value=5, step=1)
    with col2:
        result_day_range = st.number_input("Result Day Range", min_value=1, value=5, step=1)
    with col3:
        volume_threshold = st.number_input("Min Avg Volume (in thousands)", min_value=0, value=1000, step=10)
    with col4:
        year_gap = st.number_input("Year Gap", min_value=1, value=1, step=1)
    
    # Button to trigger analysis
    if st.button("Generate Suggestions"):
        min_avg_volume = volume_threshold * 1000  # Convert thousands to actual volume
        tickers = get_all_tickers(engine, min_avg_volume, year_gap)
        
        if not tickers:
            st.warning("No tickers found with the specified volume threshold.")
            return
            
        st.write(f"Analyzing {len(tickers)} tickers with average volume >= {min_avg_volume} and no zero-volume days in the last year...")
        
        # Parallel processing of tickers
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            # Note: delta_target is no longer passed; it is calculated dynamically per ticker
            future_to_ticker = {executor.submit(analyze_ticker, ticker, day_range, result_day_range, engine): ticker for ticker in tickers}
            for future in concurrent.futures.as_completed(future_to_ticker):
                res = future.result()
                if res is not None: # Filter out failed tickers
                    results.append(res)
        
        # Convert results to DataFrame
        df_results = pd.DataFrame(results)
        
        if df_results.empty or "exchange" not in df_results.columns:
            st.warning("Analysis failed for all selected tickers or no tickers met the criteria.")
            return
        
        # Add Exchange Ranking for sorting (HSX: 3, HNX: 2, UPCOM: 1)
        ex_map = {"HSX": 3, "HNX": 2, "UPCOM": 1}
        df_results["ex_rank"] = df_results["exchange"].map(ex_map).fillna(0)

        # Define Trend Alignment Groups
        bullish_trends = ["Strong Up", "Up", "Overbought (Up)"]
        bearish_trends = ["Strong Down", "Down", "Oversold (Down)"]

        # Table 1: Top 5 by Possibility of Up
        df_up = df_results[df_results["stat_trend"].isin(["Strong Up", "Up"]) & df_results["tech_trend"].isin(bullish_trends)]
        
        top_up_possibility = df_up.sort_values(
            by=["possibility_up", "total_signals", "ex_rank"], 
            ascending=[False, False, False]
        ).head(5)[["ticker", "exchange", "current_delta", "possibility_up", "tech_trend", "total_signals"]]
        
        st.subheader("Top 5 Tickers by Possibility of Up")
        st.dataframe(top_up_possibility, use_container_width=True)
        
        # Table 2: Top 5 by Delta of Up
        top_up_delta = df_up.sort_values(
            by=["max_up_delta", "total_signals", "ex_rank"], 
            ascending=[False, False, False]
        ).head(5)[["ticker", "exchange", "current_delta", "max_up_delta", "tech_trend", "total_signals"]]
        
        st.subheader("Top 5 Tickers by Delta of Up")
        st.dataframe(top_up_delta, use_container_width=True)
        
        # Table 3: Top 5 by Possibility of Down
        df_down = df_results[df_results["stat_trend"].isin(["Strong Down", "Down"]) & df_results["tech_trend"].isin(bearish_trends)]
        
        top_down_possibility = df_down.sort_values(
            by=["possibility_down", "total_signals", "ex_rank"], 
            ascending=[False, False, False]
        ).head(5)[["ticker", "exchange", "current_delta", "possibility_down", "tech_trend", "total_signals"]]

        st.subheader("Top 5 Tickers by Possibility of Down")
        st.dataframe(top_down_possibility, use_container_width=True)
        
        # Table 4: Top 5 by Delta of Down
        top_down_delta = df_down.sort_values(
            by=["min_down_delta", "total_signals", "ex_rank"], 
            ascending=[True, False, False] # min_down_delta ascending means most negative
        ).head(5)[["ticker", "exchange", "current_delta", "min_down_delta", "tech_trend", "total_signals"]]

        st.subheader("Top 5 Tickers by Delta of Down")
        st.dataframe(top_down_delta, use_container_width=True)