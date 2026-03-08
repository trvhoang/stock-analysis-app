import streamlit as st
import pandas as pd
from sqlalchemy import text
import concurrent.futures
from common_queries import BASE_DELTA_CALC_CTE, COMMON_DELTA_FILTER_WHERE_CLAUSE, DELTA_UP_THRESHOLD, DELTA_DOWN_THRESHOLD
from common_functions import analyze_ticker

# Function to analyze price movements
def analyze_price_movement(ticker, validation_days, result_days, delta_target, engine):
    if validation_days < 2:
        return pd.DataFrame(columns=["no. events", "exact_delta", "result", "result_delta", "signal_date_range"])

    lag_days = validation_days - 1
    query_str = BASE_DELTA_CALC_CTE + """
        SELECT
            date AS event_date,
            exact_delta,
            CASE 
                WHEN result_delta > :up_threshold THEN 'Up'
                WHEN result_delta < :down_threshold THEN 'Down'
                ELSE 'No Change'
            END AS result,
            result_delta, signal_date_range
        FROM delta_calc
    """ + COMMON_DELTA_FILTER_WHERE_CLAUSE + """
        ORDER BY date;
    """
    query = text(query_str)
    
    delta_min = delta_target - 1
    delta_max = delta_target + 1
    
    params = {
        "ticker": ticker,
        "validation_days": lag_days,
        "result_days": result_days,
        "delta_min": delta_min,
        "delta_max": delta_max,
        "up_threshold": DELTA_UP_THRESHOLD,
        "down_threshold": DELTA_DOWN_THRESHOLD
    }
    
    df = pd.read_sql(query, engine, params=params)
    
    if not df.empty:
        df["no. events"] = range(1, len(df) + 1)
        # Round numerical columns to 2 decimal places for cleaner display
        df["exact_delta"] = df["exact_delta"].round(2)
        df["result_delta"] = df["result_delta"].round(2)
        df = df[["no. events", "exact_delta", "result", "result_delta", "signal_date_range"]]
    else:        
        df = pd.DataFrame(columns=["no. events", "exact_delta", "result", "result_delta", "signal_date_range"])
    
    return df

# Function to provide advice with three options
def provide_advice(validation_days, result_days, analysis_results):
    # analysis_results is the dictionary from analyze_ticker
    if analysis_results is None or analysis_results["total_signals"] == 0:
        latest_delta = analysis_results.get('current_delta', 'N/A') if analysis_results else 'N/A'
        return f"The current {validation_days}-day delta is {latest_delta}%, but no historical data matches the criteria for prediction."

    latest_delta = analysis_results["current_delta"]
    up_prob = analysis_results["possibility_up"]
    down_prob = analysis_results["possibility_down"]
    
    # Calculate no_change_prob from the others
    no_change_prob = round(100 - up_prob - down_prob, 2)

    probs = {"Up": up_prob, "Down": down_prob, "No Change": no_change_prob}
    
    # Find the outcome with the highest probability
    prediction = max(probs, key=probs.get)
    max_prob_val = probs[prediction]

    # Count how many outcomes share the max probability to check for ties
    tie_count = sum(1 for prob in probs.values() if prob == max_prob_val)

    if tie_count > 1:
        prediction = "Uncertain (multiple equal probabilities)"
    
    return f"Based on historical data, after a {validation_days}-day delta of {latest_delta:.2f}%, the stock is more likely to go **{prediction}** in the next {result_days} days."

