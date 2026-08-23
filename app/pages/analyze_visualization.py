import streamlit as st
import pandas as pd
from sqlalchemy import text
import concurrent.futures
from commons.common_queries import BASE_DELTA_CALC_CTE, COMMON_DELTA_FILTER_WHERE_CLAUSE, DELTA_UP_THRESHOLD, DELTA_DOWN_THRESHOLD
from commons.common_functions import (
    analyze_ticker, provide_advice, generate_technical_advice, 
    generate_final_advice, TREND_EMOJIS
)
# Import neighbor module using the pages package prefix
from commons.technical_analysis import (
    fetch_data, calculate_stochastic, calculate_rsi, calculate_ma_cross, 
    calculate_ma_trend, calculate_ma_cross_trend, 
    calculate_stochastic_trend, calculate_rsi_trend,
    calculate_dimension_technical_score, calculate_adx, get_latest_adx_value,
)
from commons.price_utils import PRICE_OUTPUT_EXPORT, prepare_price_for_output

EXPORT_RANGE_UNITS = ("days", "months", "years")
EXPORT_VISIBLE_KEY = "analyze_export_visible"
EXPORT_CSV_KEY = "analyze_export_csv"
EXPORT_FILENAME_KEY = "analyze_export_filename"
EXPORT_FORM_LABEL = "Export form"


def build_historical_context_query():
    """Return the full-history query with raw-connection bindings."""
    query = text("""
        SELECT date, open, high, low, close, volume
        FROM trading_data
        WHERE ticker = :ticker
        ORDER BY date ASC
    """)
    return str(query).replace(":ticker", "%(ticker)s")


