import streamlit as st
import pandas as pd
from sqlalchemy import text
import concurrent.futures
from common_queries import BASE_DELTA_CALC_CTE, COMMON_DELTA_FILTER_WHERE_CLAUSE, DELTA_UP_THRESHOLD, DELTA_DOWN_THRESHOLD
from common_functions import analyze_ticker
from technical_analysis import fetch_data, calculate_stochastic, calculate_rsi, calculate_ma_cross, calculate_ma_trend, calculate_ma_cross_trend

# Centralized Emoji Map for consistency across advice functions
TREND_EMOJIS = {
    "Strong Up": "📈",
    "Up": "📈",
    "Sideways": "♻️",
    "Down": "📉",
    "Strong Down": "📉",
    "Unknown": "❓",
    "Overbought (Up)": "📈", # Mapped to Strong Bullish behavior
    "Oversold (Down)": "📉"  # Mapped to Strong Bearish behavior
}

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
    
    # Convert SQLAlchemy :param syntax to Psycopg2 %(param)s syntax for raw connection
    query_str = query_str.replace(":ticker", "%(ticker)s")
    query_str = query_str.replace(":validation_days", "%(validation_days)s")
    query_str = query_str.replace(":result_days", "%(result_days)s")
    query_str = query_str.replace(":delta_min", "%(delta_min)s")
    query_str = query_str.replace(":delta_max", "%(delta_max)s")
    query_str = query_str.replace(":up_threshold", "%(up_threshold)s")
    query_str = query_str.replace(":down_threshold", "%(down_threshold)s")
    
    delta_min = float(delta_target - 1)
    delta_max = float(delta_target + 1)
    
    params = {
        "ticker": ticker,
        "validation_days": int(lag_days),
        "result_days": int(result_days),
        "delta_min": delta_min,
        "delta_max": delta_max,
        "up_threshold": float(DELTA_UP_THRESHOLD),
        "down_threshold": float(DELTA_DOWN_THRESHOLD)
    }
    
    # Use a raw connection to bypass pandas/SQLAlchemy compatibility issues
    # This fixes "TypeError: Query must be a string unless using sqlalchemy"
    conn = engine.raw_connection()
    try:
        df = pd.read_sql(query_str, conn, params=params)
    finally:
        conn.close()
    
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
        return f"The current {validation_days}-day delta is {latest_delta}%, but no historical data matches the criteria for prediction.", "Unknown"

    latest_delta = analysis_results["current_delta"]
    up_prob = analysis_results["possibility_up"]
    
    # New logic based on up_prob thresholds
    # Determine the trend key first, then map to emoji
    if up_prob > 70:
        trend = "Strong Up"
    elif 52 < up_prob <= 70:
        trend = "Up"
    elif 48 < up_prob <= 52:
        trend = "Sideways"
    elif 30 < up_prob <= 48:
        trend = "Down"
    else: # up_prob <= 30
        trend = "Strong Down"
    
    emoji = TREND_EMOJIS.get(trend, "")
    prediction = f"{trend} {emoji}"
    
    # BUG FIX: Return tuple (message, trend) to match caller expectation
    return f"Based on historical data, after a {validation_days}-day delta of {latest_delta:.2f}%, the stock is more likely to go **{prediction}** in the next {result_days} days.", trend

# Helper to generate technical advice based on indicator scores
def generate_technical_advice(tech_data):
    if not tech_data:
        return "Not enough data to generate technical advice.", "Unknown", 0

    total_score = 0
    count = 0
    
    # Mapping trend strings to points (0-4 scale)
    # 4: Strong Bullish (Strong Up, Overbought (Up))
    # 3: Bullish (Up)
    # 2: Neutral (Sideways, Unknown)
    # 1: Bearish (Down)
    # 0: Strong Bearish (Strong Down, Oversold (Down))
    trend_map = {
        "Strong Up": 4, "Overbought (Up)": 4,
        "Up": 3,
        "Sideways": 2, "Unknown": 2, "None": 2,
        "Down": 1,
        "Strong Down": 0, "Oversold (Down)": 0
    }

    for item in tech_data:
        # item structure: [index, Name, Value, Trend]
        trend = item[3]
        score = trend_map.get(trend, 2) # Default to 2 (Sideways) if unknown
        total_score += score
        count += 1
    
    if count == 0:
        return "No valid indicators found.", "Unknown", 0

    max_points = count * 4
    percentage = (total_score / max_points) * 100
    
    # Determine advice based on percentage thresholds
    # Use standard keys to fetch emojis later
    if percentage > 70: trend = "Strong Up"
    elif 53 <= percentage <= 70: trend = "Up"
    elif 48 <= percentage < 53: trend = "Sideways"
    elif 30 <= percentage < 48: trend = "Down"
    else: trend = "Strong Down" # < 30
    
    emoji = TREND_EMOJIS.get(trend, "")
    advice_display = f"{trend} {emoji}"
        
    display_string = f"Based on {count} technical indicators, the overall trend is **{advice_display}** (Score: {percentage:.0f}%)."
    
    # Return raw trend key for matrix lookup in the next step
    return display_string, trend, percentage

