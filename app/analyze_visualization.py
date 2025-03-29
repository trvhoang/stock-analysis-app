import streamlit as st
import pandas as pd
from sqlalchemy import text

# Function to analyze price movements
def analyze_price_movement(ticker, validation_days, result_days, delta_target, engine):
    query = text("""
        WITH trading_days AS (
            SELECT date, close,
                   ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date) AS day_rank
            FROM trading_data
            WHERE ticker = :ticker
        ),
        ordered_data AS (
            SELECT date, close,
                   LAG(close, :validation_days) OVER (ORDER BY date) AS prev_close,
                   LEAD(close, :result_days) OVER (ORDER BY date) AS next_close,
                   LAG(date, :validation_days) OVER (ORDER BY date) AS start_date,
                   day_rank,
                   LAG(day_rank, :validation_days) OVER (ORDER BY date) AS prev_day_rank,
                   LEAD(day_rank, :result_days) OVER (ORDER BY date) AS next_day_rank
            FROM trading_days
        ),
        delta_calc AS (
            SELECT date,
                   close,
                   prev_close,
                   next_close,
                   start_date,
                   CASE 
                       WHEN prev_close IS NOT NULL AND (day_rank - prev_day_rank) = :validation_days
                       THEN ROUND(((close - prev_close)::FLOAT / prev_close * 100)::NUMERIC, 2)
                       ELSE NULL 
                   END AS exact_delta,
                   CASE 
                       WHEN next_close IS NOT NULL AND (next_day_rank - day_rank) = :result_days
                       THEN ROUND(((next_close - close)::FLOAT / close * 100)::NUMERIC, 2)
                       ELSE NULL 
                   END AS result_delta,
                   CONCAT(TO_CHAR(start_date, 'DD/MM/YYYY'), ' - ', 
                          TO_CHAR(date, 'DD/MM/YYYY')) AS signal_date_range
            FROM ordered_data
        )
        SELECT 
            date AS event_date,
            exact_delta,
            CASE 
                WHEN result_delta > 0 THEN 'Up'
                WHEN result_delta < 0 THEN 'Down'
                ELSE 'No Change'
            END AS result,
            result_delta,
            signal_date_range
        FROM delta_calc
        WHERE exact_delta IS NOT NULL 
          AND exact_delta BETWEEN :delta_min AND :delta_max
          AND result_delta IS NOT NULL
          AND start_date IS NOT NULL
        ORDER BY date;
    """)
    
    delta_min = delta_target - 1
    delta_max = delta_target + 1
    
    params = {
        "ticker": ticker,
        "validation_days": validation_days,
        "result_days": result_days,
        "delta_min": delta_min,
        "delta_max": delta_max
    }
    
    df = pd.read_sql(query, engine, params=params)
    
    if not df.empty:
        df["no. events"] = range(1, len(df) + 1)
        df = df[["no. events", "exact_delta", "result", "result_delta", "signal_date_range"]]
    else:
        df = pd.DataFrame(columns=["no. events", "exact_delta", "result", "result_delta", "signal_date_range"])
    
    return df

# Function to create analyzed statistical report with No Change
def create_analyzed_statistical_report(df_block):
    if df_block.empty:
        return pd.DataFrame(columns=["result", "possibility of result", "result range", "median"])
    
    result_counts = df_block["result"].value_counts()
    total_events = len(df_block)
    
    up_results = df_block[df_block["result"] == "Up"]["result_delta"]
    down_results = df_block[df_block["result"] == "Down"]["result_delta"]
    no_change_results = df_block[df_block["result"] == "No Change"]["result_delta"]
    
    stats = []
    if "Up" in result_counts:
        up_count = result_counts["Up"]
        up_percentage = round((up_count / total_events) * 100, 2)
        up_range = f"{up_results.min()}% to {up_results.max()}%" if not up_results.empty else "N/A"
        up_median = round(up_results.median(), 2) if not up_results.empty else "N/A"
        stats.append({"result": f"{up_count} times Up", "possibility of result": f"{up_percentage}%", "result range": up_range, "median": f"{up_median}%"})
    
    if "Down" in result_counts:
        down_count = result_counts["Down"]
        down_percentage = round((down_count / total_events) * 100, 2)
        down_range = f"{down_results.min()}% to {down_results.max()}%" if not down_results.empty else "N/A"
        down_median = round(down_results.median(), 2) if not down_results.empty else "N/A"
        stats.append({"result": f"{down_count} times Down", "possibility of result": f"{down_percentage}%", "result range": down_range, "median": f"{down_median}%"})
    
    if "No Change" in result_counts:
        no_change_count = result_counts["No Change"]
        no_change_percentage = round((no_change_count / total_events) * 100, 2)
        no_change_range = f"{no_change_results.min()}% to {no_change_results.max()}%" if not no_change_results.empty else "N/A"
        no_change_median = round(no_change_results.median(), 2) if not no_change_results.empty else "N/A"
        stats.append({"result": f"{no_change_count} times No Change", "possibility of result": f"{no_change_percentage}%", "result range": no_change_range, "median": f"{no_change_median}%"})
    
    return pd.DataFrame(stats)