def build_historical_technical_score_table(df_full, short_ma, long_ma):
    """Precompute as-of historical scores once for binary-search lookups.

    Indicator values are calculated on the complete chronological frame, then
    each row's score is derived from only the bounded context required by the
    existing classifiers. This preserves historical output while avoiding a
    full ``df_full.iloc[:idx + 1]`` scan for every signal event.
    """
    working_df = df_full.copy()
    score_name = "Technical score"
    if working_df.empty:
        return pd.Series(dtype=float, index=working_df.index, name=score_name)

    working_df, _ = calculate_stochastic(working_df)
    working_df, _ = calculate_rsi(working_df, length=14)
    working_df = calculate_ma_cross(working_df, [(short_ma, long_ma)])
    short_col = f"SMA_{short_ma}"
    long_col = f"SMA_{long_ma}"
    cross_col = f"cross_{short_ma}_{long_ma}"
    scores = []
    recent_crosses = []

    for index in range(len(working_df)):
        signal = working_df[cross_col].iloc[index]
        if signal in (1, -1):
            recent_crosses = (recent_crosses + [int(signal)])[-3:]

        # Keep the existing minimum-history behavior and still collect cross
        # events above so later rows see the same historical event sequence.
        if index < 10:
            scores.append(None)
            continue

        # RSI reads at most 30 rows; MA reversal reads at most 4 rows. The
        # Stochastic classifier's non-neutral branches depend only on its
        # latest values; its aggregate branch also returns Sideways, so one
        # current row preserves the existing final classification.
        stoch_context = working_df.iloc[index:index + 1]
        rsi_context = working_df.iloc[max(0, index - 29):index + 1]
        ma_context = working_df.iloc[max(0, index - 3):index + 1]
        cross_context = pd.DataFrame({cross_col: recent_crosses})
        trends = [
            calculate_stochastic_trend(stoch_context),
            calculate_rsi_trend(rsi_context),
            calculate_ma_trend(ma_context, short_col, long_col),
            calculate_ma_cross_trend(cross_context, cross_col),
        ]
        trend_points = {
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
        total_points = sum(trend_points.get(trend, 2) for trend in trends)
        scores.append(round((total_points / 16) * 100, 2))

    return pd.Series(scores, index=working_df.index, name=score_name)


def validate_export_inputs(ticker, range_value, range_unit):
    """Return normalized export inputs or a user-safe validation message."""
    normalized_ticker = str(ticker or "").strip().upper()
    if not normalized_ticker:
        return None, "Ticker code is required."
    if not normalized_ticker.isalnum():
        return None, "Ticker code must contain only letters and numbers."

    try:
        numeric_range = float(range_value)
    except (TypeError, ValueError):
        return None, "Time range must be a positive whole number."
    if not numeric_range.is_integer() or numeric_range <= 0:
        return None, "Time range must be a positive whole number."

    normalized_unit = str(range_unit or "").strip().lower()
    if normalized_unit not in EXPORT_RANGE_UNITS:
        return None, "Time unit must be days, months, or years."

    return {
        "ticker": normalized_ticker,
        "range_value": int(numeric_range),
        "range_unit": normalized_unit,
    }, None


def fetch_export_history(ticker, range_value, range_unit, engine):
    """Fetch only the requested calendar-bounded trading rows for export."""
    values, error = validate_export_inputs(ticker, range_value, range_unit)
    if error:
        raise ValueError(error)

    # The latest-date CTE keeps the range anchored to available data while the
    # ticker/date predicates allow PostgreSQL to use the time-series index.
    query = text("""
        WITH latest_record AS (
            SELECT MAX(date) AS latest_date
            FROM trading_data
            WHERE ticker = %(ticker)s
        )
        SELECT
            td.ticker,
            td.date AS trading_date,
            td.open,
            td.high,
            td.low,
            td.close,
            td.volume
        FROM trading_data AS td
        CROSS JOIN latest_record
        WHERE td.ticker = %(ticker)s
          AND td.date BETWEEN latest_record.latest_date - (
              CASE %(range_unit)s
                  WHEN 'days' THEN %(range_value)s * INTERVAL '1 day'
                  WHEN 'months' THEN %(range_value)s * INTERVAL '1 month'
                  WHEN 'years' THEN %(range_value)s * INTERVAL '1 year'
              END
          ) AND latest_record.latest_date
        ORDER BY td.date ASC
    """)
    params = {
        "ticker": values["ticker"],
        "range_value": values["range_value"],
        "range_unit": values["range_unit"],
    }

    conn = engine.raw_connection()
    try:
        # Raw connections require the SQL text string for pandas compatibility.
        return pd.read_sql(query.text, conn, params=params)
    finally:
        conn.close()


def format_export_dataframe(df, include_percentage_change, include_ohlc_volume=False):
    """Build stable export columns while preserving stored price values."""
    source_columns = ["ticker", "trading_date", "close"]
    columns = ["ticker", "trading_date"]
    if include_ohlc_volume:
        source_columns = [
            "ticker",
            "trading_date",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
        columns.extend(
            [
                "open_price",
                "high_price",
                "low_price",
                "close_price",
                "trading_volume",
            ]
        )
    else:
        columns.append("close_price")
    if include_percentage_change:
        columns.append("percentage_change")

    if df.empty:
        return pd.DataFrame(columns=columns)

    export_df = (
        df[source_columns]
        .copy()
        .sort_values("trading_date")
        .reset_index(drop=True)
    )

    for price_column in ("open", "high", "low", "close"):
        if price_column in export_df:
            price_values = export_df.pop(price_column)
            price_values = prepare_price_for_output(
                price_values, PRICE_OUTPUT_EXPORT
            )
            export_df[f"{price_column}_price"] = price_values
    if "volume" in export_df:
        export_df["trading_volume"] = export_df.pop("volume")

    if include_percentage_change:
        # Chronological order makes first row intentionally have no prior value.
        export_df["percentage_change"] = export_df["close_price"].pct_change().mul(100).round(2)

    return export_df[columns]


def build_export_filename(ticker, range_value, range_unit):
    """Return deterministic CSV name for one export request."""
    return f"{ticker}_{range_value}_{range_unit}_price_history.csv"


def get_export_form_container():
    """Use Streamlit's native expander for accessible form collapse/expand."""
    return st.expander(EXPORT_FORM_LABEL, expanded=True)


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
        # Include event_date internally to allow joining with historical technical indicator data
        df = df[["no. events", "event_date", "exact_delta", "result", "result_delta", "signal_date_range"]]
    else:        
        # Ensure consistent column structure even on empty results
        df = pd.DataFrame(columns=["no. events", "event_date", "exact_delta", "result", "result_delta", "signal_date_range"])
    
    return df

def _classify_statistical_trend(possibility_up, possibility_down):
    """Classify directional evidence without treating no-change as bearish."""
    if possibility_up > 70:
        return "Strong Up"
    if 53 <= possibility_up <= 70:
        return "Up"
    if possibility_down > 70:
        return "Strong Down"
    if 53 <= possibility_down <= 70:
        return "Down"
    # Down uses direct possibility_down evidence, not low possibility_up.
    return "Sideways"


# Function to provide advice with three options
def provide_advice(validation_days, result_days, analysis_results):
    # analysis_results is the dictionary from analyze_ticker
    if analysis_results is None or analysis_results["total_signals"] == 0:
        latest_delta = analysis_results.get('current_delta', 'N/A') if analysis_results else 'N/A'
        return f"The current {validation_days}-day delta is {latest_delta}%, but no historical data matches the criteria for prediction.", "Unknown"

    latest_delta = analysis_results["current_delta"]
    up_prob = analysis_results["possibility_up"]
    down_prob = analysis_results["possibility_down"]

    # Determine the trend key first, then map to emoji.
    trend = _classify_statistical_trend(up_prob, down_prob)
    
    emoji = TREND_EMOJIS.get(trend, "")
    prediction = f"{trend} {emoji}"
    
    # BUG FIX: Return tuple (message, trend) to match caller expectation
    return f"Based on historical data, after a {validation_days}-day delta of {latest_delta:.2f}%, the stock is more likely to go **{prediction}** in the next {result_days} days.", trend

# Helper to generate technical advice based on indicator scores
def generate_technical_advice(tech_data, adx_value=None):
    if not tech_data:
        return "Not enough data to generate technical advice.", "Unknown", 0

    percentage, _, count = calculate_dimension_technical_score(
        tech_data, adx_value=adx_value
    )
    if count == 0:
        return "No valid indicators found.", "Unknown", 0

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
    elif 53 <= up_prob <= 70: stat_key = "Up"
    elif 48 <= up_prob < 53: stat_key = "Sideways"
    elif 30 <= up_prob < 48: stat_key = "Down"
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

    # 2. Reuse the current technical snapshot produced by analyze_ticker.
    # This keeps portfolio analysis bounded to one technical fetch/calculation
    # per ticker while preserving the existing output columns and score keys.
    tech_data = stats_res.get("technical_signals", [])
    adx_value = stats_res.get("technical_adx_value")

    # Generate Score
    _, tech_trend_key, tech_score = generate_technical_advice(
        tech_data, adx_value=adx_value
    )
    
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

        st.session_state.setdefault(EXPORT_VISIBLE_KEY, False)
        st.session_state.setdefault(EXPORT_CSV_KEY, None)
        st.session_state.setdefault(EXPORT_FILENAME_KEY, None)

        if st.button("Export", key="analyze_export_button"):
            st.session_state[EXPORT_VISIBLE_KEY] = True
            st.session_state[EXPORT_CSV_KEY] = None
            st.session_state[EXPORT_FILENAME_KEY] = None

        if st.session_state[EXPORT_VISIBLE_KEY]:
            with get_export_form_container():
                with st.form("analyze_export_form"):
                    export_ticker = st.text_input("Export Ticker Code", value=ticker)
                    export_range = st.number_input(
                        "Export Time Range", min_value=1, value=30, step=1
                    )
                    export_unit = st.selectbox("Export Time Unit", EXPORT_RANGE_UNITS)
                    include_percentage_change = st.checkbox("Include Percentage Change")
                    include_ohlc_volume = st.checkbox(
                        "Include OHLC Prices and Trading Volume"
                    )
                    export_submitted = st.form_submit_button("Prepare CSV")

            if export_submitted:
                st.session_state[EXPORT_CSV_KEY] = None
                st.session_state[EXPORT_FILENAME_KEY] = None
                try:
                    export_values, export_error = validate_export_inputs(
                        export_ticker, export_range, export_unit
                    )
                    if export_error:
                        st.error(export_error)
                    else:
                        history_df = fetch_export_history(
                            export_values["ticker"],
                            export_values["range_value"],
                            export_values["range_unit"],
                            engine,
                        )
                        export_df = format_export_dataframe(
                            history_df,
                            include_percentage_change,
                            include_ohlc_volume,
                        )
                        if export_df.empty:
                            st.warning("No trading history found for the requested range.")
                        else:
                            st.session_state[EXPORT_CSV_KEY] = export_df.to_csv(
                                index=False
                            ).encode("utf-8")
                            st.session_state[EXPORT_FILENAME_KEY] = build_export_filename(
                                export_values["ticker"],
                                export_values["range_value"],
                                export_values["range_unit"],
                            )
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Unable to export price history. Please try again later.")

            if st.session_state[EXPORT_CSV_KEY]:
                st.download_button(
                    "Download CSV",
                    data=st.session_state[EXPORT_CSV_KEY],
                    file_name=st.session_state[EXPORT_FILENAME_KEY],
                    mime="text/csv",
                    key="analyze_export_download",
                )
        
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

            # --- NEW: Historical Technical Context Analysis ---
            # We calculate the technical score for EVERY historical point to provide deeper context
            if not df_block.empty:
                # Re-use the timeframe logic from the technical report (Day if < 15, Week otherwise)
                if validation_days < 15:
                    tech_timeframe, s_ma, l_ma = 'Day', 5, 10
                else:
                    tech_timeframe, s_ma, l_ma = 'Week', 4, 12
                
                # Fetch full data for technical context in one go for efficiency
                with st.spinner("Calculating historical technical scores..."):
                    query_all = build_historical_context_query()
                    conn = engine.raw_connection()
                    try:
                        df_full = pd.read_sql(query_all, conn, params={"ticker": ticker.upper()})
                    finally:
                        conn.close()
                    
                    if not df_full.empty:
                        df_full['date'] = pd.to_datetime(df_full['date'])
                        # Resample full history to match selected timeframe
                        if tech_timeframe == 'Week':
                            df_full = df_full.set_index('date').resample('W').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna().reset_index()
                        
                        # Precompute each as-of score once. Event dates below
                        # use binary-search lookups instead of rescanning a
                        # growing historical prefix for every event.
                        historical_scores = build_historical_technical_score_table(
                            df_full,
                            s_ma,
                            l_ma,
                        )
                        
                        def score_point(target_date):
                            target_dt = pd.to_datetime(target_date)
                            # Use binary search to find the index of the latest technical data point 
                            # on or before the signal date. This is critical for Weekly/Monthly timeframes.
                            idx = df_full['date'].searchsorted(target_dt, side='right') - 1
                            
                            # Lower threshold from 30 to 10 to provide scores for earlier historical points.
                            if idx < 10: return None
                            if idx >= len(historical_scores):
                                return None
                            value = historical_scores.iloc[idx]
                            return None if pd.isna(value) else value

                        # Identify the result category with the highest frequency (Up, Down, or No Change)
                        # to focus the historical technical context analysis on the most likely outcome,
                        # as per the requirement to analyze the technical trend of the 'higher result'.
                        # Count of Up include Up/Strong Up, Down include Down/Strong Down, No Change include No Change/Sideways.
                        probs = {"Up": up_prob, "Down": down_prob, "No Change": no_change_prob}
                        target_res = max(probs, key=probs.get)

                        # Apply calculation ONLY to rows matching the predicted result to save processing time.
                        # Other rows in the detailed report will show 'None' or 'NaN'.
                        df_block['Technical score'] = None
                        mask = df_block['result'] == target_res
                        if mask.any():
                            df_block.loc[mask, 'Technical score'] = df_block.loc[mask, 'event_date'].apply(score_point)
                        
                        matches = df_block[mask]
                        
                        if not matches.empty:
                            # Categorize matching scores based on technical trend logic:
                            # Up (>= 53), Sideway (48-52), Down (< 48)
                            up_m = matches[matches['Technical score'] >= 53]
                            sw_m = matches[(matches['Technical score'] >= 48) & (matches['Technical score'] < 53)]
                            dw_m = matches[matches['Technical score'] < 48]
                            
                            # Lookup emoji for predicted result category (target_res is Up, No Change, or Down)
                            res_emoji = TREND_EMOJIS.get(target_res, TREND_EMOJIS.get("Sideways" if target_res == "No Change" else "Unknown", "❓"))
                            
                            summary_txt = (f"technical trend summary of {len(matches)} times {target_res} {res_emoji}: "
                                          f"{len(up_m)} times Up 📈 (Avg. score: {up_m['Technical score'].mean() if not up_m.empty else 0:.1f}%), "
                                          f"{len(sw_m)} times Sideway/Unknowns ♻️ (Avg. score: {sw_m['Technical score'].mean() if not sw_m.empty else 0:.1f}%), "
                                          f"{len(dw_m)} times Down 📉 (Avg. score: {dw_m['Technical score'].mean() if not dw_m.empty else 0:.1f}%)")
                            st.markdown(f"*{summary_txt}*")

            # --- 2.3 Block Day and Delta Statistical Report ---
            # Collapsed by default to declutter UI
            with st.expander("Block Day and Delta Statistical Report", expanded=False):
                if not df_block.empty:
                    # Show Technical score and reorder columns for clarity
                    display_cols = ["no. events", "exact_delta", "Technical score", "result", "result_delta", "signal_date_range"]
                    st.dataframe(df_block[display_cols], use_container_width=True, hide_index=True)
                else:
                    st.write("No events found matching the criteria.")
            
            # --- 3.1 Technical Report ---
            st.subheader("Technical Report")
            
            # analyze_ticker owns the single current snapshot. The report is
            # display-ready and includes all eight indicators, including ADX
            # as a gate-only record rather than a score vote.
            tech_data = analysis_results.get("technical_signals", [])
            technical_report = analysis_results.get("technical_report", [])
            adx_value = analysis_results.get("technical_adx_value")

            if technical_report:
                report_rows = [
                    {
                        "Indicator": record["indicator"],
                        "Dimension": record["dimension"],
                        "Role": record["role"],
                        "Value": record["value"],
                        "Trend": record["trend"],
                    }
                    for record in technical_report
                ]
                st.dataframe(
                    pd.DataFrame(report_rows),
                    use_container_width=True,
                    hide_index=True,
                )

                if adx_value is None:
                    st.caption("ADX gate: not applied (ADX unavailable).")
                elif adx_value < 20:
                    st.caption("ADX gate: ADX < 20; trend-direction weight is halved.")
                else:
                    st.caption("ADX gate: ADX >= 20; trend-direction keeps full weight.")
            else:
                st.info("Not enough data to generate the Technical Report.")
            
            # Generate Technical Advice
            technical_advice_display, technical_trend, _ = generate_technical_advice(
                tech_data, adx_value=adx_value
            )

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