# Helper to generate final advice by combining statistical and technical trends
def generate_final_advice(ticker, statistical_trend, technical_trend):
    # The matrix from the user prompt
    final_advice_matrix = {
        # Rows: Statistical Advice
        "Strong Up": {
            # Columns: Technical Advice
            "Strong Up": "Strong Up", "Up": "Up", "Sideways": "Up", "Down": "Unknown", "Strong Down": "Unknown"
        },
        "Up": {
            "Strong Up": "Up", "Up": "Up", "Sideways": "Sideways", "Down": "Unknown", "Strong Down": "Unknown"
        },
        "Sideways": {
            "Strong Up": "Up", "Up": "Sideways", "Sideways": "Unknown", "Down": "Down", "Strong Down": "Down"
        },
        "Down": {
            "Strong Up": "Unknown", "Up": "Unknown", "Sideways": "Unknown", "Down": "Down", "Strong Down": "Strong Down"
        },
        "Strong Down": {
            "Strong Up": "Unknown", "Up": "Unknown", "Sideways": "Unknown", "Down": "Strong Down", "Strong Down": "Strong Down"
        }
    }

    # Lookup the result
    final_outlook = final_advice_matrix.get(statistical_trend, {}).get(technical_trend, "Unknown")
    
    # Use centralized emoji map
    emoji = TREND_EMOJIS.get(final_outlook, "❓")
    final_advice_with_emoji = f"{final_outlook} {emoji}"

    # Provide a more descriptive text
    if final_outlook == "Strong Up":
        text = "Both statistical and technical analyses are strongly bullish."
    elif final_outlook == "Up":
        text = "Both analyses point towards a bullish outlook."
    elif final_outlook == "Sideways":
        text = "The analyses show mixed signals, suggesting a sideways movement."
    elif final_outlook == "Down":
        text = "Both analyses point towards a bearish outlook."
    elif final_outlook == "Strong Down":
        text = "Both statistical and technical analyses are strongly bearish."
    else: # Unknown
        text = "The statistical and technical signals are conflicting, leading to an uncertain outlook."

    return f"**{ticker}'s trend: {final_advice_with_emoji}**. {text}"    
    return f"**{ticker}'s trend: {final_advice_with_emoji}**. {text}"