# Analyze page logic
def analyze_page(engine):
    st.header("Analyze Page")
    
    tab1, tab2 = st.tabs(["Ticker Analyze", "Portfolio Analyze"])
    
    with tab1:
        col1, col2, col3 = st.columns(3)
        with col1:
            ticker = st.text_input("Ticker Code", value="FPT")
        with col2:
            validation_days = st.number_input("Validation Day Range", min_value=2, value=5, step=1)
        with col3:
            result_days = st.number_input("Result Day Range", min_value=1, value=10, step=1)
        
        if st.button("Analyze"):
            ticker = ticker.upper()
            
            # 1. Get summary stats, current delta, and date range from the common function
            analysis_results = analyze_ticker(ticker, validation_days, result_days, engine)
            
            if analysis_results is None:
                st.error("Not enough data to calculate the latest signal or run analysis.")
                return

            latest_delta = analysis_results["current_delta"]
            start_date = analysis_results["start_date"]
            end_date = analysis_results["end_date"]

            # 2. Display current delta
            date_range_str = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
            st.metric(label=f"Current {validation_days}-Day Delta (Signal): {date_range_str}", value=f"{latest_delta:.2f}%")

            # 3. Get detailed event list for display
            df_block = analyze_price_movement(ticker, validation_days, result_days, latest_delta, engine)
            
            # 4. Generate and display advice
            advice = provide_advice(validation_days, result_days, analysis_results)
            st.subheader("Advice")
            st.write(advice)

            # 5. Display statistical report (re-creating it from analysis_results for display)
            st.subheader("Analyzed Statistical Report")
            if analysis_results["total_signals"] > 0:
                up_prob = analysis_results['possibility_up']
                down_prob = analysis_results['possibility_down']
                no_change_prob = round(100 - up_prob - down_prob, 2)
                
                # Helper to format numbers to 2 decimal places safely
                fmt = lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else "N/A"

                up_count = round(analysis_results['total_signals'] * (up_prob / 100))
                down_count = round(analysis_results['total_signals'] * (down_prob / 100))
                no_change_count = analysis_results['total_signals'] - up_count - down_count

                stats_data = []
                if up_count > 0:
                    stats_data.append({
                        "result": f"{up_count} times Up", 
                        "possibility of result": f"{fmt(up_prob)}%", 
                        "result range": f"{fmt(analysis_results.get('min_up_delta'))}% to {fmt(analysis_results.get('max_up_delta'))}%", 
                        "median": f"{fmt(analysis_results.get('median_up_delta'))}%"
                    })
                if down_count > 0:
                     stats_data.append({
                        "result": f"{down_count} times Down", 
                        "possibility of result": f"{fmt(down_prob)}%", 
                        "result range": f"{fmt(analysis_results.get('min_down_delta'))}% to {fmt(analysis_results.get('max_down_delta'))}%", 
                        "median": f"{fmt(analysis_results.get('median_down_delta'))}%"
                    })
                if no_change_count > 0:
                    stats_data.append({
                        "result": f"{no_change_count} times No Change", 
                        "possibility of result": f"{fmt(no_change_prob)}%", 
                        "result range": "N/A", # This info is not in analyze_ticker
                        "median": "N/A" # This info is not in analyze_ticker
                    })
                
                df_stats_display = pd.DataFrame(stats_data)
                st.dataframe(df_stats_display, use_container_width=True)
            else:
                st.write("No statistical data available.")

            # 6. Display detailed event list
            st.subheader("Block Day and Delta Statistical Report")
            if not df_block.empty:
                st.dataframe(df_block, use_container_width=True)
            else:
                st.write("No events found matching the criteria.")

    with tab2:
        st.subheader("Portfolio Analysis")
        portfolio_input = st.text_area("Enter Tickers (comma separated)", value="FPT, PAT, DGW, CAP, VCB, REE, VCI")
        
        col1, col2 = st.columns(2)
        with col1:
            p_validation_days = st.number_input("Validation Day Range", min_value=2, value=5, step=1, key="p_val")
        with col2:
            p_result_days = st.number_input("Result Day Range", min_value=1, value=10, step=1, key="p_res")
            
        if st.button("Analyze Portfolio"):
            tickers = [t.strip().upper() for t in portfolio_input.split(",") if t.strip()]
            
            if not tickers:
                st.warning("Please enter at least one ticker.")
            else:
                st.write(f"Analyzing {len(tickers)} tickers...")
                results = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    future_to_ticker = {executor.submit(analyze_ticker, ticker, p_validation_days, p_result_days, engine): ticker for ticker in tickers}
                    for future in concurrent.futures.as_completed(future_to_ticker):
                        res = future.result()
                        if res is not None:
                            results.append(res)
                
                if results:
                    df_results = pd.DataFrame(results)
                    
                    # Round main numerical columns to 2 decimal places for display
                    cols_to_round = ["current_delta", "possibility_up", "possibility_down"]
                    for col in cols_to_round:
                        if col in df_results.columns:
                            df_results[col] = df_results[col].astype(float).round(2)

                    # Logic to format up_delta: min  median  max (separated by 2 tabs)
                    # Hide if possibility_up < possibility_down
                    def format_up_delta(row):
                        if row["possibility_up"] < row["possibility_down"]:
                            return ""
                        if pd.isna(row["min_up_delta"]):
                            return ""
                        # Format: min<2 tabs>median<2 tabs>max, rounded to 2 decimal places
                        return f"{float(row['min_up_delta']):.2f}\t\t{float(row['median_up_delta']):.2f}\t\t{float(row['max_up_delta']):.2f}"

                    # Logic to format down_delta: max  median  min (separated by 2 tabs)
                    # Hide if possibility_up > possibility_down
                    def format_down_delta(row):
                        if row["possibility_up"] > row["possibility_down"]:
                            return ""
                        if pd.isna(row["min_down_delta"]):
                            return ""
                        # Format: max<2 tabs>median<2 tabs>min, rounded to 2 decimal places
                        return f"{float(row['max_down_delta']):.2f}\t\t{float(row['median_down_delta']):.2f}\t\t{float(row['min_down_delta']):.2f}"

                    df_results["up_delta"] = df_results.apply(format_up_delta, axis=1)
                    df_results["down_delta"] = df_results.apply(format_down_delta, axis=1)

                    # Reorder columns for better readability
                    cols = ["ticker", "current_delta", "possibility_up", "up_delta", "possibility_down", "down_delta", "total_signals"]
                    # Ensure all columns exist (in case of empty results or schema changes)
                    cols = [c for c in cols if c in df_results.columns]
                    st.dataframe(df_results[cols], use_container_width=True)
                else:
                    st.write("No valid results found for the given tickers.")