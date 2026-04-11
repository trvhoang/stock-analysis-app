# suggestion_visualization.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
import concurrent.futures
from datetime import datetime, timedelta
# Updated import to use the commons package prefix
from commons.common_functions import analyze_ticker

# Function to get all tickers with average volume filter, no zero-volume days, and at least one record in the last year
def get_all_tickers(engine, min_avg_volume):
    # Calculate the date 1 year ago from today
    one_year_ago = datetime.today().date() - timedelta(days=365)
    
    # Use raw string with %(param)s placeholders for raw_connection compatibility
    query = """
        SELECT ticker
        FROM trading_data
        WHERE ticker <> 'VNINDEX'
        AND ticker IN (
            SELECT ticker 
            FROM trading_data 
            WHERE date >= %(one_year_ago)s
        )
        GROUP BY ticker
        HAVING AVG(volume) >= %(min_avg_volume)s
        AND ticker NOT IN (
            SELECT ticker 
            FROM trading_data 
            WHERE volume = 0 
            AND date >= %(one_year_ago)s
        )
    """
    
    params = {"min_avg_volume": min_avg_volume, "one_year_ago": one_year_ago}
    
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
    col1, col2, col3 = st.columns(3)
    with col1:
        day_range = st.number_input("Day Range", min_value=2, value=5, step=1)
    with col2:
        result_day_range = st.number_input("Result Day Range", min_value=1, value=10, step=1)
    with col3:
        volume_threshold = st.number_input("Min Avg Volume (in thousands)", min_value=0, value=500, step=10)
    
    # Button to trigger analysis
    if st.button("Generate Suggestions"):
        min_avg_volume = volume_threshold * 1000  # Convert thousands to actual volume
        tickers = get_all_tickers(engine, min_avg_volume)
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
        
        # Table 1: Top 5 by Possibility of Up
        top_up_possibility = df_results.nlargest(5, "possibility_up")[["ticker", "current_delta", "possibility_up", "total_signals"]]
        st.subheader("Top 5 Tickers by Possibility of Up")
        st.dataframe(top_up_possibility, use_container_width=True)
        
        # Table 2: Top 5 by Delta of Up
        top_up_delta = df_results.nlargest(5, "max_up_delta")[["ticker", "current_delta", "min_up_delta", "median_up_delta", "max_up_delta", "total_signals"]]
        st.subheader("Top 5 Tickers by Delta of Up")
        st.dataframe(top_up_delta, use_container_width=True)
        
        # Table 3: Top 5 by Possibility of Down
        top_down_possibility = df_results.nlargest(5, "possibility_down")[["ticker", "current_delta", "possibility_down", "total_signals"]]
        st.subheader("Top 5 Tickers by Possibility of Down")
        st.dataframe(top_down_possibility, use_container_width=True)
        
        # Table 4: Top 5 by Delta of Down
        top_down_delta = df_results.nsmallest(5, "min_down_delta")[["ticker", "current_delta", "min_down_delta", "median_down_delta", "max_down_delta", "total_signals"]]
        st.subheader("Top 5 Tickers by Delta of Down")
        st.dataframe(top_down_delta, use_container_width=True)