# Wrapper function for Portfolio Analysis (Runs both Stats and Tech)
def analyze_portfolio_ticker(ticker, validation_days, result_days, engine):
    # 1. Statistical Analysis
    stats_res = analyze_ticker(ticker, validation_days, result_days, engine)
    if not stats_res:
        return None

    # Determine Statistical Trend & Dominant Stats
    up_prob = stats_res["possibility_up"]
    down_prob = stats_res["possibility_down"]
    
    # Logic for Final Advice key (matching provide_advice thresholds)
    if up_prob > 70: stat_key = "Strong Up"
    elif 52 < up_prob <= 70: stat_key = "Up"
    elif 48 < up_prob <= 52: stat_key = "Sideways"
    elif 30 < up_prob <= 48: stat_key = "Down"
    else: stat_key = "Strong Down"

    if up_prob >= down_prob:
        stat_trend = "up" # Lowercase as per example
        possibility_val = up_prob
        possibility_str = f"{up_prob:.2f} (up)"
        if stats_res["min_up_delta"] is None:
             delta_str = "N/A"
        else:
             delta_str = f"{stats_res['min_up_delta']:.2f} {stats_res['median_up_delta']:.2f} {stats_res['max_up_delta']:.2f} (up)"
    else:
        stat_trend = "down" # Lowercase as per example
        possibility_val = down_prob
        possibility_str = f"{down_prob:.2f} (down)"
        if stats_res["min_down_delta"] is None:
             delta_str = "N/A"
        else:
             # For down, show max (least negative) -> median -> min (most negative)
             delta_str = f"{stats_res['max_down_delta']:.2f} {stats_res['median_down_delta']:.2f} {stats_res['min_down_delta']:.2f} (down)"

    # 2. Technical Analysis
    if validation_days <= 5:
        tech_timeframe = 'Day'
        short_ma, long_ma = 5, 10
    else:
        tech_timeframe = 'Week'
        short_ma, long_ma = 4, 12
        
    df_tech = fetch_data(ticker, tech_timeframe, 100, engine)
    tech_data = []
    
    if not df_tech.empty:
        # Stochastic
        # Use the same robust check as the Ticker Analyze tab
        df_tech, stoch_trend = calculate_stochastic(df_tech)
        if '%K' in df_tech.columns and '%D' in df_tech.columns:
            tech_data.append([0, "Stochastic", "", stoch_trend])
        
        # RSI
        df_tech, rsi_trend = calculate_rsi(df_tech, length=14)
        if 'RSI_14' in df_tech.columns:
            tech_data.append([1, "RSI14", "", rsi_trend])
            
        # MA & Cross
        df_tech = calculate_ma_cross(df_tech, [(short_ma, long_ma)])
        short_col = f'SMA_{short_ma}'
        long_col = f'SMA_{long_ma}'
        signal_col = f'cross_{short_ma}_{long_ma}'

        if short_col in df_tech.columns and long_col in df_tech.columns:
            ma_spread_trend = calculate_ma_trend(df_tech, short_col, long_col)
            tech_data.append([2, "MA", "", ma_spread_trend])

        # The MA Cross signal is now checked separately for robustness
        if signal_col in df_tech.columns:
            ma_cross_event_trend = calculate_ma_cross_trend(df_tech, signal_col)
            tech_data.append([3, "MA cross", "", ma_cross_event_trend]) 

    # Generate Score
    _, tech_trend_key, tech_score = generate_technical_advice(tech_data)
    
    # Map tech trend key to lowercase for display consistency
    tech_trend_display = tech_trend_key.lower() if tech_trend_key != "Unknown" else "unknown"

    return {
        "ticker": ticker,
        "statistical trend": stat_trend,
        "stat_trend_key": stat_key, 
        "possibility_sort": possibility_val,
        "possibility": possibility_str,
        "delta": delta_str,
        "technical trend": tech_trend_display,
        "tech_trend_key": tech_trend_key,
        "score": f"{tech_score:.0f}%"
    }

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
                st.error("Not enough data to calculate the latest signal or run analysis. Check container logs for details.")
                return

            latest_delta = analysis_results["current_delta"]
            start_date = analysis_results["start_date"]
            end_date = analysis_results["end_date"]

            # --- 1. Current X-Day Delta (Signal) ---
            date_range_str = f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
            st.metric(label=f"Current {validation_days}-Day Delta (Signal): {date_range_str}", value=f"{latest_delta:.2f}%")

            # Calculate detailed event list (used for Step 2.3)
            df_block = analyze_price_movement(ticker, validation_days, result_days, latest_delta, engine)
            
            # Generate Statistical Advice (used for Step 2.2 and Final Advice)
            statistical_advice_display, statistical_trend = provide_advice(validation_days, result_days, analysis_results)
            
            # --- 2.1 Analyzed Statistical Report ---
            # Re-creating report from analysis_results for display
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

            # --- 2.2 Statistical Advice ---
            st.subheader("Statistical Advice")
            st.write(statistical_advice_display)

            # --- 2.3 Block Day and Delta Statistical Report ---
            # Collapsed by default to declutter UI
            with st.expander("Block Day and Delta Statistical Report", expanded=False):
                if not df_block.empty:
                    st.dataframe(df_block, use_container_width=True)
                else:
                    st.write("No events found matching the criteria.")
            
            # --- 3.1 Technical Report ---
            st.subheader("Technical Report")
            
            # Initialize tech_data list
            tech_data = []
            
            # Logic for Timeframe and MA Pair selection based on validation_days
            # If looking at short term (<15 days), use Daily data and 5-10 MA
            # If looking at longer term (>5 days), use Weekly data and 4-12 MA
            if validation_days < 15:
                tech_timeframe = 'Day'
                short_ma, long_ma = 5, 10
            else:
                tech_timeframe = 'Week'
                short_ma, long_ma = 4, 12
            
            # Fetch data for technical analysis (default lookback 100 as per requirement)
            # This ensures we have enough history for accurate indicator calculation
            df_tech = fetch_data(ticker, tech_timeframe, 100, engine)
            
            if not df_tech.empty:
                # 1. Stochastic Calculation
                df_tech, stoch_trend = calculate_stochastic(df_tech)
                if '%K' in df_tech.columns and '%D' in df_tech.columns:
                    k_val = df_tech['%K'].iloc[-1]
                    d_val = df_tech['%D'].iloc[-1]
                    tech_data.append([0, "Stochastic", f"%K: {k_val:.1f} - %D: {d_val:.1f}", stoch_trend])
                
                # 2. RSI Calculation
                df_tech, rsi_trend = calculate_rsi(df_tech, length=14)
                if 'RSI_14' in df_tech.columns:
                    rsi_val = df_tech['RSI_14'].iloc[-1]
                    tech_data.append([1, "RSI14", f"{rsi_val:.1f}", rsi_trend])
                
                # 3. MA Calculation
                df_tech = calculate_ma_cross(df_tech, [(short_ma, long_ma)])
                short_col = f'SMA_{short_ma}'
                long_col = f'SMA_{long_ma}'
                
                if short_col in df_tech.columns and long_col in df_tech.columns:
                    s_val = df_tech[short_col].iloc[-1]
                    l_val = df_tech[long_col].iloc[-1]
                    # Get trend based on spread/reversal
                    ma_spread_trend = calculate_ma_trend(df_tech, short_col, long_col)
                    tech_data.append([2, "MA", f"SMA_{short_ma}: {s_val:.1f} - SMA_{long_ma}: {l_val:.1f}", ma_spread_trend])
                
                # 4. MA Cross Calculation
                # Check for recent cross events (Golden/Death)
                signal_col = f'cross_{short_ma}_{long_ma}'
                if signal_col in df_tech.columns:
                    # Get trend based on cross events
                    ma_cross_event_trend = calculate_ma_cross_trend(df_tech, signal_col)

                    # Get last 3 non-zero signals to show history
                    recent_signals = df_tech[df_tech[signal_col] != 0][signal_col].tail(3).tolist()
                    # Map 1/-1 to Golden/Death for readability
                    signal_map = {1: "Golden", -1: "Death"}
                    signal_str = " - ".join([signal_map.get(s, "") for s in recent_signals]) if recent_signals else "None"
                    tech_data.append([3, "MA cross", signal_str, ma_cross_event_trend])
            
            if tech_data:
                df_tech_report = pd.DataFrame(tech_data, columns=["#", "Indicator name", "value", "trend"])
                st.dataframe(df_tech_report, use_container_width=True, hide_index=True)
            elif not tech_data and df_tech.empty:
                st.info(f"Not enough data to generate Technical Report for timeframe {tech_timeframe}.")
            
            # Generate Technical Advice
            technical_advice_display, technical_trend, _ = generate_technical_advice(tech_data)

            # --- 3.2 Technical Advice ---
            st.subheader("Technical Advice")
            st.write(technical_advice_display)
            
            # Generate Final Advice using trends from previous steps
            final_advice_display = generate_final_advice(ticker, statistical_trend, technical_trend)

            # --- 4. Final Advice ---
            st.subheader("Final Advice")
            st.write(final_advice_display)

            # --- 5. Explanation of 4.Final Advice ---
            st.subheader("Explanation")
            # Placeholder as requested
            st.info("Detailed explanation of the final advice calculation will be added here in a future update.")

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
                    # UPDATED: Use the new wrapper function
                    future_to_ticker = {executor.submit(analyze_portfolio_ticker, ticker, p_validation_days, p_result_days, engine): ticker for ticker in tickers}
                    for future in concurrent.futures.as_completed(future_to_ticker):
                        res = future.result()
                        if res is not None:
                            results.append(res)
                
                if results:
                    df_results = pd.DataFrame(results)
                    
                    # Add "No" column (1-based index)
                    df_results.insert(0, "No", range(1, len(df_results) + 1))
                    
                    # Add Emojis to Statistical Trend
                    # Map "up" -> "Up 📈", "down" -> "Down 📉"
                    df_results["statistical trend"] = df_results["statistical trend"].apply(
                        lambda x: f"{x} {TREND_EMOJIS.get(x.title() if x else '', '')}"
                    )

                    # Add Emojis to Technical Trend
                    df_results["technical trend"] = df_results.apply(
                        lambda row: f"{row['technical trend']} {TREND_EMOJIS.get(row['tech_trend_key'], '')}", axis=1
                    )

                    # Generate Final Advice
                    # We need the raw capitalized keys for the matrix lookup in generate_final_advice   
                    df_results["final advice"] = df_results.apply(
                        lambda row: generate_final_advice(row["ticker"], row["stat_trend_key"], row["tech_trend_key"]).split('.')[0].replace("**Final Outlook: ", "").replace("**", ""), 
                        axis=1
                    )

                    # Columns requested
                    cols = ["No", "ticker", "statistical trend", "possibility", "delta", "technical trend", "score", "final advice"]
                    st.dataframe(df_results[cols], use_container_width=True, hide_index=True)
                else:
                    st.write("No valid results found for the given tickers.")