# Function to provide advice with three options
def provide_advice(ticker, validation_days, result_days, delta_target, df_stats, engine):
    query_latest = text("""
        SELECT date, close,
               LAG(close, :validation_days) OVER (ORDER BY date) AS prev_close
        FROM trading_data
        WHERE ticker = :ticker
        ORDER BY date DESC
        LIMIT :validation_days
    """)
    params = {"ticker": ticker, "validation_days": validation_days}
    df_latest = pd.read_sql(query_latest, engine, params=params)
    
    if len(df_latest) < validation_days or df_latest["prev_close"].iloc[0] is None:
        return "Not enough data to calculate the latest block day delta."
    
    latest_close = df_latest["close"].iloc[0]
    prev_close = df_latest["prev_close"].iloc[0]
    latest_delta = round(((latest_close - prev_close) / prev_close * 100), 2)
    delta_min = delta_target - 1
    delta_max = delta_target + 1
    
    if delta_min <= latest_delta <= delta_max:
        if df_stats.empty:
            return f"Latest {validation_days}-day delta is {latest_delta}%, but no historical data matches the criteria for prediction."
        
        up_row = df_stats[df_stats["result"].str.contains("Up")]
        down_row = df_stats[df_stats["result"].str.contains("Down")]
        no_change_row = df_stats[df_stats["result"].str.contains("No Change")]
        
        up_prob = float(up_row["possibility of result"].iloc[0].replace("%", "")) if not up_row.empty else 0
        down_prob = float(down_row["possibility of result"].iloc[0].replace("%", "")) if not down_row.empty else 0
        no_change_prob = float(no_change_row["possibility of result"].iloc[0].replace("%", "")) if not no_change_row.empty else 0
        
        probs = {"Up": up_prob, "Down": down_prob, "No Change": no_change_prob}
        max_prob = max(probs.values())
        predictions = [k for k, v in probs.items() if v == max_prob]
        
        if len(predictions) == 1:
            prediction = predictions[0]
        else:
            prediction = "Uncertain (multiple equal probabilities)"
        
        return f"Based on historical data, after a {validation_days}-day delta of {latest_delta}%, the stock is more likely to go **{prediction}** in the next {result_days} days."
    else:
        return f"Latest {validation_days}-day delta is {latest_delta}%, which is outside the target range ({delta_min}% to {delta_max}%). No prediction can be made."

# Analyze page logic
def analyze_page(engine):
    st.header("Analyze Page")
    
    col1, col2 = st.columns(2)
    with col1:
        ticker = st.text_input("Ticker Code", value="FPT")
    with col2:
        validation_days = st.number_input("Validation Day Range", min_value=1, value=3, step=1)
    
    col3, col4 = st.columns(2)
    with col3:
        result_days = st.number_input("Result Day Range", min_value=1, value=7, step=1)
    with col4:
        delta_target = st.number_input("Delta Range (%)", value=-3.0, step=0.1)
    
    if st.button("Analyze"):
        ticker = ticker.upper()
        
        df_block = analyze_price_movement(ticker, validation_days, result_days, delta_target, engine)
        df_stats = create_analyzed_statistical_report(df_block)
        
        st.subheader("Block Day and Delta Statistical Report")
        if not df_block.empty:
            st.dataframe(df_block, use_container_width=True)
        else:
            st.write("No events found matching the criteria.")
        
        st.subheader("Analyzed Statistical Report")
        if not df_stats.empty:
            st.dataframe(df_stats, use_container_width=True)
        else:
            st.write("No statistical data available.")
        
        advice = provide_advice(ticker, validation_days, result_days, delta_target, df_stats, engine)
        st.subheader("Advice")
        st.write(advice)